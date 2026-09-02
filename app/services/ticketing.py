import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, Company, Conversation, Store, SupportEmailRecipient, SupportTicket
from .notifications import emit_notification


def _company_ticket_code(company: Company | None) -> str:
    if not company:
        return 'EDM'
    text = f'{company.company_key} {company.name}'.lower()
    if 'coppel' in text or 'cpp' in text:
        return 'CPP'
    if 'iqos' in text or 'pmi' in text or 'philip morris' in text:
        return 'PMI'
    clean = re.sub(r'[^A-Z0-9]', '', (company.company_key or company.name or 'EDM').upper())
    return (clean[:3] or 'EDM')


def _store_ticket_code(store: Store | None) -> str:
    if not store:
        return 'SIN-TIENDA'
    digits = re.findall(r'\d+', store.name or '')
    if digits:
        return digits[0]
    clean = re.sub(r'[^A-Z0-9]', '-', (store.name or '').upper()).strip('-')
    clean = re.sub(r'-+', '-', clean)
    return clean[:18] or 'SIN-TIENDA'


def ticket_code(ticket: SupportTicket, company: Company | None = None, store: Store | None = None) -> str:
    opened = ticket.opened_at or datetime.utcnow()
    return f'EDM-{_company_ticket_code(company)}-{opened:%Y%m%d}-{_store_ticket_code(store)}-{ticket.id:06d}'


def _ticket_code(ticket: SupportTicket, company: Company | None = None, store: Store | None = None) -> str:
    return ticket_code(ticket, company, store)


def ticket_tracking(db: Session, ticket: SupportTicket) -> dict:
    rows = db.query(AuditLog).filter(
        AuditLog.entity == 'support_ticket',
        AuditLog.entity_id == str(ticket.id),
        AuditLog.action == 'ticket_followup',
    ).order_by(AuditLog.id.desc()).limit(1).all()
    latest = rows[0] if rows else None
    details = latest.details if latest and isinstance(latest.details, dict) else {}
    if ticket.status == 'closed':
        default_status = 'Cerrado'
        default_message = 'La atención de este ticket fue cerrada. Si el problema continúa, indícalo para retomar la revisión.'
    else:
        default_status = 'En atención'
        default_message = 'Tu caso está siendo atendido por nuestro equipo. Puedes consultar este ticket nuevamente para conocer cualquier actualización.'
    return {
        'status_label': str(details.get('status_label') or default_status),
        'message': str(details.get('message') or default_message),
        'updated_at': latest.created_at if latest else (ticket.closed_at or ticket.opened_at),
        'updated_by': latest.username if latest else None,
    }


def add_ticket_followup(db: Session, *, ticket: SupportTicket, username: str, message: str, status_label: str = 'En atención') -> AuditLog:
    row = AuditLog(
        username=username,
        action='ticket_followup',
        entity='support_ticket',
        entity_id=str(ticket.id),
        details={
            'status_label': (status_label or 'En atención')[:80],
            'message': message.strip()[:2000],
        },
    )
    db.add(row)
    return row


def _smtp_ready() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def _send_email(subject: str, body: str, recipients: list[str]) -> tuple[bool, str]:
    recipients = sorted({str(x).strip() for x in recipients if str(x).strip()})
    if not recipients:
        return False, 'sin_destinatarios'
    if not _smtp_ready():
        return False, 'smtp_no_configurado'
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)
    try:
        smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True, 'sent'
    except Exception as exc:
        return False, str(exc)[:500]


def _recipient_emails(db: Session, company_id: int) -> list[str]:
    rows = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company_id,
        SupportEmailRecipient.is_active.is_(True),
    ).all()
    return [row.email for row in rows]


def _ticket_message(ticket: SupportTicket, company: Company, store: Store | None, conversation: Conversation, event: str) -> tuple[str, str]:
    code = ticket_code(ticket, company, store)
    store_name = store.name if store else 'Tienda sin identificar'
    if event == 'closed':
        subject = f'[{code}] Caso cerrado - {company.name} / {store_name}'
        body = (
            f'Ticket: {code}\nEstado: CERRADO\nEmpresa: {company.name}\nTienda: {store_name}\n'
            f'Contacto: {conversation.wa_user_id}\nResultado: {ticket.close_result or "cerrado"}\n'
            f'Cerrado por: {ticket.closed_by or "sistema"}\nDescripción: {ticket.description}\n'
        )
    else:
        subject = f'[{code}] Nueva incidencia - {company.name} / {store_name}'
        body = (
            f'Ticket: {code}\nEstado: ABIERTO\nEmpresa: {company.name}\nTienda: {store_name}\n'
            f'Contacto: {conversation.wa_user_id}\nDescripción inicial: {ticket.description}\n'
            'El caso puede revisarse desde el dashboard de Phygital Bot.\n'
        )
    return subject, body


def notify_ticket(db: Session, ticket: SupportTicket, company: Company, store: Store | None, conversation: Conversation, event: str) -> None:
    code = ticket_code(ticket, company, store)
    store_name = store.name if store else 'Tienda sin identificar'
    if event == 'closed':
        title = f'{code} cerrado - {store_name}'
        body = f'{company.name}: caso cerrado ({ticket.close_result or "cerrado"}).'
        event_type = 'ticket_closed'
    else:
        title = f'{code} abierto - {store_name}'
        body = f'{company.name}: nueva incidencia identificada.'
        event_type = 'ticket_opened'
    details = {
        'ticket_id': ticket.id,
        'ticket_code': code,
        'company_id': company.id,
        'company': company.name,
        'store_id': store.id if store else None,
        'store': store_name,
        'conversation_id': conversation.id,
        'status': ticket.status,
    }
    for audience in ('admin', 'operator', 'reader'):
        emit_notification(
            db,
            audience=audience,
            event_type=event_type,
            title=title,
            body=body,
            event_key=f'ticket:{ticket.id}:{audience}:{event}:{ticket.opened_at.isoformat() if ticket.opened_at else "0"}',
            details=details,
        )
    subject, email_body = _ticket_message(ticket, company, store, conversation, event)
    sent, result = _send_email(subject, email_body, _recipient_emails(db, company.id))
    db.add(AuditLog(
        action='ticket_email_sent' if sent else 'ticket_email_not_sent',
        entity='support_ticket',
        entity_id=str(ticket.id),
        details={'event': event, 'result': result, 'company': company.company_key},
    ))


def ensure_ticket(db: Session, *, company: Company, store: Store | None, conversation: Conversation, description: str) -> SupportTicket:
    ticket = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    if ticket:
        if ticket.status == 'closed':
            ticket.status = 'open'
            ticket.opened_at = datetime.utcnow()
            ticket.closed_at = None
            ticket.closed_by = None
            ticket.close_result = None
            ticket.description = description[:4000]
            notify_ticket(db, ticket, company, store, conversation, 'opened')
        if store and ticket.store_id != store.id:
            ticket.store_id = store.id
        return ticket
    ticket = SupportTicket(
        company_id=company.id,
        store_id=store.id if store else None,
        conversation_id=conversation.id,
        status='open',
        subject='Incidencia de soporte',
        description=description[:4000],
    )
    db.add(ticket)
    db.flush()
    db.add(AuditLog(action='ticket_opened', entity='support_ticket', entity_id=str(ticket.id), details={
        'company': company.company_key,
        'store': store.name if store else None,
        'conversation_id': conversation.id,
    }))
    notify_ticket(db, ticket, company, store, conversation, 'opened')
    return ticket


def close_ticket(db: Session, *, conversation: Conversation, username: str, result: str) -> SupportTicket | None:
    ticket = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    if not ticket or ticket.status == 'closed':
        return ticket
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    ticket.status = 'closed'
    ticket.closed_at = datetime.utcnow()
    ticket.closed_by = username
    ticket.close_result = result
    db.add(AuditLog(username=username, action='ticket_closed', entity='support_ticket', entity_id=str(ticket.id), details={'result': result}))
    if company:
        notify_ticket(db, ticket, company, store, conversation, 'closed')
    return ticket


def ticket_dict(ticket: SupportTicket, company: Company | None, store: Store | None, db: Session | None = None) -> dict:
    data = {
        'id': ticket.id,
        'code': ticket_code(ticket, company, store),
        'company_id': ticket.company_id,
        'company_name': company.name if company else 'Sin empresa',
        'store_id': ticket.store_id,
        'store_name': store.name if store else 'Tienda sin identificar',
        'conversation_id': ticket.conversation_id,
        'status': ticket.status,
        'subject': ticket.subject,
        'description': ticket.description,
        'opened_at': ticket.opened_at,
        'closed_at': ticket.closed_at,
        'closed_by': ticket.closed_by,
        'close_result': ticket.close_result,
    }
    if db is not None:
        data['tracking'] = ticket_tracking(db, ticket)
    return data
