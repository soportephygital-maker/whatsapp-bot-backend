import os
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import get_current_user, require_admin, require_case_closer, require_operator, require_primary_admin
from ..database import get_db
from ..models import AppNotification, AuditLog, Company, Contact, Conversation, ConversationChannel, GlobalSetting, HelpRequest, Message, Store, User
from ..schemas import ConversationReply, HelpRequestStatus, UIAuditEvent
from ..services.escalation import process_help_escalations
from ..services.notifications import audience_for_role, emit_notification
from ..services.whatsapp import send_text_message

router = APIRouter(prefix='/api', tags=['dashboard'])
OWNER_ALIAS_KEY = 'owner_display_alias'
DEFAULT_OWNER_ALIAS = 'Zoe Ortiz'


def _hidden_admin_username() -> str:
    return (os.getenv('BOOTSTRAP_ADMIN_USERNAME') or '').strip()


def _owner_alias(db: Session) -> str:
    row = db.get(GlobalSetting, OWNER_ALIAS_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return str(value.get('alias') or DEFAULT_OWNER_ALIAS).strip() or DEFAULT_OWNER_ALIAS


@router.get('/stats')
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        'empresas': db.query(func.count(Company.id)).filter(Company.is_active.is_(True)).scalar() or 0,
        'contactos_soporte_autorizados': db.query(func.count(Contact.id)).filter(Contact.is_active.is_(True)).scalar() or 0,
        'conversaciones': db.query(func.count(Conversation.id)).scalar() or 0,
        'mensajes': db.query(func.count(Message.id)).scalar() or 0,
        'solicitudes_ayuda_nuevas': db.query(func.count(HelpRequest.id)).filter(HelpRequest.status == 'new').scalar() or 0,
    }


@router.get('/notifications')
def notifications(after_id: int = Query(default=0, ge=0), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    audiences = audience_for_role(user.role)
    rows = db.query(AppNotification).filter(AppNotification.id > after_id, AppNotification.audience.in_(audiences)).order_by(AppNotification.id.asc()).limit(100).all()
    return [{'id': row.id, 'event_type': row.event_type, 'title': row.title, 'body': row.body, 'details': row.details or {}, 'created_at': row.created_at} for row in rows]


@router.get('/conversaciones')
def conversations(company_id: int | None = Query(default=None), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Conversation)
    if company_id is not None:
        query = query.filter(Conversation.company_id == company_id)
    rows = query.order_by(Conversation.updated_at.desc()).limit(200).all()
    support_phones = {c.phone for c in db.query(Contact).filter(Contact.is_active.is_(True)).all()}
    companies = {c.id: c.name for c in db.query(Company).all()}
    return [{'id': c.id, 'company_id': c.company_id, 'company_name': companies.get(c.company_id, 'Sin empresa'), 'wa_user_id': c.wa_user_id, 'authorized_support_contact': ''.join(ch for ch in c.wa_user_id if ch.isdigit()) in support_phones, 'known_contact': ''.join(ch for ch in c.wa_user_id if ch.isdigit()) in support_phones, 'state': c.state, 'status': c.status, 'updated_at': c.updated_at} for c in rows]


@router.get('/conversaciones/{conversation_id}/mensajes')
def conversation_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversación no encontrada')
    rows = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    primary_admin = _hidden_admin_username()
    alias = _owner_alias(db)
    result = []
    for row in rows:
        sender = row.sender
        internal_sender = None
        if primary_admin and sender == primary_admin:
            if user.role == 'admin':
                internal_sender = sender
            sender = alias
        raw = row.raw_payload or {}
        delivery = {
            key: raw.get(key)
            for key in ('delivery_status', 'sent', 'error', 'transport', 'provider_message_id')
            if key in raw
        }
        item = {
            'id': row.id,
            'direction': row.direction,
            'sender': sender,
            'body': row.body,
            'created_at': row.created_at,
            'delivery': delivery,
        }
        if internal_sender:
            item['internal_sender'] = internal_sender
        result.append(item)
    return result


def _activate_human_mode(db: Session, conversation: Conversation, user: User, company: Company, sender_id: str | None):
    conversation.status = 'human_active'
    pending = db.query(HelpRequest).filter(HelpRequest.conversation_id == conversation.id, HelpRequest.status.in_(['new', 'reviewing'])).all()
    for request in pending:
        request.status = 'reviewing'
        db.add(AuditLog(username=user.username, action='human_response_sent', entity='help_request', entity_id=str(request.id), details={'conversation_id': conversation.id, 'to': conversation.wa_user_id}))
    db.add(AuditLog(username=user.username, action='manual_reply_sent', entity='conversation', entity_id=str(conversation.id), details={'to': conversation.wa_user_id, 'company': company.company_key, 'phone_number_id': sender_id, 'chatbot_paused': True}))


def _latest_android_context(db: Session, conversation_id: int) -> dict:
    rows = db.query(Message).filter(Message.conversation_id == conversation_id, Message.direction == 'inbound').order_by(Message.id.desc()).limit(20).all()
    for row in rows:
        payload = row.raw_payload or {}
        if payload.get('provider') == 'android_notification':
            return payload
    return {}


@router.post('/conversaciones/{conversation_id}/responder')
def reply_conversation(conversation_id: int, data: ConversationReply, user: User = Depends(require_operator), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversación no encontrada')
    company = db.get(Company, conversation.company_id) if conversation.company_id else None
    if not company:
        raise HTTPException(status_code=409, detail='La conversación no tiene una empresa válida')
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail='La respuesta no puede estar vacía')
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    sender_id = channel.phone_number_id if channel else None
    if sender_id and sender_id.startswith('android:'):
        device_id = sender_id.split(':', 1)[1]
        context = _latest_android_context(db, conversation.id)
        notification_key = context.get('notification_key')
        package_name = context.get('package_name')
        if not notification_key or not package_name:
            raise HTTPException(status_code=409, detail='No hay una notificación activa de WhatsApp para usar como puente. Espera un mensaje nuevo del cliente y vuelve a intentar.')
        if not context.get('reply_capable', False):
            raise HTTPException(status_code=409, detail='La notificación actual de WhatsApp no permite respuesta directa desde Android.')
        message = Message(conversation_id=conversation.id, direction='outbound', sender=user.username, body=text, raw_payload={'manual': True, 'manual_dashboard': True, 'transport': 'android_notification', 'delivery_status': 'requested', 'device_id': device_id, 'notification_key': notification_key, 'package_name': package_name, 'sender_display': context.get('sender_display'), 'operator': user.username, 'company': company.company_key})
        db.add(message); db.flush(); _activate_human_mode(db, conversation, user, company, sender_id)
        db.add(AuditLog(username=user.username, action='manual_reply_queued_android', entity='message', entity_id=str(message.id), details={'conversation_id': conversation.id, 'device_id': device_id, 'notification_key': notification_key}))
        db.commit(); db.refresh(message)
        return {'status': 'queued', 'sent': False, 'queued': True, 'message_id': message.id, 'provider': {'transport': 'android_notification', 'device_id': device_id}, 'chatbot_paused': True}
    if not sender_id:
        sender_store = db.query(Store).filter(Store.company_id == company.id, Store.whatsapp_phone_number_id.isnot(None)).order_by(Store.id.asc()).first()
        sender_id = sender_store.whatsapp_phone_number_id if sender_store else None
    try:
        result = send_text_message(conversation.wa_user_id, text, phone_number_id=sender_id, db=db)
    except Exception as exc:
        db.add(AuditLog(username=user.username, action='manual_reply_error', entity='conversation', entity_id=str(conversation.id), details={'to': conversation.wa_user_id, 'error': str(exc)})); db.commit()
        raise HTTPException(status_code=502, detail=f'No se pudo enviar: {exc}') from exc
    if not result.get('sent'):
        db.add(AuditLog(username=user.username, action='manual_reply_blocked', entity='conversation', entity_id=str(conversation.id), details={'to': conversation.wa_user_id, 'reason': result.get('reason') or result.get('error')})); db.commit()
        raise HTTPException(status_code=409, detail=f"Envío bloqueado: {result.get('reason') or result.get('error') or 'configuración de seguridad'}")
    message = Message(conversation_id=conversation.id, direction='outbound', sender=user.username, body=text, raw_payload={'manual': True, 'result': result})
    db.add(message); _activate_human_mode(db, conversation, user, company, sender_id); db.commit(); db.refresh(message)
    return {'status': 'ok', 'sent': True, 'message_id': message.id, 'provider': result, 'chatbot_paused': True}


@router.get('/help-requests')
def help_requests(status: str | None = Query(default=None), company_id: int | None = Query(default=None), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(HelpRequest)
    if status: query = query.filter(HelpRequest.status == status)
    if company_id is not None: query = query.filter(HelpRequest.company_id == company_id)
    rows = query.order_by(HelpRequest.created_at.desc()).limit(200).all()
    companies = {c.id: c.name for c in db.query(Company).all()}; channel_map = {c.conversation_id: c for c in db.query(ConversationChannel).all()}; stores = {s.id: s.name for s in db.query(Store).all()}
    return [{'id': r.id, 'company_id': r.company_id, 'company_name': companies.get(r.company_id, 'Sin empresa'), 'store_name': stores.get(channel_map.get(r.conversation_id).store_id, 'Tienda sin identificar') if channel_map.get(r.conversation_id) else 'Tienda sin identificar', 'conversation_id': r.conversation_id, 'wa_user_id': r.wa_user_id, 'body': r.body, 'status': r.status, 'authorized_support_contact': r.is_known_contact, 'known_contact': r.is_known_contact, 'is_group': r.is_group, 'created_at': r.created_at} for r in rows]


@router.patch('/help-requests/{request_id}')
def update_help_request(request_id: int, data: HelpRequestStatus, user: User = Depends(require_case_closer), db: Session = Depends(get_db)):
    row = db.get(HelpRequest, request_id)
    if not row: raise HTTPException(status_code=404, detail='Solicitud no encontrada')
    previous = row.status; row.status = data.status
    company = db.get(Company, row.company_id) if row.company_id else None
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == row.conversation_id).first() if row.conversation_id else None
    store = db.get(Store, channel.store_id) if channel and channel.store_id else None
    conversation = db.get(Conversation, row.conversation_id) if row.conversation_id else None
    db.add(AuditLog(username=user.username, action='actualizar_solicitud_ayuda', entity='help_request', entity_id=str(row.id), details={'status_before': previous, 'status_after': row.status, 'wa_user_id': row.wa_user_id}))
    if data.status in ('resolved', 'ignored') and previous not in ('resolved', 'ignored'):
        if conversation:
            tree = company.decision_tree or {} if company else {}; conversation.status = 'open'; conversation.state = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
            db.add(AuditLog(username=user.username, action='chatbot_resumed', entity='conversation', entity_id=str(conversation.id), details={'help_request_id': row.id, 'status': data.status}))
        success = data.status == 'resolved'; store_name = store.name if store else 'Tienda sin identificar'; company_name = company.name if company else 'Empresa sin identificar'; outcome = 'atendido con éxito' if success else 'cerrado sin atención exitosa'
        for audience in ('admin', 'reader'):
            emit_notification(db, audience=audience, event_type='help_request_closed', title=f'Caso cerrado - {store_name}', body=f'Solicitud #{row.id} de {company_name}: {outcome}.', event_key=f'help:{row.id}:{audience}:closed:{data.status}', details={'help_request_id': row.id, 'company': company_name, 'store': store_name, 'success': success, 'status': data.status})
    db.commit()
    return {'status': 'ok', 'id': row.id, 'request_status': row.status, 'chatbot_resumed': data.status in ('resolved', 'ignored')}


@router.post('/support/escalations/run')
def run_escalations(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return process_help_escalations(db)


@router.post('/audit/ui-events')
def audit_ui_event(event: UIAuditEvent, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(AuditLog(username=user.username, action=event.action, entity='ui', details={'element_id': event.element_id, 'label': event.label, 'path': event.path})); db.commit()
    return {'status': 'ok'}


@router.get('/audit/activity/users')
def audit_activity_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    hidden = _hidden_admin_username()
    query = db.query(AuditLog.username).filter(AuditLog.username.isnot(None))
    if hidden: query = query.filter(AuditLog.username != hidden)
    rows = query.distinct().order_by(AuditLog.username.asc()).all()
    return [row[0] for row in rows if row[0]]


@router.get('/audit/activity')
def audit_activity(username: str | None = Query(default=None), limit: int = Query(default=200, ge=1, le=500), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    hidden = _hidden_admin_username(); query = db.query(AuditLog)
    if hidden: query = query.filter((AuditLog.username.is_(None)) | (AuditLog.username != hidden))
    if username: query = query.filter(AuditLog.username == username)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{'id': row.id, 'username': row.username, 'action': row.action, 'entity': row.entity, 'entity_id': row.entity_id, 'details': row.details or {}, 'created_at': row.created_at} for row in rows]


@router.delete('/audit/activity/{log_id}')
def delete_audit_activity(log_id: int, _: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    row = db.get(AuditLog, log_id)
    if not row: raise HTTPException(status_code=404, detail='Registro no encontrado')
    db.delete(row); db.commit()
    return {'status': 'ok', 'deleted_id': log_id}


@router.delete('/audit/activity')
def clear_audit_activity(username: str | None = Query(default=None), _: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    hidden = _hidden_admin_username(); query = db.query(AuditLog)
    if hidden: query = query.filter((AuditLog.username.is_(None)) | (AuditLog.username != hidden))
    if username: query = query.filter(AuditLog.username == username)
    deleted = query.delete(synchronize_session=False); db.commit()
    return {'status': 'ok', 'deleted': deleted, 'username': username}