import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_operator
from ..database import get_db
from ..models import AuditLog, Company, Conversation, ConversationChannel, HelpRequest, Message, Store, User
from ..services.classifier import classify_incoming
from ..services.company_routing import detect_company
from ..services.decision_tree import match_response_with_action
from ..services.notifications import emit_notification

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge'])

ALLOWED_PACKAGES = {'com.whatsapp', 'com.whatsapp.w4b'}
DEFAULT_NO_MATCH_FIRST = 'No pude identificar una opción válida. Por favor describe nuevamente lo que necesitas o usa alguna de las opciones disponibles.'
DEFAULT_NO_MATCH_REPEAT = 'Sigo sin poder identificar tu solicitud. Revisa las opciones disponibles o escribe humano si necesitas atención de una persona.'
HUMAN_PAUSE_MINUTES = 60


class LocalInbound(BaseModel):
    package_name: str
    device_id: str = Field(min_length=4, max_length=120)
    notification_key: str = Field(min_length=1, max_length=500)
    post_time: int = 0
    sender: str = Field(default='Contacto', max_length=200)
    sender_key: str = Field(default='', max_length=500)
    text: str = Field(min_length=1, max_length=5000)
    store_id: int | None = None
    selected_store_ids: list[int] = Field(default_factory=list)
    is_group: bool = False
    can_reply: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeliveryUpdate(BaseModel):
    message_id: int
    sent: bool
    notification_key: str | None = None
    error: str | None = None


def _local_user_id(data: LocalInbound) -> str:
    identity = data.sender_key.strip() or data.sender.strip() or data.notification_key
    digest = hashlib.sha256(f'{data.package_name}|{identity}'.encode()).hexdigest()[:20]
    label = ' '.join(data.sender.split())[:42]
    return f'local:{digest}:{label}'[:80]


def _provider_message_id(data: LocalInbound) -> str:
    raw = '|'.join([data.device_id, data.package_name, data.notification_key, str(data.post_time), data.sender_key, data.text])
    return 'local:' + hashlib.sha256(raw.encode()).hexdigest()[:56]


def _root_state(tree: dict) -> str:
    return str(tree.get('nodo_raiz') or tree.get('root') or 'inicio')


def _no_match_message(tree: dict, repeated: bool) -> str:
    key = 'respuesta_sin_sentido_2' if repeated else 'respuesta_sin_sentido_1'
    fallback = DEFAULT_NO_MATCH_REPEAT if repeated else DEFAULT_NO_MATCH_FIRST
    return str(tree.get(key) or fallback).strip()


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _explicit_human_request(value: str) -> bool:
    text = f" {_normalize_text(value)} "
    phrases = (
        ' humano ', ' una persona ', ' hablar con una persona ', ' hablar con alguien ',
        ' asesor ', ' asesora ', ' agente humano ', ' atencion humana ',
    )
    return any(phrase in text for phrase in phrases)


def _previous_message_was_unmatched(db: Session, conversation_id: int, current_message_id: int) -> bool:
    row = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'inbound',
        Message.id < current_message_id,
    ).order_by(Message.id.desc()).first()
    if not row:
        return False
    return bool((row.raw_payload or {}).get('tree_unmatched'))


def _human_pause_deadline(db: Session, conversation_id: int) -> tuple[HelpRequest | None, datetime | None]:
    request = db.query(HelpRequest).filter(
        HelpRequest.conversation_id == conversation_id,
        HelpRequest.status.in_(['new', 'reviewing']),
    ).order_by(HelpRequest.created_at.desc()).first()

    anchor = request.created_at if request else None
    recent_outbound = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'outbound',
    ).order_by(Message.id.desc()).limit(50).all()
    for row in recent_outbound:
        payload = row.raw_payload or {}
        is_manual = bool(payload.get('manual') or payload.get('manual_dashboard') or (row.sender and row.sender != 'bot'))
        if not is_manual:
            continue
        if row.created_at and (anchor is None or row.created_at > anchor):
            anchor = row.created_at
        break

    if anchor is None:
        return request, None
    return request, anchor + timedelta(minutes=HUMAN_PAUSE_MINUTES)


def _selected_stores(data: LocalInbound, db: Session) -> list[Store]:
    ids = list(dict.fromkeys([*(data.selected_store_ids or []), *([data.store_id] if data.store_id else [])]))
    if not ids:
        raise HTTPException(status_code=409, detail='Selecciona al menos una tienda en la app')
    rows = db.query(Store).join(Company, Store.company_id == Company.id).filter(
        Store.id.in_(ids), Company.is_active.is_(True)
    ).order_by(Store.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=409, detail='Las tiendas seleccionadas ya no están disponibles')
    return rows


def _ensure_help_request(db: Session, *, conversation: Conversation, company: Company, store: Store, local_user_id: str, body: str, reason: str) -> HelpRequest:
    conversation.status = 'help_pending'
    row = db.query(HelpRequest).filter(HelpRequest.conversation_id == conversation.id, HelpRequest.status.in_(['new', 'reviewing'])).first()
    if row:
        return row
    row = HelpRequest(company_id=company.id, conversation_id=conversation.id, wa_user_id=local_user_id, body=body, reason=reason, status='new', is_known_contact=False, is_group=False)
    db.add(row)
    db.flush()
    emit_notification(db, audience='admin', event_type='help_request_new', title=f'Nueva solicitud de ayuda - {store.name}', body=f'{company.name}: {local_user_id} solicita atención humana.', event_key=f'help:{row.id}:admin:new', details={'help_request_id': row.id, 'company': company.name, 'store': store.name, 'local_user_id': local_user_id, 'transport': 'android_notification'})
    db.add(AuditLog(action='human_help_request', entity='conversation', entity_id=str(conversation.id), details={'from': local_user_id, 'company': company.company_key, 'store': store.name, 'transport': 'android_notification', 'chatbot_pause_minutes': HUMAN_PAUSE_MINUTES}))
    return row


def _queue_outbound(db: Session, *, conversation: Conversation, text: str, data: LocalInbound, company: Company, store: Store) -> Message:
    row = Message(conversation_id=conversation.id, direction='outbound', sender='bot', body=text, raw_payload={'transport': 'android_notification', 'delivery_status': 'requested', 'can_reply': data.can_reply, 'notification_key': data.notification_key, 'device_id': data.device_id, 'company': company.company_key, 'store': store.name})
    db.add(row)
    db.flush()
    return row


@router.get('/stores')
def bridge_stores(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Store).join(Company, Store.company_id == Company.id).filter(Company.is_active.is_(True)).order_by(Company.name.asc(), Store.name.asc()).all()
    return [{'id': row.id, 'name': row.name, 'company_id': row.company_id, 'company_key': row.company.company_key, 'company_name': row.company.name} for row in rows]


@router.get('/manual-pending')
def manual_pending(device_id: str, operator: User = Depends(require_operator), db: Session = Depends(get_db)):
    channel_rows = db.query(ConversationChannel).filter(ConversationChannel.phone_number_id == f'android:{device_id}').all()
    conversation_ids = [row.conversation_id for row in channel_rows]
    if not conversation_ids:
        return []
    rows = db.query(Message).filter(
        Message.conversation_id.in_(conversation_ids),
        Message.direction == 'outbound',
    ).order_by(Message.id.asc()).limit(100).all()
    result = []
    for row in rows:
        payload = row.raw_payload or {}
        if payload.get('transport') != 'android_notification':
            continue
        if not payload.get('manual_dashboard'):
            continue
        if payload.get('device_id') != device_id:
            continue
        if payload.get('delivery_status') != 'requested':
            continue
        result.append({
            'message_id': row.id,
            'conversation_id': row.conversation_id,
            'text': row.body,
            'notification_key': payload.get('notification_key'),
            'package_name': payload.get('package_name'),
            'sender_display': payload.get('sender_display'),
            'operator': payload.get('operator'),
        })
    if result:
        db.add(AuditLog(username=operator.username, action='local_bridge_manual_poll', entity='local_bridge', entity_id=device_id, details={'pending': len(result)}))
        db.commit()
    return result


@router.post('/inbound')
def local_inbound(data: LocalInbound, operator: User = Depends(require_operator), db: Session = Depends(get_db)):
    if data.package_name not in ALLOWED_PACKAGES:
        raise HTTPException(status_code=400, detail='Paquete no autorizado para el puente local')

    selected_stores = _selected_stores(data, db)
    selected_company_ids = {row.company_id for row in selected_stores}
    fallback_store = selected_stores[0]
    fallback_company = db.get(Company, fallback_store.company_id)

    provider_message_id = _provider_message_id(data)
    duplicate = db.query(Message).filter(Message.provider_message_id == provider_message_id).first()
    if duplicate:
        return {'status': 'duplicate', 'should_reply': False, 'conversation_id': duplicate.conversation_id}

    local_user_id = _local_user_id(data)
    classification = classify_incoming(db, {'from': data.sender, 'text': data.text, 'is_group': data.is_group, 'raw': {'group_id': 'local' if data.is_group else None}})
    if classification['is_group']:
        db.add(AuditLog(username=operator.username, action='local_bridge_group_ignored', entity='local_bridge', entity_id=provider_message_id, details={'sender': data.sender, 'package': data.package_name}))
        db.commit()
        return {'status': 'ignored_group', 'should_reply': False}

    company, routing = detect_company(db, data.text, fallback=fallback_company)
    if not company or company.id not in selected_company_ids:
        company = fallback_company
        routing = {'reason': 'selected_store_fallback'}
    store = next((row for row in selected_stores if row.company_id == company.id), fallback_store)

    conversation = db.query(Conversation).filter(
        Conversation.wa_user_id == local_user_id,
        Conversation.company_id == company.id,
        Conversation.status.in_(['open', 'help_pending', 'human_active']),
    ).order_by(Conversation.id.desc()).first()
    if not conversation:
        conversation = Conversation(company_id=company.id, wa_user_id=local_user_id, state=_root_state(company.decision_tree or {}))
        db.add(conversation)
        db.flush()

    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    if not channel:
        channel = ConversationChannel(conversation_id=conversation.id)
        db.add(channel)
    channel.company_id = company.id
    channel.store_id = store.id
    channel.phone_number_id = f'android:{data.device_id}'[:80]

    inbound_payload = {'provider': 'android_notification', 'package_name': data.package_name, 'device_id': data.device_id, 'notification_key': data.notification_key, 'post_time': data.post_time, 'sender_display': data.sender, 'sender_key': data.sender_key, 'reply_capable': data.can_reply, 'store_id': store.id, 'selected_store_ids': [s.id for s in selected_stores], 'classification': classification, 'company_routing': routing, 'metadata': data.metadata}
    inbound_message = Message(conversation_id=conversation.id, direction='inbound', sender=local_user_id, body=data.text, provider_message_id=provider_message_id, raw_payload=inbound_payload)
    db.add(inbound_message)
    db.flush()
    db.add(AuditLog(username=operator.username, action='local_bridge_inbound', entity='conversation', entity_id=str(conversation.id), details={'company': company.company_key, 'store': store.name, 'sender': data.sender, 'package': data.package_name, 'routing': routing, 'selected_store_ids': [s.id for s in selected_stores]}))

    if classification['is_known_contact']:
        db.add(AuditLog(username=operator.username, action='authorized_support_bot_skipped', entity='conversation', entity_id=str(conversation.id), details={'from': data.sender, 'transport': 'android_notification'}))
        db.commit()
        return {'status': 'known_support_skipped', 'should_reply': False, 'conversation_id': conversation.id}

    tree = company.decision_tree or {}
    root_state = _root_state(tree)
    if conversation.status in ('help_pending', 'human_active'):
        request_row, pause_until = _human_pause_deadline(db, conversation.id)
        now = datetime.utcnow()
        if pause_until and now < pause_until:
            remaining_seconds = max(1, int((pause_until - now).total_seconds()))
            inbound_payload['chatbot_paused'] = True
            inbound_payload['human_pause_until'] = pause_until.isoformat()
            inbound_message.raw_payload = dict(inbound_payload)
            db.add(AuditLog(username=operator.username, action='chatbot_skipped_human_support', entity='conversation', entity_id=str(conversation.id), details={'sender': data.sender, 'store': store.name, 'conversation_status': conversation.status, 'help_request_id': request_row.id if request_row else None, 'pause_until': pause_until.isoformat(), 'remaining_seconds': remaining_seconds}))
            db.commit()
            return {'status': 'human_support_paused', 'conversation_id': conversation.id, 'should_reply': False, 'chatbot_paused': True, 'pause_until': pause_until.isoformat(), 'remaining_seconds': remaining_seconds}

        conversation.status = 'open'
        conversation.state = root_state
        db.add(AuditLog(username=operator.username, action='chatbot_auto_resumed_after_human_timeout', entity='conversation', entity_id=str(conversation.id), details={'help_request_id': request_row.id if request_row else None, 'pause_minutes': HUMAN_PAUSE_MINUTES}))

    matched, response_text, next_state, action = match_response_with_action(tree, conversation.state, data.text)
    matched_from_root = False
    if not matched and conversation.state != root_state:
        matched, response_text, next_state, action = match_response_with_action(tree, root_state, data.text)
        matched_from_root = matched

    if matched:
        conversation.state = next_state
        if action != 'human_help':
            conversation.status = 'open'
        inbound_payload['tree_unmatched'] = False
        inbound_payload['tree_matched_from_root'] = matched_from_root
        inbound_message.raw_payload = dict(inbound_payload)
        if action == 'human_help':
            _ensure_help_request(db, conversation=conversation, company=company, store=store, local_user_id=local_user_id, body=data.text, reason='decision_tree_human_help')
    elif _explicit_human_request(data.text):
        inbound_payload['tree_unmatched'] = False
        inbound_message.raw_payload = dict(inbound_payload)
        _ensure_help_request(db, conversation=conversation, company=company, store=store, local_user_id=local_user_id, body=data.text, reason='explicit_human_request')
        response_text = ''
        action = 'human_help'
    else:
        repeated = _previous_message_was_unmatched(db, conversation.id, inbound_message.id)
        inbound_payload['tree_unmatched'] = True
        inbound_payload['tree_unmatched_repeated'] = repeated
        inbound_message.raw_payload = dict(inbound_payload)
        response_text = _no_match_message(tree, repeated)
        action = 'no_match_repeat' if repeated else 'no_match_first'

    if action == 'human_help':
        response_text = ''
        inbound_payload['chatbot_paused'] = True
        inbound_payload['human_handoff_silent'] = True
        inbound_message.raw_payload = dict(inbound_payload)

    response_text = (response_text or '').strip()
    should_reply = bool(response_text and data.can_reply)
    outbound_message_id = None
    if response_text:
        outbound = _queue_outbound(db, conversation=conversation, text=response_text, data=data, company=company, store=store)
        outbound_message_id = outbound.id
        if not data.can_reply:
            payload = dict(outbound.raw_payload or {})
            payload['delivery_status'] = 'not_reply_capable'
            outbound.raw_payload = payload

    db.commit()
    return {'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key, 'company_name': company.name, 'store_name': store.name, 'routing': routing, 'action': action, 'reply_text': response_text if should_reply else '', 'should_reply': should_reply, 'outbound_message_id': outbound_message_id, 'chatbot_paused': action == 'human_help'}


@router.post('/delivery')
def local_delivery(data: DeliveryUpdate, operator: User = Depends(require_operator), db: Session = Depends(get_db)):
    message = db.get(Message, data.message_id)
    if not message or message.direction != 'outbound':
        raise HTTPException(status_code=404, detail='Mensaje de salida no encontrado')
    payload = dict(message.raw_payload or {})
    if payload.get('transport') != 'android_notification':
        raise HTTPException(status_code=409, detail='El mensaje no pertenece al puente Android')
    payload['delivery_status'] = 'sent' if data.sent else 'failed'
    if data.notification_key:
        payload['notification_key'] = data.notification_key
    if data.error:
        payload['delivery_error'] = data.error[:1000]
    message.raw_payload = payload
    db.add(AuditLog(username=operator.username, action='local_bridge_reply_sent' if data.sent else 'local_bridge_reply_failed', entity='message', entity_id=str(message.id), details={'conversation_id': message.conversation_id, 'error': data.error, 'manual_dashboard': bool(payload.get('manual_dashboard'))}))
    db.commit()
    return {'status': 'ok', 'message_id': message.id, 'sent': data.sent}
