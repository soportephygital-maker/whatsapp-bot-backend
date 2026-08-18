from datetime import datetime
from sqlalchemy.orm import Session
from ..config import settings
from ..models import AuditLog, Company, ConversationChannel, HelpRequest, Store, SupportContact
from .notifications import emit_notification
from .whatsapp import send_text_message

INITIAL_HUMAN_WAIT_MINUTES = 5


def _elapsed_minutes(created_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    return max(0.0, (now - created_at).total_seconds() / 60.0)


def _last_stage_log(db: Session, request_id: int, action: str) -> AuditLog | None:
    return db.query(AuditLog).filter(
        AuditLog.entity == 'help_request',
        AuditLog.entity_id == str(request_id),
        AuditLog.action == action,
    ).order_by(AuditLog.created_at.desc()).first()


def _sender_context(db: Session, request: HelpRequest):
    channel = None
    if request.conversation_id:
        channel = db.query(ConversationChannel).filter(
            ConversationChannel.conversation_id == request.conversation_id
        ).first()
    store = db.get(Store, channel.store_id) if channel and channel.store_id else None
    if not store and request.company_id:
        store = db.query(Store).filter(
            Store.company_id == request.company_id,
            Store.whatsapp_phone_number_id.isnot(None),
        ).order_by(Store.id.asc()).first()
    return store, (channel.phone_number_id if channel and channel.phone_number_id else (store.whatsapp_phone_number_id if store else None))


def _support_message(company: Company, store: Store | None, request: HelpRequest, stage: str) -> str:
    store_name = store.name if store else 'Tienda sin identificar'
    return (
        f'Phygital Bot - solicitud de ayuda ({stage})\n'
        f'Empresa: {company.name}\n'
        f'Tienda: {store_name}\n'
        f'Cliente WhatsApp: {request.wa_user_id}\n'
        f'Mensaje: {request.body[:1200]}\n'
        f'Solicitud #{request.id}'
    )


def _notify_contact(db: Session, request: HelpRequest, company: Company, store: Store | None, sender_id: str | None, contact: SupportContact, action: str, stage: str) -> bool:
    try:
        result = send_text_message(
            contact.phone,
            _support_message(company, store, request, stage),
            phone_number_id=sender_id,
            db=db,
        )
    except Exception as exc:
        db.add(AuditLog(
            action='support_notification_error',
            entity='help_request',
            entity_id=str(request.id),
            details={'support_id': contact.id, 'role': contact.role, 'error': str(exc)},
        ))
        return False
    if not result.get('sent'):
        db.add(AuditLog(
            action='support_notification_blocked',
            entity='help_request',
            entity_id=str(request.id),
            details={'support_id': contact.id, 'role': contact.role, 'reason': result.get('reason')},
        ))
        return False
    db.add(AuditLog(
        action=action,
        entity='help_request',
        entity_id=str(request.id),
        details={'support_id': contact.id, 'support_name': contact.name, 'support_phone': contact.phone, 'role': contact.role},
    ))
    return True


def process_help_escalations(db: Session) -> dict:
    requests = db.query(HelpRequest).filter(HelpRequest.status == 'new').order_by(HelpRequest.created_at.asc()).all()
    now = datetime.utcnow()
    sent = 0
    blocked = 0
    app_events = 0

    for request in requests:
        company = db.get(Company, request.company_id) if request.company_id else None
        if not company:
            continue
        store, sender_id = _sender_context(db, request)
        store_name = store.name if store else 'Tienda sin identificar'

        primary = db.query(SupportContact).filter(
            SupportContact.company_id == company.id,
            SupportContact.role == 'primary',
            SupportContact.is_active.is_(True),
        ).order_by(SupportContact.priority.asc()).first()
        secondary = db.query(SupportContact).filter(
            SupportContact.company_id == company.id,
            SupportContact.role == 'secondary',
            SupportContact.is_active.is_(True),
        ).order_by(SupportContact.priority.asc()).first()

        primary_log = _last_stage_log(db, request.id, 'support_primary_notified')
        secondary_log = _last_stage_log(db, request.id, 'support_secondary_notified')
        all_log = _last_stage_log(db, request.id, 'support_all_app_notified')

        if not primary_log:
            if _elapsed_minutes(request.created_at, now) < INITIAL_HUMAN_WAIT_MINUTES:
                continue
            if emit_notification(
                db,
                audience='operator',
                event_type='escalation_started',
                title=f'Escalamiento iniciado - {store_name}',
                body=f'La solicitud #{request.id} de {company.name} lleva 5 minutos sin respuesta humana.',
                event_key=f'help:{request.id}:operator:escalation_started',
                details={'help_request_id': request.id, 'company': company.name, 'store': store_name},
            ):
                app_events += 1
            if primary:
                ok = _notify_contact(db, request, company, store, sender_id, primary, 'support_primary_notified', 'primario')
                if ok:
                    sent += 1
                else:
                    blocked += 1
            else:
                db.add(AuditLog(action='support_primary_missing', entity='help_request', entity_id=str(request.id), details={'company': company.company_key}))
                primary_log = AuditLog(created_at=now)
            db.flush()
            primary_log = _last_stage_log(db, request.id, 'support_primary_notified') or primary_log

        if request.status != 'new':
            continue

        if primary_log and not secondary_log:
            wait_primary = max(1, primary.escalation_after_minutes if primary else INITIAL_HUMAN_WAIT_MINUTES)
            if _elapsed_minutes(primary_log.created_at, now) < wait_primary:
                continue
            if secondary:
                ok = _notify_contact(db, request, company, store, sender_id, secondary, 'support_secondary_notified', 'secundario')
                if ok:
                    sent += 1
                else:
                    blocked += 1
                db.flush()
                secondary_log = _last_stage_log(db, request.id, 'support_secondary_notified')
            else:
                db.add(AuditLog(action='support_secondary_missing', entity='help_request', entity_id=str(request.id), details={'company': company.company_key}))
                secondary_log = AuditLog(created_at=now)

        if request.status != 'new':
            continue

        if secondary_log and not all_log:
            wait_secondary = max(1, secondary.escalation_after_minutes if secondary else INITIAL_HUMAN_WAIT_MINUTES)
            if _elapsed_minutes(secondary_log.created_at, now) < wait_secondary:
                continue
            if emit_notification(
                db,
                audience='all',
                event_type='support_broadcast',
                title=f'Solicitud de apoyo - {store_name}',
                body=f'Primario y secundario no atendieron la solicitud #{request.id} de {company.name}. Se requiere apoyo.',
                event_key=f'help:{request.id}:all:support_broadcast',
                details={'help_request_id': request.id, 'company': company.name, 'store': store_name},
            ):
                app_events += 1
            db.add(AuditLog(action='support_all_app_notified', entity='help_request', entity_id=str(request.id), details={'company': company.company_key, 'store': store_name}))

    db.commit()
    return {'processed': len(requests), 'sent': sent, 'blocked': blocked, 'app_events': app_events, 'initial_wait_minutes': INITIAL_HUMAN_WAIT_MINUTES}
