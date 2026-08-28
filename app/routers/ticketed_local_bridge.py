from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Company, Conversation, ConversationChannel, Store, User
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
