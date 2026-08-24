import hashlib
import hmac
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuditLog, Company, Conversation, ConversationChannel, HelpRequest, Message, Store
from ..services.classifier import classify_incoming
from ..services.company_routing import detect_company
from ..services.decision_tree import match_response_with_action
from ..services.notifications import emit_notification
from ..services.whatsapp import extract_messages, send_text_message

router = APIRouter(prefix='/webhooks/whatsapp', tags=['whatsapp'])
HUMAN_PAUSE_MINUTES = 60


@router.get('')
def verify_webhook(hub_mode: str | None = Query(default=None, alias='hub.mode'), hub_verify_token: str | None = Query(default=None, alias='hub.verify_token'), hub_challenge: str | None = Query(default=None, alias='hub.challenge')):
    if hub_mode == 'subscribe' and settings.whatsapp_verify_token and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge or '', media_type='text/plain')
    raise HTTPException(status_code=403, detail='Verificación de webhook inválida')


def verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not settings.whatsapp_app_secret:
        if settings.environment.lower() == 'production':
            raise HTTPException(status_code=503, detail='WHATSAPP_APP_SECRET no configurado')
        return
    if not signature_header or not signature_header.startswith('sha256='):
        raise HTTPException(status_code=401, detail='Firma de webhook faltante')
    expected = hmac.new(settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.split('=', 1)[1]
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail='Firma de webhook inválida')


def _ensure_help(db: Session, conversation: Conversation, company: Company, store: Store, wa_user_id: str, body: str, reason: str) -> None:
    conversation.status = 'help_pending'
    help_request = db.query(HelpRequest).filter(HelpRequest.conversation_id == conversation.id, HelpRequest.status.in_(['new', 'reviewing'])).first()
    if not help_request:
        help_request = HelpRequest(company_id=company.id, conversation_id=conversation.id, wa_user_id=wa_user_id, body=body, reason=reason, status='new', is_known_contact=False, is_group=False)
        db.add(help_request)
        db.flush()
        emit_notification(db, audience='admin', event_type='help_request_new', title=f'Nueva solicitud de ayuda - {store.name}', body=f'{company.name}: {wa_user_id} solicita atención humana.', event_key=f'help:{help_request.id}:admin:new', details={'help_request_id': help_request.id, 'company': company.name, 'store': store.name, 'wa_user_id': wa_user_id})
    db.add(AuditLog(action='human_help_request', entity='conversation', entity_id=str(conversation.id), details={'from': wa_user_id, 'company': company.company_key, 'store': store.name, 'chatbot_pause_minutes': HUMAN_PAUSE_MINUTES}))


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


@router.post('')
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    verify_signature(raw_body, request.headers.get('X-Hub-Signature-256'))
    payload = await request.json()

    for incoming in extract_messages(payload):
        wa_user_id = incoming.get('from')
        if not wa_user_id:
            continue
        classification = classify_incoming(db, incoming)
        if classification['is_group']:
            db.add(AuditLog(action='whatsapp_group_ignored', entity='whatsapp', entity_id=incoming.get('id'), details={'from': wa_user_id}))
            continue

        phone_number_id = incoming.get('phone_number_id')
        store = db.query(Store).filter(Store.whatsapp_phone_number_id == phone_number_id).first() if phone_number_id else None
        fallback_company = db.get(Company, store.company_id) if store else None
        if not fallback_company:
            db.add(AuditLog(action='whatsapp_message_ignored', entity='whatsapp', entity_id=incoming.get('id'), details={'reason': 'unknown_phone_number_id', 'phone_number_id': phone_number_id, 'from': wa_user_id}))
            continue

        message_text = incoming.get('text') or ''
        company, routing = detect_company(db, message_text, fallback=fallback_company)
        company = company or fallback_company
        duplicate = db.query(Message).filter(Message.provider_message_id == incoming.get('id')).first() if incoming.get('id') else None
        if duplicate:
            continue

        conversation = db.query(Conversation).filter(
            Conversation.wa_user_id == wa_user_id,
            Conversation.company_id == company.id,
            Conversation.status.in_(['open', 'help_pending', 'human_active']),
        ).order_by(Conversation.id.desc()).first()
        if not conversation:
            conversation = Conversation(company_id=company.id, wa_user_id=wa_user_id, state=(company.decision_tree or {}).get('nodo_raiz') or 'inicio')
            db.add(conversation)
            db.flush()

        channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
        if not channel:
            channel = ConversationChannel(conversation_id=conversation.id)
            db.add(channel)
        channel.company_id = company.id
        channel.store_id = store.id
        channel.phone_number_id = phone_number_id

        db.add(Message(conversation_id=conversation.id, direction='inbound', sender=wa_user_id, body=message_text, provider_message_id=incoming.get('id'), raw_payload={'provider': incoming.get('raw'), 'classification': classification, 'phone_number_id': phone_number_id, 'store_id': store.id, 'company_routing': routing}))
        db.add(AuditLog(action='company_routing', entity='conversation', entity_id=str(conversation.id), details={'company': company.company_key, 'store': store.name, **routing}))

        if classification['is_known_contact']:
            db.add(AuditLog(action='authorized_support_bot_skipped', entity='conversation', entity_id=str(conversation.id), details={'from': wa_user_id, 'company': company.company_key, 'store': store.name}))
            continue

        tree = company.decision_tree or {}
        root_state = tree.get('nodo_raiz') or 'inicio'
        if conversation.status in ('help_pending', 'human_active'):
            request_row, pause_until = _human_pause_deadline(db, conversation.id)
            now = datetime.utcnow()
            if pause_until and now < pause_until:
                db.add(AuditLog(action='chatbot_skipped_human_support', entity='conversation', entity_id=str(conversation.id), details={'from': wa_user_id, 'store': store.name, 'conversation_status': conversation.status, 'help_request_id': request_row.id if request_row else None, 'pause_until': pause_until.isoformat(), 'remaining_seconds': max(1, int((pause_until - now).total_seconds()))}))
                continue
            conversation.status = 'open'
            conversation.state = root_state
            db.add(AuditLog(action='chatbot_auto_resumed_after_human_timeout', entity='conversation', entity_id=str(conversation.id), details={'help_request_id': request_row.id if request_row else None, 'pause_minutes': HUMAN_PAUSE_MINUTES}))

        matched, response_text, next_state, action = match_response_with_action(tree, conversation.state, message_text)
        if matched:
            conversation.state = next_state
            if action == 'human_help':
                _ensure_help(db, conversation, company, store, wa_user_id, message_text, 'decision_tree_human_help')
            try:
                send_result = send_text_message(wa_user_id, response_text, phone_number_id=phone_number_id, db=db)
            except Exception as exc:
                send_result = {'sent': False, 'error': str(exc)}
            db.add(Message(conversation_id=conversation.id, direction='outbound', sender='bot', body=response_text, raw_payload=send_result if isinstance(send_result, dict) else None))
            db.add(AuditLog(action='decision_tree_bot_match', entity='conversation', entity_id=str(conversation.id), details={'from': wa_user_id, 'state': conversation.state, 'action': action, 'sent': bool(send_result.get('sent')) if isinstance(send_result, dict) else False, 'store': store.name, 'company': company.company_key}))
            if isinstance(send_result, dict) and not send_result.get('sent'):
                db.add(AuditLog(action='whatsapp_send_blocked', entity='conversation', entity_id=str(conversation.id), details={'to': wa_user_id, 'reason': send_result.get('reason') or send_result.get('error')}))
            continue

        if classification['help_requested']:
            _ensure_help(db, conversation, company, store, wa_user_id, message_text, 'human_help_requested')
        else:
            db.add(AuditLog(action='unknown_contact_no_tree_match', entity='conversation', entity_id=str(conversation.id), details={'from': wa_user_id, 'store': store.name, 'company': company.company_key}))

    db.commit()
    return {'status': 'ok'}