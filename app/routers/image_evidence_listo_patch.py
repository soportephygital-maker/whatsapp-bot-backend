from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Message, User
from . import image_evidence_patch, local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-image-finish'])

LISTO_WORDS = {'listo', 'lista', 'ya', 'continuar', 'continua', 'continuemos', 'terminar', 'finalizar'}
LISTO_TEXT = '✅ Listo. La evidencia quedó registrada en el reporte. Puedes continuar con la atención.'


def _save_listo_message(db: Session, data: local_bridge.LocalInbound, conversation) -> None:
    provider_message_id = local_bridge._provider_message_id(data)
    if db.query(Message).filter(Message.provider_message_id == provider_message_id).first():
        return
    db.add(Message(
        conversation_id=conversation.id,
        direction='inbound',
        sender=local_bridge._local_user_id(data),
        body=data.text,
        provider_message_id=provider_message_id,
        raw_payload={
            'provider': 'android_notification',
            'package_name': data.package_name,
            'device_id': data.device_id,
            'notification_key': data.notification_key,
            'post_time': data.post_time,
            'sender_display': data.sender,
            'sender_key': data.sender_key,
            'reply_capable': data.can_reply,
            'metadata': dict(data.metadata or {}),
            'image_evidence_finish': True,
        },
    ))


def _last_outbound_is_image_confirmation(db: Session, conversation_id: int) -> bool:
    row = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'outbound',
    ).order_by(Message.id.desc()).first()
    text = str(row.body or '') if row else ''
    return 'foto quedó registrada' in text.lower() or 'evidencia quedó registrada' in text.lower()


@router.post('/inbound')
def image_evidence_finish_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    normalized = image_evidence_patch._normalized(data.text)
    local_user_id, conversation, company, store, ticket = image_evidence_patch._active_context(db, data)
    if conversation and company and store and normalized in LISTO_WORDS:
        in_photo_state = conversation.state in {image_evidence_patch.IMAGE_CONFIRM_STATE, image_evidence_patch.IMAGE_WAIT_STATE}
        just_confirmed = _last_outbound_is_image_confirmation(db, conversation.id)
        if in_photo_state or just_confirmed:
            context = image_evidence_patch._latest_image_context(db, conversation.id)
            return_state = str(context.get('return_state') or '').strip()
            if return_state and return_state not in {image_evidence_patch.IMAGE_CONFIRM_STATE, image_evidence_patch.IMAGE_WAIT_STATE}:
                conversation.state = return_state
            _save_listo_message(db, data, conversation)
            outbound = image_evidence_patch._reply(
                db,
                conversation=conversation,
                company=company,
                store=store,
                data=data,
                text=LISTO_TEXT,
            )
            db.commit()
            return {
                'status': 'ok',
                'conversation_id': conversation.id,
                'company_key': company.company_key,
                'company_name': company.name,
                'store_name': store.name,
                'action': 'image_evidence_finished',
                'reply_text': LISTO_TEXT if data.can_reply else '',
                'should_reply': bool(data.can_reply),
                'outbound_message_id': outbound.id,
                'ticket_id': ticket.id if ticket else None,
                'chatbot_paused': False,
            }
    return image_evidence_patch.image_evidence_inbound(data=data, operator=operator, db=db)
