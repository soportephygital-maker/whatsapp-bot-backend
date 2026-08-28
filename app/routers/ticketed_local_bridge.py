from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Company, Conversation, ConversationChannel, Message, Store, User
from ..services.ticketing import ensure_ticket
from . import local_bridge
from .global_entry import global_entry_settings

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-tickets'])


def _global_welcome(db: Session) -> str:
    config = global_entry_settings(db)
    if not config.get('enabled', True):
        return ''
    parts = [
        str(config.get('entry_message') or '').strip(),
        str(config.get('request_message') or '').strip(),
    ]
    return '\n\n'.join(part for part in parts if part)


def _replace_queued_reply(db: Session, result: dict, text: str, can_reply: bool) -> None:
    outbound_id = result.get('outbound_message_id')
    outbound = db.get(Message, outbound_id) if outbound_id else None
    if outbound:
        outbound.body = text
    result['reply_text'] = text if can_reply else ''
    result['should_reply'] = bool(text and can_reply)


@router.post('/inbound')
def ticketed_local_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    result = local_bridge.local_inbound(data=data, operator=operator, db=db)
    conversation_id = result.get('conversation_id') if isinstance(result, dict) else None
    if not conversation_id or result.get('status') in {'duplicate', 'ignored_group', 'known_support_skipped'}:
        return result

    conversation = db.get(Conversation, conversation_id)
    if not conversation or not conversation.company_id:
        return result

    company = db.get(Company, conversation.company_id)
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    store = db.get(Store, channel.store_id) if channel and channel.store_id else None
    if not company:
        return result

    routing = result.get('routing') or {}
    action = str(result.get('action') or '')
    inbound_count = db.query(func.count(Message.id)).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).scalar() or 0
    is_first_message = inbound_count == 1

    # A brand/store fallback selected by the Android bridge is not enough to
    # treat the customer as identified. On the first unidentified message
    # ("hola", "buenas", or any free text), always send the configurable
    # global-entry prompt instead of a company tree error/no-match response.
    if is_first_message and not routing.get('matched'):
        welcome = _global_welcome(db)
        if welcome:
            _replace_queued_reply(db, result, welcome, data.can_reply)
            result['action'] = 'global_entry'
            result['company_identified'] = False
            result['ticket_id'] = None
            result['ticket_code'] = None
            db.commit()
        return result

    tree = company.decision_tree or {}
    root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
    root_message = str((tree.get('nodos') or {}).get(root, {}).get('mensaje') or '').strip()

    # If the very first message already names the brand (for example "IQOS"
    # or "Coppel"), skip the global prompt and send that company's welcome.
    if is_first_message and routing.get('matched') and action.startswith('no_match') and root_message:
        _replace_queued_reply(db, result, root_message, data.can_reply)
        result['action'] = 'company_welcome'
        result['company_identified'] = True
    elif routing.get('matched'):
        result['company_identified'] = True

    # Tickets start only after the company has actually been identified from
    # the user's message. A generic first greeting does not create a ticket.
    if routing.get('matched'):
        ticket = ensure_ticket(
            db,
            company=company,
            store=store,
            conversation=conversation,
            description=data.text,
        )
        db.commit()
        result['ticket_id'] = ticket.id
        result['ticket_code'] = f'TKT-{ticket.id:06d}'
    else:
        db.commit()
    return result
