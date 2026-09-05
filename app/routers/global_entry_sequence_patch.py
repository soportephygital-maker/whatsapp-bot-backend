from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import AuditLog, Company, Conversation, Message, Store, User
from . import local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-global-entry-sequence'])

GLOBAL_ENTRY_WAITING_STATE = '__global_entry_waiting_company__'
GLOBAL_ENTRY_RETRY_STATE = '__global_entry_retry_company__'
BOT_ECHO_WINDOW_SECONDS = 30
SELF_SENDER_LABELS = {'tu', 'you', 'me', 'yo'}


def _safe_rapid_multi_message_state(
    db: Session,
    conversation_id: int,
    current_message_id: int,
    current_post_time: int,
) -> tuple[bool, bool]:
    """Detect a real multi-message burst without blocking a normal reply to the bot."""
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


local_bridge._rapid_multi_message_state = _safe_rapid_multi_message_state


def _active_before(db: Session, data: local_bridge.LocalInbound) -> Conversation | None:
    local_user_id = local_bridge._local_user_id(data)
    return ticketed_local_bridge._active_conversation(db, local_user_id)


def _same_device(payload: dict, data: local_bridge.LocalInbound) -> bool:
    return str(payload.get('device_id') or '') == str(data.device_id or '')


def _is_recent_bot_echo_any_conversation(
    db: Session,
    data: local_bridge.LocalInbound,
) -> tuple[bool, Message | None]:
    """Catch WhatsApp echoes even when Android reports the sender as 'Tú'.

    Inline replies may be reposted by WhatsApp with a different notification title.
    That changes the local user id, so a same-conversation echo guard is not enough.
    We therefore compare the incoming text with recent bot output from the same
    Android device before any conversation routing happens.
    """
    candidate = local_bridge._normalize_text(data.text)
    if not candidate:
        return False, None

    cutoff = datetime.utcnow() - timedelta(seconds=BOT_ECHO_WINDOW_SECONDS)
    rows = db.query(Message).filter(
        Message.direction == 'outbound',
        Message.sender == 'bot',
        Message.created_at >= cutoff,
    ).order_by(Message.id.desc()).limit(30).all()

    sender_label = local_bridge._normalize_text(data.sender)
    sender_is_self = sender_label in SELF_SENDER_LABELS

    for row in rows:
        payload = row.raw_payload or {}
        if not _same_device(payload, data):
            continue
        sent = local_bridge._normalize_text(row.body or '')
        if not sent:
            continue
        exact = candidate == sent
        rebuilt = len(sent) >= 40 and (candidate.endswith(sent) or sent.endswith(candidate))
        if exact or rebuilt:
            return True, row

    # A notification explicitly titled "Tú/You/Me" is an outgoing WhatsApp
    # notification, not a customer message. Ignore it even if WhatsApp altered the
    # visible body enough that exact echo comparison is no longer possible.
    if sender_is_self:
        return True, None

    return False, None


@router.post('/inbound')
def global_entry_sequence_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Keep global intake stable and reject WhatsApp self-notification echoes."""
    is_echo, echoed = _is_recent_bot_echo_any_conversation(db, data)
    if is_echo:
        conversation_id = echoed.conversation_id if echoed else None
        db.add(AuditLog(
            username=operator.username,
            action='local_bridge_bot_echo_ignored',
            entity='conversation' if conversation_id else 'local_bridge',
            entity_id=str(conversation_id or data.device_id),
            details={
                'echoed_outbound_message_id': echoed.id if echoed else None,
                'sender': data.sender,
                'package': data.package_name,
                'device_id': data.device_id,
                'window_seconds': BOT_ECHO_WINDOW_SECONDS,
            },
        ))
        db.commit()
        return {
            'status': 'duplicate',
            'conversation_id': conversation_id,
            'action': 'bot_echo_ignored',
            'reply_text': '',
            'should_reply': False,
            'outbound_message_id': None,
            'chatbot_paused': False,
        }

    before = _active_before(db, data)
    previous_state = before.state if before else None
    already_greeted = previous_state in {GLOBAL_ENTRY_WAITING_STATE, GLOBAL_ENTRY_RETRY_STATE}

    result = ticketed_local_bridge.ticketed_local_inbound(data=data, operator=operator, db=db)
    if not isinstance(result, dict):
        return result

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
