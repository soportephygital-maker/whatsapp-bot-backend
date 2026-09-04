import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, Company, Conversation, HelpRequest, Store, SupportTicket
from .case_reports import build_chat_pdf, build_summary_pdf
from .ticketing import ticket_code


def _recipients(db: Session, company_id: int) -> list[str]:
    from ..models import SupportEmailRecipient
    rows = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company_id,
        SupportEmailRecipient.is_active.is_(True),
    ).all()
    return sorted({str(row.email).strip() for row in rows if str(row.email or '').strip()})


def _smtp_ready() -> tuple[bool, str]:
    sender = (settings.smtp_from_email or settings.smtp_username or '').strip()
    if not settings.smtp_host:
        return False, 'SMTP_HOST faltante'
    if not sender:
        return False, 'SMTP_FROM_EMAIL/SMTP_USERNAME faltante'
    if settings.smtp_username and not settings.smtp_password:
        return False, 'SMTP_PASSWORD faltante'
    return True, sender


def _subject(event: str, code: str, company: Company, store: Store | None) -> str:
    store_name = store.name if store else 'Tienda sin identificar'
    labels = {
        'human_required': 'Requiere atención humana',
        'status_changed': 'Cambio de estado',
        'closed_no_human': 'Caso cerrado sin atención humana',
        'resolved_success': 'Caso concluido con éxito',
    }
    return f'[{code}] {labels.get(event, event)} - {company.name} / {store_name}'


def _plain_body(event: str, ticket: SupportTicket, company: Company, store: Store | None, conversation: Conversation) -> str:
    code = ticket_code(ticket, company, store)
    store_name = store.name if store else 'Tienda sin identificar'
    labels = {
        'human_required': 'REQUIERE ATENCIÓN HUMANA',
        'status_changed': 'CAMBIO DE ESTADO',
        'closed_no_human': 'CERRADO SIN ATENCIÓN HUMANA',
        'resolved_success': 'CONCLUIDO CON ÉXITO',
    }
    return (
        f'Ticket: {code}\nEvento: {labels.get(event, event)}\nEmpresa: {company.name}\n'
        f'Tienda: {store_name}\nContacto: {conversation.wa_user_id}\n'
        f'Problema: {ticket.description}\nResultado: {ticket.close_result or "Pendiente"}\n'
        'Se adjuntan el expediente completo de la conversación y el resumen ejecutivo del caso.\n'
    )


def _html_body(event: str, ticket: SupportTicket, company: Company, store: Store | None, conversation: Conversation) -> str:
    from html import escape
    code = escape(ticket_code(ticket, company, store))
    store_name = escape(store.name if store else 'Tienda sin identificar')
    labels = {
        'human_required': ('Requiere atención humana', '#fee2e2', '#991b1b'),
        'status_changed': ('Cambio de estado', '#dbeafe', '#1d4ed8'),
        'closed_no_human': ('Cerrado', '#dcfce7', '#166534'),
        'resolved_success': ('Resuelto con éxito', '#dcfce7', '#166534'),
    }
    label, bg, fg = labels.get(event, (event, '#f3f4f6', '#374151'))
    return f'''<!doctype html><html><body style="margin:0;padding:24px;background:#f6f7f9;font-family:Arial,Helvetica,sans-serif;color:#202124;">
<table role="presentation" width="100%"><tr><td align="center"><table role="presentation" width="100%" style="max-width:560px;background:#fff;border:1px solid #e5e7eb;border-radius:16px;"><tr><td style="padding:28px;">
<table role="presentation" width="100%"><tr><td><div style="font-size:14px;color:#6b7280">Ticket de soporte</div><div style="font-size:18px;font-weight:700">{code}</div></td><td align="right"><span style="display:inline-block;background:{bg};color:{fg};padding:7px 14px;border-radius:999px;font-weight:600">{escape(label)}</span></td></tr></table>
<div style="height:1px;background:#e5e7eb;margin:20px 0"></div>
<table role="presentation" width="100%"><tr><td style="padding:7px 0;color:#6b7280">Empresa</td><td align="right"><b>{escape(company.name)}</b></td></tr><tr><td style="padding:7px 0;color:#6b7280">Tienda</td><td align="right"><b>{store_name}</b></td></tr><tr><td style="padding:7px 0;color:#6b7280">Contacto</td><td align="right"><b>{escape(conversation.wa_user_id)}</b></td></tr></table>
<div style="height:1px;background:#e5e7eb;margin:20px 0"></div><div style="font-size:14px;color:#6b7280;margin-bottom:7px">Problema</div><div style="font-size:16px;line-height:1.5">{escape(ticket.description or 'Sin descripción').replace(chr(10), '<br>')}</div>
<div style="margin-top:20px;background:#f7f7f7;padding:13px 15px;border-radius:12px;color:#6b7280;font-size:14px">Se adjuntan el expediente completo y el resumen ejecutivo del caso.</div>
</td></tr></table></td></tr></table></body></html>'''


def send_case_event_email(db: Session, *, ticket: SupportTicket, event: str) -> bool:
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    conversation = db.get(Conversation, ticket.conversation_id)
    if not company or not conversation:
        return False
    recipients = _recipients(db, company.id)
    ready, sender_or_error = _smtp_ready()
    if not recipients or not ready:
        db.add(AuditLog(action='case_event_email_not_sent', entity='support_ticket', entity_id=str(ticket.id), details={'event': event, 'result': 'sin_destinatarios' if not recipients else sender_or_error}))
        return False
    code = ticket_code(ticket, company, store)
    chat_pdf = build_chat_pdf(db, ticket=ticket, company=company, store=store, conversation=conversation, code=code)
    summary_pdf = build_summary_pdf(db, ticket=ticket, company=company, store=store, conversation=conversation, code=code)
    msg = EmailMessage()
    msg['Subject'] = _subject(event, code, company, store)
    msg['From'] = formataddr((settings.smtp_from_name, sender_or_error))
    msg['To'] = ', '.join(recipients)
    msg.set_content(_plain_body(event, ticket, company, store, conversation))
    msg.add_alternative(_html_body(event, ticket, company, store, conversation), subtype='html')
    msg.add_attachment(chat_pdf, maintype='application', subtype='pdf', filename=f'{code}-chat-completo.pdf')
    msg.add_attachment(summary_pdf, maintype='application', subtype='pdf', filename=f'{code}-resumen.pdf')
    try:
        smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        db.add(AuditLog(action='case_event_email_sent', entity='support_ticket', entity_id=str(ticket.id), details={'event': event, 'recipients': recipients}))
        return True
    except Exception as exc:
        db.add(AuditLog(action='case_event_email_not_sent', entity='support_ticket', entity_id=str(ticket.id), details={'event': event, 'result': str(exc)[:500]}))
        return False


def human_was_required(db: Session, ticket: SupportTicket) -> bool:
    return db.query(HelpRequest.id).filter(HelpRequest.conversation_id == ticket.conversation_id).first() is not None


def create_learning_candidate(db: Session, ticket: SupportTicket) -> None:
    from ..models import AILearningPoint
    if ticket.status != 'closed':
        return
    existing = db.query(AILearningPoint).filter(AILearningPoint.ticket_id == ticket.id).first()
    if existing:
        return
    solution = ticket.close_result or ''
    row = AILearningPoint(company_id=ticket.company_id, ticket_id=ticket.id, problem=ticket.description or '', solution=solution, confidence=40 if solution else 20, status='pending')
    db.add(row)
