from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Company, Conversation, Store, User
from . import local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-global-entry-sequence'])

GLOBAL_ENTRY_WAITING_STATE = '__global_entry_waiting_company__'


def _active_before(db: Session, data: local_bridge.LocalInbound) -> Conversation | None:
    local_user_id = local_bridge._local_user_id(data)
    return ticketed_local_bridge._active_conversation(db, local_user_id)


@router.post('/inbound')
def global_entry_sequence_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Guarantee that the generic greeting is sent before the unmatched-company prompt.

    The existing ticketed bridge decides between the greeting and the retry text by
    counting inbound messages. That count can include older messages from an open
    conversation, so a user's first message of a new interaction may incorrectly
    receive the "empresa no identificada" response. This wrapper uses an explicit
    waiting state instead:

    1. First unidentified interaction -> generic greeting.
    2. Next unidentified reply -> unmatched-company guidance.
    3. Company/store identified -> continue through the normal ticketed bridge.
    """
    before = _active_before(db, data)
    was_waiting_for_company = bool(before and before.state == GLOBAL_ENTRY_WAITING_STATE)

    result = ticketed_local_bridge.ticketed_local_inbound(data=data, operator=operator, db=db)
    if not isinstance(result, dict):
        return result

    # Never interfere with duplicate suppression, ignored groups, known support
    # contacts, or the mandatory silence while a human operator owns the chat.
    if result.get('status') in {'duplicate', 'ignored_group', 'known_support_skipped', 'human_support_paused'}:
        return result
    if result.get('chatbot_paused') or result.get('action') in {'multi_message_warning', 'multi_message_burst_suppressed'}:
        return result

    if result.get('action') != 'global_entry' or result.get('company_identified'):
        return result

    conversation_id = result.get('conversation_id')
    conversation = db.get(Conversation, conversation_id) if conversation_id else None
    if not conversation:
        return result

    company = db.get(Company, conversation.company_id) if conversation.company_id else None
    store = ticketed_local_bridge._selected_context_store(
        data,
        db,
        company.id if company else None,
    )
    if not store and company:
        stores = ticketed_local_bridge._selected_company_stores(data, company.id, db)
        store = stores[0] if stores else None

    message = ticketed_local_bridge._global_welcome(db, retry=was_waiting_for_company)
    if message:
        ticketed_local_bridge._set_reply(
            db,
            result,
            message,
            data,
            conversation=conversation,
            company=company,
            store=store,
        )

    conversation.state = GLOBAL_ENTRY_WAITING_STATE
    result['action'] = 'global_entry_retry' if was_waiting_for_company else 'global_entry'
    result['company_identified'] = False
    result['ticket_id'] = None
    result['ticket_code'] = None
    db.commit()
    return result
