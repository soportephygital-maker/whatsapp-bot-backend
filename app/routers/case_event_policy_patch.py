from ..models import Company, Conversation, Store, SupportTicket
from ..services import ticketing
from ..services.ai_learning import customer_suggestion
from ..services.case_event_notifications import create_learning_candidate, human_was_required, send_case_event_email
from . import local_bridge, ticketed_case_close, ticketed_local_bridge


_original_send_email = ticketing._send_email
_original_help_request = local_bridge._ensure_help_request
_original_close_ticket = ticketing.close_ticket
_original_ticketed_inbound = ticketed_local_bridge.ticketed_local_inbound


def _policy_send_email(subject: str, body: str, recipients: list[str], html_body: str | None = None):
    """Suppress legacy opening/closing emails; milestone emails own those events now."""
    normalized = str(subject or '').lower()
    if 'nueva incidencia' in normalized or 'caso cerrado' in normalized:
        return True, 'suppressed_by_milestone_policy'
    return _original_send_email(subject, body, recipients, html_body=html_body)


def _policy_help_request(db, *, conversation, company, store, local_user_id, body, reason):
    request = _original_help_request(
        db,
        conversation=conversation,
        company=company,
        store=store,
        local_user_id=local_user_id,
        body=body,
        reason=reason,
    )
    ticket = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    if not ticket:
        # Human escalation itself is a reportable case. Creating it here does not
        # send the old opening email because the milestone policy suppresses it.
        ticket = ticketing.ensure_ticket(
            db,
            company=company,
            store=store,
            conversation=conversation,
            description=str(body or 'Solicitud de atención humana'),
        )
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


def _ai_guided_ticketed_inbound(data, operator, db):
    """Use only admin-approved learning points as an optional no-match fallback."""
    result = _original_ticketed_inbound(data=data, operator=operator, db=db)
    if not isinstance(result, dict):
        return result
    if result.get('status') != 'ok' or result.get('chatbot_paused'):
        return result
    if result.get('action') not in {'no_match_first', 'no_match_repeat'}:
        return result
    company_key = result.get('company_key')
    if not company_key:
        return result
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        return result
    suggestion = customer_suggestion(db, company_id=company.id, question=data.text)
    if not suggestion:
        return result
    conversation = db.get(Conversation, result.get('conversation_id')) if result.get('conversation_id') else None
    if not conversation:
        return result
    store = ticketed_local_bridge._selected_context_store(data, db, company.id)
    if not store:
        rows = ticketed_local_bridge._selected_company_stores(data, company.id, db)
        store = rows[0] if len(rows) == 1 else None
    if store:
        ticketed_local_bridge._set_reply(db, result, suggestion, data, conversation=conversation, company=company, store=store)
        result['action'] = 'ai_approved_knowledge'
    return result


ticketing._send_email = _policy_send_email
local_bridge._ensure_help_request = _policy_help_request
ticketing.close_ticket = _policy_close_ticket
# These modules imported close_ticket directly, so update their bound references too.
ticketed_local_bridge.close_ticket = _policy_close_ticket
ticketed_case_close.close_ticket = _policy_close_ticket
# Global entry calls this module function dynamically, so approved AI learning can
# answer only when the normal tree has no match and human support is not active.
ticketed_local_bridge.ticketed_local_inbound = _ai_guided_ticketed_inbound
