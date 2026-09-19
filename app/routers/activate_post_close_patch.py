from ..models import Conversation, HelpRequest, Message
from . import conversation_admin, dashboard, local_bridge, post_close_flow_patch, ticketed_local_bridge

_original_inbound = ticketed_local_bridge.ticketed_local_inbound
_original_close = conversation_admin.close_conversation
_original_help_update = dashboard.update_help_request


def _queue_prompt(db, conversation):
    latest = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).first()
    payload = dict(latest.raw_payload or {}) if latest else {}
    conversation.status = 'open'
    conversation.state = 'post_close_prompt'
    db.add(Message(
        conversation_id=conversation.id,
        direction='outbound',
        sender='bot',
        body='¿Quieres reportar otro problema?\n1️⃣ Sí, abrir un reporte nuevo\n2️⃣ No',
        raw_payload={
            'transport': 'android_notification',
            'manual_dashboard': True,
            'delivery_status': 'requested',
            'device_id': payload.get('device_id'),
            'notification_key': payload.get('notification_key'),
            'package_name': payload.get('package_name'),
            'sender_display': payload.get('sender_display'),
        },
    ))


def _routed_inbound(data, operator, db):
    local_user_id = local_bridge._local_user_id(data)
    conversation = db.query(Conversation).filter(
        Conversation.wa_user_id == local_user_id,
        Conversation.status.in_(['open', 'help_pending', 'human_active']),
    ).order_by(Conversation.id.desc()).first()
    if not conversation or conversation.state not in {'post_close_prompt', 'post_close_wait'}:
        return _original_inbound(data=data, operator=operator, db=db)
    ticketed_local_bridge.ticketed_local_inbound = _original_inbound
    try:
        return post_close_flow_patch.post_close_inbound(data=data, operator=operator, db=db)
    finally:
        ticketed_local_bridge.ticketed_local_inbound = _routed_inbound


def _close(*args, **kwargs):
    result = _original_close(*args, **kwargs)
    db = kwargs.get('db')
    conversation_id = kwargs.get('conversation_id')
    if db is not None and conversation_id is not None:
        conversation = db.get(Conversation, conversation_id)
        if conversation:
            _queue_prompt(db, conversation)
            db.commit()
            if isinstance(result, dict):
                result['post_close_prompt'] = True
                result['chatbot_resumed'] = False
    return result


def _help_update(*args, **kwargs):
    result = _original_help_update(*args, **kwargs)
    db = kwargs.get('db')
    request_id = kwargs.get('request_id')
    data = kwargs.get('data')
    if db is not None and request_id is not None and getattr(data, 'status', None) in ('resolved', 'ignored'):
        request = db.get(HelpRequest, request_id)
        conversation = db.get(Conversation, request.conversation_id) if request and request.conversation_id else None
        if conversation:
            _queue_prompt(db, conversation)
            db.commit()
            if isinstance(result, dict):
                result['post_close_prompt'] = True
                result['chatbot_resumed'] = False
    return result


conversation_admin.close_conversation = _close
dashboard.update_help_request = _help_update
ticketed_local_bridge.ticketed_local_inbound = _routed_inbound
