from datetime import datetime
from sqlalchemy.orm import Session
from ..config import settings
from ..models import AuditLog, Company, HelpRequest, Store, SupportContact
from .whatsapp import send_text_message


def _elapsed_minutes(created_at: datetime) -> float:
    now = datetime.utcnow()
    return max(0.0, (now - created_at).total_seconds() / 60.0)


def process_help_escalations(db: Session) -> dict:
    if not settings.whatsapp_send_enabled:
        return {'processed': 0, 'sent': 0, 'blocked': 0, 'reason': 'WHATSAPP_SEND_ENABLED=false'}

    requests = db.query(HelpRequest).filter(HelpRequest.status == 'new').order_by(HelpRequest.created_at.asc()).all()
    sent = 0
    blocked = 0

    for request in requests:
        company = db.get(Company, request.company_id) if request.company_id else None
        if not company:
            continue

        sender_store = db.query(Store).filter(
            Store.company_id == company.id,
            Store.whatsapp_phone_number_id.isnot(None),
        ).order_by(Store.id.asc()).first()
        sender_id = sender_store.whatsapp_phone_number_id if sender_store else None

        contacts = db.query(SupportContact).filter(
            SupportContact.company_id == company.id,
            SupportContact.is_active.is_(True),
        ).order_by(SupportContact.role.asc(), SupportContact.priority.asc()).all()
        if not contacts:
            continue

        existing_logs = db.query(AuditLog).filter(
            AuditLog.entity == 'help_request',
            AuditLog.entity_id == str(request.id),
            AuditLog.action.in_(['support_primary_notified', 'support_secondary_notified']),
        ).all()
        already_notified = {
            (row.action, str((row.details or {}).get('support_id')))
            for row in existing_logs
        }
        elapsed = _elapsed_minutes(request.created_at)

        for contact in contacts:
            action = 'support_primary_notified' if contact.role == 'primary' else 'support_secondary_notified'
            if (action, str(contact.id)) in already_notified:
                continue
            if contact.role == 'secondary' and elapsed < contact.escalation_after_minutes:
                continue

            stage = 'primario' if contact.role == 'primary' else 'secundario'
            text = (
                f'Phygital Bot - solicitud de ayuda ({stage})\n'
                f'Empresa: {company.name}\n'
                f'Contacto WhatsApp: {request.wa_user_id}\n'
                f'Mensaje: {request.body[:1200]}\n'
                f'Solicitud #{request.id}'
            )
            try:
                result = send_text_message(contact.phone, text, phone_number_id=sender_id)
            except Exception as exc:
                db.add(AuditLog(
                    action='support_notification_error',
                    entity='help_request',
                    entity_id=str(request.id),
                    details={'support_id': contact.id, 'role': contact.role, 'error': str(exc)},
                ))
                continue

            if result.get('sent'):
                db.add(AuditLog(
                    action=action,
                    entity='help_request',
                    entity_id=str(request.id),
                    details={
                        'support_id': contact.id,
                        'support_name': contact.name,
                        'support_phone': contact.phone,
                        'role': contact.role,
                        'elapsed_minutes': round(elapsed, 1),
                    },
                ))
                sent += 1
            else:
                blocked += 1

    db.commit()
    return {'processed': len(requests), 'sent': sent, 'blocked': blocked}
