import re
import unicodedata


def _normalize(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _criteria(value: str) -> list[str]:
    # A command can contain alternatives separated by commas, semicolons or pipes.
    # Example: "etiquetas, costos" means etiquetas OR costos.
    return [item for item in (_normalize(part) for part in re.split(r'[,;|]+', str(value or ''))) if item]


def _contains_criterion(message: str, criterion: str) -> bool:
    if not message or not criterion:
        return False
    # Normalized strings are space-delimited, so padding with spaces gives us
    # token/phrase boundaries and prevents a command such as "a" matching "hola".
    return f' {criterion} ' in f' {message} '


def _matches(command: str, text: str) -> bool:
    message = _normalize(text)
    return any(_contains_criterion(message, criterion) for criterion in _criteria(command))


def _silence_human_handoff(response: str, action: str | None) -> str:
    return '' if str(action or '').strip().lower() == 'human_help' else str(response)


def match_response_with_action(tree: dict, state: str, text: str) -> tuple[bool, str, str, str | None]:
    if not tree:
        return (False, '', state, None)

    nodes = tree.get('nodos') or tree.get('nodes')
    if isinstance(nodes, dict):
        root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
        node = nodes.get(state) or nodes.get(root) or nodes.get('inicio')
        if not node:
            return (False, '', state, None)

        for option in node.get('opciones', []) or []:
            if _matches(option.get('comando', ''), text):
                next_state = option.get('siguiente') or state
                response = option.get('respuesta') or nodes.get(next_state, {}).get('mensaje') or 'Continuemos.'
                action = option.get('accion') or option.get('action')
                action_value = str(action) if action else None
                return (True, _silence_human_handoff(response, action_value), str(next_state), action_value)

        return (False, '', state, None)

    # Legacy flat dictionary format: {state: {message: ..., options: {...}}}
    node = tree.get(state) or tree.get('inicio')
    if not isinstance(node, dict):
        return (False, '', state, None)
    options = node.get('options') or node.get('opciones') or {}
    if isinstance(options, dict):
        for command, selected in options.items():
            if not _matches(str(command), text):
                continue
            if isinstance(selected, dict):
                next_state = selected.get('next') or selected.get('siguiente') or state
                response = selected.get('response') or selected.get('respuesta') or ''
                action = selected.get('action') or selected.get('accion')
                action_value = str(action) if action else None
                return (True, _silence_human_handoff(response, action_value), str(next_state), action_value)
            if isinstance(selected, str):
                return (True, selected, state, None)
    return (False, '', state, None)


def match_response(tree: dict, state: str, text: str) -> tuple[bool, str, str]:
    matched, response, next_state, _ = match_response_with_action(tree, state, text)
    return matched, response, next_state
