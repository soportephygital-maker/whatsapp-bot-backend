from ..models import SupportTicket
from ..services import ticketing
from ..services.case_event_notifications import create_learning_candidate, human_was_required, send_case_event_email
from . import local_bridge, ticketed_case_close, ticketed_local_bridge


_original_send_email = ticketing._send_email
_original_help_request = local_bridge._ensure_help_request
_original_close_ticket = ticketing.close_ticket


def _policy_send_email(subject: str, body: str, recipients: list[str], html_body: str | None = None):
    """Suppress legacy opening/closing emails; milestone emails own those events now."""
    normalized = str(subject or '').lower()
    if 'nueva incidencia' in normalized or 'caso cerrado' in normalized:
        return True, 'suppressed_by_milestone_policy'
    return _original_send_email(subject, body, recipients, html_body=html_body)


def _policy_help_request(db, *, conversation, company, store, local_user_id, body, reason):
    existing = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    request = _original_help_request(
        db,
        conversation=conversation,
        company=company,
        store=store,
        local_user_id=local_user_id,
        body=body,
        reason=reason,
    )
    ticket = existing or db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    if ticket:
        already = db.query(ticketing.AuditLog).filter(
            ticketing.AuditLog.entity == 'support_ticket',
            ticketing.AuditLog.entity_id == str(ticket.id),
            ticketing.AuditLog.action == 'case_event_email_sent',
        ).all()
        sent_human = any((row.details or {}).get('event') == 'human_required' for row in already)
        if not sent_human:
            send_case_event_email(db, ticket=ticket, event='human_required')
    return request


def _policy_close_ticket(db, *, conversation, username: str, result: str):
    before = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first() if conversation else None
    was_closed = bool(before and before.status == 'closed')
    ticket = _original_close_ticket(db, conversation=conversation, username=username, result=result)
    if not ticket or was_closed:
        return ticket
    normalized = str(result or '').strip().lower()
    success = normalized in {'resolved', 'resuelto', 'success', 'successful', 'ok', 'cerrado', 'solved'} or 'resuelt' in normalized or 'exito' in normalized or 'éxito' in normalized
    if success:
        event = 'resolved_success'
    elif not human_was_required(db, ticket):
        event = 'closed_no_human'
    else:
        event = 'status_changed'
    send_case_event_email(db, ticket=ticket, event=event)
    create_learning_candidate(db, ticket)
    return ticket


ticketing._send_email = _policy_send_email
local_bridge._ensure_help_request = _policy_help_request
ticketing.close_ticket = _policy_close_ticket
# These modules imported close_ticket directly, so update their bound references too.
ticketed_local_bridge.close_ticket = _policy_close_ticket
ticketed_case_close.close_ticket = _policy_close_ticket
