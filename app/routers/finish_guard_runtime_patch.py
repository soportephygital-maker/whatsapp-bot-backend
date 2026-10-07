from sqlalchemy.orm import Session

from ..models import AuditLog, Company, Conversation
from ..services import decision_tree
from . import local_bridge, ticketed_local_bridge

_original_match = local_bridge.match_response_with_action
_original_ticketed_local_inbound = ticketed_local_bridge.ticketed_local_inbound

_EXPLICIT_FINISH = {
    'fin', 'finalizar', 'finaliza', 'terminar', 'termina', 'cerrar', 'cierra',
    'cerrar caso', 'cerrar ticket', 'finalizar caso', 'finalizar ticket',
    'terminar caso', 'terminar ticket',
}


def _is_explicit_finish(text: str) -> bool:
    normalized = local_bridge._normalize_text(text)
    return normalized in _EXPLICIT_FINISH


def _looks_like_prompt(text: str) -> bool:
    value = str(text or '').strip()
    if not value:
        return False
    if '?' in value or '¿' in value:
        return True
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    option_lines = 0
    for line in lines:
        if line[:1].isdigit() or line.startswith(('0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣')):
            option_lines += 1
    return option_lines >= 2


def _guarded_match(tree: dict, state: str, text: str):
    matched, response, next_state, action = _original_match(tree, state, text)
    action_value = str(action or '').strip().lower()
    if matched and action_value in {'finish', 'ticket_close'} and _looks_like_prompt(response) and not _is_explicit_finish(text):
        # A node cannot close while its own response is still asking the user a question.
        # Preserve the destination state and response, but defer the close action until
        # the user actually answers or sends an explicit close command.
        return matched, response, next_state, 'pending_question'
    return matched, response, next_state, action


# local_bridge imported match_response_with_action directly, so patch that bound symbol.
local_bridge.match_response_with_action = _guarded_match


def _recover_destination_state(tree: dict, previous_state: str | None, text: str, prompt: str) -> str | None:
    root = local_bridge._root_state(tree)
    state = previous_state or root

    matched, response, next_state, action = decision_tree.match_response_with_action(tree, state, text)
    if not matched and state != root:
        matched, response, next_state, action = decision_tree.match_response_with_action(tree, root, text)
    if matched and next_state:
        return str(next_state)

    nodes = tree.get('nodos') or tree.get('nodes') or {}
    prompt_norm = local_bridge._normalize_text(prompt)
    if isinstance(nodes, dict) and prompt_norm:
        for node_id, node in nodes.items():
            if not isinstance(node, dict):
                continue
            node_message = str(node.get('mensaje') or node.get('message') or '').strip()
            if node_message and local_bridge._normalize_text(node_message) == prompt_norm:
                return str(node_id)
    return previous_state


def guarded_ticketed_local_inbound(data, operator, db: Session):
    local_user_id = local_bridge._local_user_id(data)
    before = ticketed_local_bridge._active_conversation(db, local_user_id)
    previous_state = before.state if before else None

    result = _original_ticketed_local_inbound(data=data, operator=operator, db=db)
    if not isinstance(result, dict):
        return result

    action_base, _ = ticketed_local_bridge._action_parts(result.get('action'))
    if action_base not in {'finish', 'ticket_close'}:
        return result

    prompt = str(result.get('reply_text') or '')
    if _is_explicit_finish(data.text) or not _looks_like_prompt(prompt):
        return result

    conversation_id = result.get('conversation_id')
    conversation = db.get(Conversation, conversation_id) if conversation_id else None
    if not conversation:
        return result

    company = db.get(Company, conversation.company_id) if conversation.company_id else None
    tree = company.decision_tree or {} if company else {}
    recovered_state = _recover_destination_state(tree, previous_state, data.text, prompt)

    conversation.status = 'open'
    if recovered_state:
        conversation.state = recovered_state
    elif previous_state:
        conversation.state = previous_state

    db.add(AuditLog(
        username=getattr(operator, 'username', None),
        action='finish_deferred_for_pending_question',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'previous_state': previous_state,
            'recovered_state': conversation.state,
            'incoming_text': str(data.text or '')[:500],
            'prompt': prompt[:1000],
            'original_action': action_base,
        },
    ))
    result['action'] = 'pending_question'
    result['chatbot_paused'] = False
    db.commit()
    return result


ticketed_local_bridge.ticketed_local_inbound = guarded_ticketed_local_inbound
