from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Company, Conversation, ConversationChannel, Message, Store, User
from ..services.ticketing import ensure_ticket
from . import local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-tickets'])


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
    if company:
        routing = result.get('routing') or {}
        action = str(result.get('action') or '')
        tree = company.decision_tree or {}
        root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
        root_message = str((tree.get('nodos') or {}).get(root, {}).get('mensaje') or '').strip()
        if routing.get('matched') and action.startswith('no_match') and conversation.state == root and root_message:
            outbound_id = result.get('outbound_message_id')
            outbound = db.get(Message, outbound_id) if outbound_id else None
            if outbound:
                outbound.body = root_message
            result['action'] = 'company_welcome'
            if data.can_reply:
                result['reply_text'] = root_message
                result['should_reply'] = True
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
    return result
