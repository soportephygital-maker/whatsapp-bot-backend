from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Company, Conversation, ConversationChannel, Message, Store, User
from ..services.company_routing import detect_company
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
    if data.store_id:
        store = db.get(Store, data.store_id)
        if store:
            return store

    ids = list(dict.fromkeys(data.selected_store_ids or []))
    if not ids:
        return None
    stores = db.query(Store).filter(Store.id.in_(ids)).order_by(Store.id.asc()).all()
    company_ids = {row.company_id for row in stores}
    if len(company_ids) == 1 and stores:
        return stores[0]
    return None


def _sticky_company_input(data: local_bridge.LocalInbound, db: Session) -> local_bridge.LocalInbound:
    """Keep follow-up answers inside the company already identified for this chat.

    The Android app may have stores from several companies selected. A follow-up
    such as "accesorio" does not contain the word Coppel, so the base bridge used
    to fall back to the first selected company (often IQOS) and lose the Coppel
    decision-tree state. Once a contact has an active company conversation, use
    that company's selected stores for ordinary follow-up messages. An explicit
    mention of another company is still allowed to route normally.
    """
    local_user_id = local_bridge._local_user_id(data)
    active = db.query(Conversation).filter(
        Conversation.wa_user_id == local_user_id,
        Conversation.status.in_(['open', 'help_pending', 'human_active']),
    ).order_by(Conversation.updated_at.desc(), Conversation.id.desc()).first()
    if not active or not active.company_id:
        return data

    detected, routing = detect_company(db, data.text, fallback=None)
    if routing.get('matched'):
        # Explicit brand/company text wins. If it names the same company the base
        # bridge will keep it; if it names another one it may start that flow.
        return data

    selected_ids = list(dict.fromkeys([*(data.selected_store_ids or []), *([data.store_id] if data.store_id else [])]))
    if not selected_ids:
        return data
    matching_stores = db.query(Store).filter(
        Store.id.in_(selected_ids),
        Store.company_id == active.company_id,
    ).order_by(Store.id.asc()).all()
    if not matching_stores:
        return data

    payload = data.dict()
    payload['selected_store_ids'] = [row.id for row in matching_stores]
    payload['store_id'] = matching_stores[0].id
    return local_bridge.LocalInbound(**payload)


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

    if conversation.company_id != company.id:
        conversation.company_id = company.id
        conversation.state = local_bridge._root_state(company.decision_tree or {})
    if channel:
        channel.company_id = company.id
        channel.store_id = store.id

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
    effective_data = _sticky_company_input(data, db)
    result = local_bridge.local_inbound(data=effective_data, operator=operator, db=db)
    conversation_id = result.get('conversation_id') if isinstance(result, dict) else None
    if not conversation_id or result.get('status') in {'duplicate', 'ignored_group', 'known_support_skipped'}:
        return result

    conversation = db.get(Conversation, conversation_id)
    if not conversation or not conversation.company_id:
        return result

    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    routing = result.get('routing') or {}

    if not routing.get('matched'):
        company, store = _align_unmatched_conversation_context(
            db,
            data=effective_data,
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

    if is_first_message and not routing.get('matched'):
        welcome = _global_welcome(db)
        if welcome:
            _replace_queued_reply(db, result, welcome, effective_data.can_reply)
            result['action'] = 'global_entry'
            result['company_identified'] = False
            result['ticket_id'] = None
            result['ticket_code'] = None
        db.commit()
        return result

    tree = company.decision_tree or {}
    root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
    root_message = str((tree.get('nodos') or {}).get(root, {}).get('mensaje') or '').strip()

    if is_first_message and routing.get('matched') and action.startswith('no_match') and root_message:
        _replace_queued_reply(db, result, root_message, effective_data.can_reply)
        result['action'] = 'company_welcome'
        result['company_identified'] = True
    elif routing.get('matched'):
        result['company_identified'] = True

    if routing.get('matched'):
        ticket = ensure_ticket(
            db,
            company=company,
            store=store,
            conversation=conversation,
            description=effective_data.text,
        )
        db.commit()
        result['ticket_id'] = ticket.id
        result['ticket_code'] = f'TKT-{ticket.id:06d}'
    else:
        db.commit()
    return result
