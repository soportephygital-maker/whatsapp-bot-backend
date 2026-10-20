from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import AuditLog, Company, Conversation, ConversationChannel, Message, Store, User
from . import local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['post-close-flow'])
COOLDOWN_MINUTES = 30


def _normalized(value: str) -> str:
    return local_bridge._normalize_text(value)


def _latest_touch(db: Session, conversation_id: int):
    return db.query(AuditLog).filter(
        AuditLog.action == 'post_close_cooldown_touch',
        AuditLog.entity == 'conversation',
        AuditLog.entity_id == str(conversation_id),
    ).order_by(AuditLog.id.desc()).first()


def _delete_base_outbound(db: Session, result: dict) -> None:
    outbound_id = result.get('outbound_message_id') if isinstance(result, dict) else None
    if outbound_id:
        row = db.get(Message, outbound_id)
        if row:
            db.delete(row)
    result['outbound_message_id'] = None
    result['reply_text'] = ''
    result['should_reply'] = False


def _store_for_conversation(db: Session, conversation: Conversation) -> Store | None:
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    return db.get(Store, channel.store_id) if channel and channel.store_id else None


def _queue_reply(db: Session, result: dict, data: local_bridge.LocalInbound, conversation: Conversation, text: str) -> None:
    company = db.get(Company, conversation.company_id) if conversation.company_id else None
    store = _store_for_conversation(db, conversation)
    if not company or not store:
        result['reply_text'] = ''
        result['should_reply'] = False
        return
    row = local_bridge._queue_outbound(db, conversation=conversation, text=text, data=data, company=company, store=store)
    result['conversation_id'] = conversation.id
    result['outbound_message_id'] = row.id
    result['reply_text'] = text if data.can_reply else ''
    result['should_reply'] = bool(data.can_reply)


def _new_conversation_from_old(db: Session, old: Conversation, data: local_bridge.LocalInbound) -> Conversation:
    company = db.get(Company, old.company_id) if old.company_id else None
    root = local_bridge._root_state(company.decision_tree or {}) if company else 'inicio'
    old.status = 'closed'
    old.state = 'closed_previous_ticket'
    new = Conversation(company_id=old.company_id, wa_user_id=old.wa_user_id, status='open', state=root)
    db.add(new)
    db.flush()
    old_channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == old.id).first()
    db.add(ConversationChannel(
        conversation_id=new.id,
        company_id=old_channel.company_id if old_channel else old.company_id,
        store_id=old_channel.store_id if old_channel else data.store_id,
        phone_number_id=old_channel.phone_number_id if old_channel else f'android:{data.device_id}'[:80],
    ))
    db.flush()
    return new


@router.post('/inbound')
def post_close_inbound(data: local_bridge.LocalInbound, operator: User = Depends(require_operator), db: Session = Depends(get_db)):
    local_user_id = local_bridge._local_user_id(data)
    conversation = db.query(Conversation).filter(
        Conversation.wa_user_id == local_user_id,
        Conversation.status.in_(['open', 'help_pending', 'human_active']),
    ).order_by(Conversation.id.desc()).first()

    if not conversation or conversation.state not in {'post_close_prompt', 'post_close_wait'}:
        return ticketed_local_bridge.ticketed_local_inbound(data=data, operator=operator, db=db)

    if conversation.state == 'post_close_wait':
        touch = _latest_touch(db, conversation.id)
        now = datetime.utcnow()
        if touch and touch.created_at and now - touch.created_at >= timedelta(minutes=COOLDOWN_MINUTES):
            conversation.status = 'closed'
            conversation.state = 'closed_previous_ticket'
            db.flush()
            return ticketed_local_bridge.ticketed_local_inbound(data=data, operator=operator, db=db)

        result = local_bridge.local_inbound(data=data, operator=operator, db=db)
        _delete_base_outbound(db, result)
        conversation = db.get(Conversation, conversation.id)
        conversation.status = 'open'
        conversation.state = 'post_close_wait'
        db.add(AuditLog(
            username=operator.username,
            action='post_close_cooldown_touch',
            entity='conversation',
            entity_id=str(conversation.id),
            details={'minutes': COOLDOWN_MINUTES, 'sender': data.sender},
        ))
        result.update({'status': 'post_close_cooldown', 'chatbot_paused': True, 'cooldown_minutes': COOLDOWN_MINUTES})
        db.commit()
        return result

    result = local_bridge.local_inbound(data=data, operator=operator, db=db)
    _delete_base_outbound(db, result)
    answer = _normalized(data.text)
    yes = answer in {'1', 'si', 'sí', 'yes', 'claro', 'nuevo', 'otro problema'}
    no = answer in {'2', 'no', 'no gracias', 'ninguno', 'nada mas'}

    if yes:
        new = _new_conversation_from_old(db, conversation, data)
        _queue_reply(db, result, data, new, 'Perfecto. Iniciaremos un reporte nuevo sin borrar el ticket anterior.\n\nCuéntame cuál es el nuevo problema.')
        result.update({'status': 'new_issue_started', 'action': 'new_ticket_conversation'})
        db.add(AuditLog(username=operator.username, action='post_close_new_issue', entity='conversation', entity_id=str(new.id), details={'previous_conversation_id': conversation.id}))
    elif no:
        conversation.status = 'open'
        conversation.state = 'post_close_wait'
        _queue_reply(db, result, data, conversation, 'Entendido. El ticket anterior permanecerá cerrado. Si vuelves a escribir, esperaré 30 minutos sin responder para evitar reiniciar la atención por error.')
        result.update({'status': 'post_close_wait', 'action': 'post_close_no_new_issue'})
        db.add(AuditLog(username=operator.username, action='post_close_no_new_issue', entity='conversation', entity_id=str(conversation.id), details={'cooldown_minutes': COOLDOWN_MINUTES}))
    else:
        conversation.status = 'open'
        conversation.state = 'post_close_prompt'
        _queue_reply(db, result, data, conversation, '¿Quieres reportar otro problema?\n1️⃣ Sí, abrir un reporte nuevo\n2️⃣ No')
        result.update({'status': 'post_close_prompt', 'action': 'post_close_prompt'})

    db.commit()
    return result
