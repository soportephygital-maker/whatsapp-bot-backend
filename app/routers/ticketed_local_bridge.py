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


def _selected_context_store(data: local_bridge.LocalInbound, db: Session) -> Store | None:
    # An explicitly selected store is the strongest company context for a
    # generic first message such as "hola".
    if data.store_id:
        store = db.get(Store, data.store_id)
        if store:
            return store

    ids = list(dict.fromkeys(data.selected_store_ids or []))
    if not ids:
        return None
    stores = db.query(Store).filter(Store.id.in_(ids)).order_by(Store.id.asc()).all()
    company_ids = {row.company_id for row in stores}
    # If every selected store belongs to the same company, the company context
    # is unambiguous even though the message itself does not name the brand.
    if len(company_ids) == 1 and stores:
        return stores[0]
    return None


def _align_unmatched_conversation_context(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    conversation: Conversation,
    channel: ConversationChannel | None,
    result: dict,
) -> tuple[Company | None, Store | None]:
    store = _selected_context_store(data, db)
    if not store:
        company = db.get(Company, conversation.company_id) if conversation.company_id else None
        current_store = db.get(Store, channel.store_id) if channel and channel.store_id else None
        return company, current_store

    company = db.get(Company, store.company_id)
    if not company:
        return None, store

    conversation.company_id = company.id
    conversation.state = local_bridge._root_state(company.decision_tree or {})
    if channel:
        channel.company_id = company.id
        channel.store_id = store.id

    # Keep the API response consistent with the corrected database context so
    # the dashboard and Android client agree on the active company immediately.
    result['company_key'] = company.company_key
    result['company_name'] = company.name
    result['store_name'] = store.name
    return company, store


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

    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    routing = result.get('routing') or {}

    # local_bridge needs a fallback company to evaluate the tree. Do not let
    # that fallback leak into the dashboard when the Android app already gives
    # us an unambiguous selected store/company context.
    if not routing.get('matched'):
        company, store = _align_unmatched_conversation_context(
            db,
            data=data,
            conversation=conversation,
            channel=channel,
            result=result,
        )
    else:
        company = db.get(Company, conversation.company_id)
        store = db.get(Store, channel.store_id) if channel and channel.store_id else None

    if not company:
        return result

    action = str(result.get('action') or '')
    inbound_count = db.query(func.count(Message.id)).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).scalar() or 0
    is_first_message = inbound_count == 1

    # A brand/store fallback is not enough to treat the customer as identified.
    # On the first unidentified message ("hola", "buenas", or any free text),
    # always send the configurable global-entry prompt instead of a tree error.
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
