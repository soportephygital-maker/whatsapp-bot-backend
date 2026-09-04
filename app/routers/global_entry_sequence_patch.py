from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Company, Conversation, Message, Store, User
from . import local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-global-entry-sequence'])

GLOBAL_ENTRY_WAITING_STATE = '__global_entry_waiting_company__'
GLOBAL_ENTRY_RETRY_STATE = '__global_entry_retry_company__'


def _safe_rapid_multi_message_state(
    db: Session,
    conversation_id: int,
    current_message_id: int,
    current_post_time: int,
) -> tuple[bool, bool]:
    """Detect a real multi-message burst without blocking a normal reply to the bot.

    A second inbound message is considered part of a burst only when it arrives
    within the configured window AND the bot has not sent any outbound message
    after the previous inbound. If the previous inbound was already marked as a
    burst, keep suppressing additional messages in that same rapid sequence.
    """
    if current_post_time <= 0:
        return False, False

    previous = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'inbound',
        Message.id < current_message_id,
    ).order_by(Message.id.desc()).first()
    if not previous:
        return False, False

    payload = previous.raw_payload or {}
    try:
        previous_post_time = int(payload.get('post_time') or 0)
    except (TypeError, ValueError):
        previous_post_time = 0
    if previous_post_time <= 0:
        return False, False

    delta = current_post_time - previous_post_time
    if delta < 0 or delta > local_bridge.MULTI_MESSAGE_WINDOW_MS:
        return False, False

    if payload.get('multi_message_burst'):
        return True, True

    bot_replied_between = db.query(Message.id).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'outbound',
        Message.id > previous.id,
        Message.id < current_message_id,
    ).first() is not None
    if bot_replied_between:
        return False, False

    return True, False


# local_bridge.local_inbound resolves this helper at request time, so replacing it
# here keeps the existing endpoint intact while correcting the false-positive case.
local_bridge._rapid_multi_message_state = _safe_rapid_multi_message_state


def _active_before(db: Session, data: local_bridge.LocalInbound) -> Conversation | None:
    local_user_id = local_bridge._local_user_id(data)
    return ticketed_local_bridge._active_conversation(db, local_user_id)


@router.post('/inbound')
def global_entry_sequence_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Keep the global intake sequence stable until company/store are identified.

    Sequence:
    1. First unidentified interaction -> generic greeting.
    2. Next unidentified reply -> unmatched-company/store guidance.
    3. Every later unidentified reply -> keep repeating that guidance; never greet again.
    4. Company/store identified -> continue through the normal ticketed bridge.
    """
    before = _active_before(db, data)
    previous_state = before.state if before else None
    already_greeted = previous_state in {GLOBAL_ENTRY_WAITING_STATE, GLOBAL_ENTRY_RETRY_STATE}

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

    # Once the greeting has been sent, every unidentified response must use the
    # configured retry message. We keep a dedicated retry state so the bot cannot
    # fall back to the greeting again on the third, fourth, etc. attempt.
    retry = already_greeted
    message = ticketed_local_bridge._global_welcome(db, retry=retry)
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

    conversation.state = GLOBAL_ENTRY_RETRY_STATE if retry else GLOBAL_ENTRY_WAITING_STATE
    result['action'] = 'global_entry_retry' if retry else 'global_entry'
    result['company_identified'] = False
    result['ticket_id'] = None
    result['ticket_code'] = None
    db.commit()
    return result
