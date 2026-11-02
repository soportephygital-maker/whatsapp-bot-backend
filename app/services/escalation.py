from datetime import datetime
from sqlalchemy.orm import Session
from ..models import AuditLog, Company, ConversationChannel, HelpRequest, Message, Store, SupportContact
from .notifications import emit_notification
from .whatsapp import send_text_message

INITIAL_HUMAN_WAIT_MINUTES = 5


def _elapsed_minutes(created_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    return max(0.0, (now - created_at).total_seconds() / 60.0)


def _last_stage_log(db: Session, request_id: int, action: str) -> AuditLog | None:
    return db.query(AuditLog).filter(AuditLog.entity == 'help_request', AuditLog.entity_id == str(request_id), AuditLog.action == action).order_by(AuditLog.created_at.desc()).first()


def _has_human_reply(db: Session, request: HelpRequest) -> bool:
    if not request.conversation_id:
        return False
    rows = db.query(Message).filter(Message.conversation_id == request.conversation_id, Message.direction == 'outbound', Message.created_at >= request.created_at).all()
    return any(bool((row.raw_payload or {}).get('manual')) for row in rows)


def _sender_context(db: Session, request: HelpRequest):
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == request.conversation_id).first() if request.conversation_id else None
    store = db.get(Store, channel.store_id) if channel and channel.store_id else None
    if not store and request.company_id:
        store = db.query(Store).filter(Store.company_id == request.company_id).order_by(Store.id.asc()).first()
    sender_id = channel.phone_number_id if channel and channel.phone_number_id else (store.whatsapp_phone_number_id if store else None)
    return store, sender_id


def _support_message(company: Company, store: Store | None, request: HelpRequest, stage: str) -> str:
    store_name = store.name if store else 'Tienda sin identificar'
    return f'Phygital Bot - solicitud de ayuda ({stage})\nEmpresa: {company.name}\nTienda: {store_name}\nCliente: {request.wa_user_id}\nMensaje: {request.body[:1200]}\nSolicitud #{request.id}'


def _attempt_contact(db: Session, request: HelpRequest, company: Company, store: Store | None, sender_id: str | None, contact: SupportContact | None, stage_key: str, stage_label: str) -> bool:
    attempt_action = f'support_{stage_key}_attempted'
    if _last_stage_log(db, request.id, attempt_action):
        return False
    details = {'company': company.company_key, 'stage': stage_key}
    if contact:
        details.update({'support_id': contact.id, 'support_name': contact.name, 'support_phone': contact.phone, 'role': contact.role})
    db.add(AuditLog(action=attempt_action, entity='help_request', entity_id=str(request.id), details=details))
    db.flush()
    if not contact:
        db.add(AuditLog(action=f'support_{stage_key}_missing', entity='help_request', entity_id=str(request.id), details={'company': company.company_key}))
        return False
    try:
        result = send_text_message(contact.phone, _support_message(company, store, request, stage_label), phone_number_id=sender_id, db=db)
    except Exception as exc:
        db.add(AuditLog(action='support_notification_error', entity='help_request', entity_id=str(request.id), details={'support_id': contact.id, 'role': contact.role, 'error': str(exc)}))
        return False
    if result.get('sent'):
        db.add(AuditLog(action=f'support_{stage_key}_notified', entity='help_request', entity_id=str(request.id), details={'support_id': contact.id, 'support_name': contact.name, 'support_phone': contact.phone, 'role': contact.role}))
        return True
    db.add(AuditLog(action='support_notification_blocked', entity='help_request', entity_id=str(request.id), details={'support_id': contact.id, 'role': contact.role, 'reason': result.get('reason') or result.get('error')}))
    return False


def process_help_escalations(db: Session) -> dict:
    requests = db.query(HelpRequest).filter(HelpRequest.status.in_(['new', 'reviewing'])).order_by(HelpRequest.created_at.asc()).all()
    now = datetime.utcnow()
    sent = blocked = app_events = 0
    for request in requests:
        if _has_human_reply(db, request):
            continue
        company = db.get(Company, request.company_id) if request.company_id else None
        if not company:
            continue
        store, sender_id = _sender_context(db, request)
        store_name = store.name if store else 'Tienda sin identificar'
        primary = db.query(SupportContact).filter(SupportContact.company_id == company.id, SupportContact.role == 'primary', SupportContact.is_active.is_(True)).order_by(SupportContact.priority.asc()).first()
        secondary = db.query(SupportContact).filter(SupportContact.company_id == company.id, SupportContact.role == 'secondary', SupportContact.is_active.is_(True)).order_by(SupportContact.priority.asc()).first()
        primary_attempt = _last_stage_log(db, request.id, 'support_primary_attempted')
        secondary_attempt = _last_stage_log(db, request.id, 'support_secondary_attempted')
        all_log = _last_stage_log(db, request.id, 'support_all_app_notified')

        if not primary_attempt:
            if _elapsed_minutes(request.created_at, now) < INITIAL_HUMAN_WAIT_MINUTES:
                continue
            if emit_notification(db, audience='operator', event_type='escalation_started', title=f'Escalamiento iniciado - {store_name}', body=f'La solicitud #{request.id} de {company.name} lleva 5 minutos sin respuesta humana.', event_key=f'help:{request.id}:operator:escalation_started', details={'help_request_id': request.id, 'company': company.name, 'store': store_name}):
                app_events += 1
            if _attempt_contact(db, request, company, store, sender_id, primary, 'primary', 'primario'):
                sent += 1
            else:
                blocked += 1
            db.flush()
            primary_attempt = _last_stage_log(db, request.id, 'support_primary_attempted')

        if _has_human_reply(db, request):
            continue
        if primary_attempt and not secondary_attempt:
            wait_primary = max(1, primary.escalation_after_minutes if primary else INITIAL_HUMAN_WAIT_MINUTES)
            if _elapsed_minutes(primary_attempt.created_at, now) < wait_primary:
                continue
            if _attempt_contact(db, request, company, store, sender_id, secondary, 'secondary', 'secundario'):
                sent += 1
            else:
                blocked += 1
            db.flush()
            secondary_attempt = _last_stage_log(db, request.id, 'support_secondary_attempted')

        if _has_human_reply(db, request):
            continue
        if secondary_attempt and not all_log:
            wait_secondary = max(1, secondary.escalation_after_minutes if secondary else INITIAL_HUMAN_WAIT_MINUTES)
            if _elapsed_minutes(secondary_attempt.created_at, now) < wait_secondary:
                continue
            if emit_notification(db, audience='all', event_type='support_broadcast', title=f'Solicitud de apoyo - {store_name}', body=f'Primario y secundario no atendieron la solicitud #{request.id} de {company.name}. Se requiere apoyo.', event_key=f'help:{request.id}:all:support_broadcast', details={'help_request_id': request.id, 'company': company.name, 'store': store_name}):
                app_events += 1
            db.add(AuditLog(action='support_all_app_notified', entity='help_request', entity_id=str(request.id), details={'company': company.company_key, 'store': store_name}))

    db.commit()
    return {'processed': len(requests), 'sent': sent, 'blocked': blocked, 'app_events': app_events, 'initial_wait_minutes': INITIAL_HUMAN_WAIT_MINUTES}
