import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Company, Conversation, Store, SupportEmailRecipient, SupportTicket
from .ticketing import ticket_code


def _recipients(db: Session, company_id: int) -> list[str]:
    rows = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company_id,
        SupportEmailRecipient.is_active.is_(True),
    ).all()
    return sorted({str(row.email or '').strip() for row in rows if str(row.email or '').strip()})


def send_evidence_email(
    db: Session,
    *,
    ticket: SupportTicket,
    filename: str,
    content_type: str,
    data: bytes,
) -> tuple[bool, str]:
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    conversation = db.get(Conversation, ticket.conversation_id)
    if not company:
        return False, 'empresa_no_encontrada'
    recipients = _recipients(db, company.id)
    if not recipients:
        return False, 'sin_destinatarios'
    sender = (settings.smtp_from_email or settings.smtp_username or '').strip()
    if not settings.smtp_host or not sender:
        return False, 'smtp_no_configurado'

    problem = ' '.join(str(ticket.subject or '').split()).strip()
    if not problem or problem.lower() in {'incidencia', 'incidencia de soporte', 'soporte', 'reporte'}:
        problem = ' '.join(str(ticket.description or '').split()).strip() or 'Falla reportada sin detalle'
    code = ticket_code(ticket, company, store)
    store_name = store.name if store else 'Tienda sin identificar'
    contact = conversation.wa_user_id if conversation else 'Sin contacto'

    msg = EmailMessage()
    msg['Subject'] = f'[{code}] Evidencia recibida - {problem[:80]}'
    msg['From'] = formataddr((settings.smtp_from_name, sender))
    msg['To'] = ', '.join(recipients)
    msg.set_content(
        f'Ticket: {code}\n'
        f'Empresa: {company.name}\n'
        f'Tienda: {store_name}\n'
        f'Contacto: {contact}\n'
        f'Falla reportada: {problem}\n'
        'Foto recibida: se adjunta la evidencia capturada desde WhatsApp.\n'
    )
    maintype, _, subtype = (content_type or 'application/octet-stream').partition('/')
    if not subtype:
        maintype, subtype = 'application', 'octet-stream'
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename or 'evidencia.jpg')

    try:
        smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True, 'sent'
    except Exception as exc:
        return False, str(exc)[:500]
