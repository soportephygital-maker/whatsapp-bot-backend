import re
import unicodedata


def _normalize(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _criteria(value) -> list[str]:
    """Return normalized alternatives from strings or lists.

    Existing tree options use a single command string with comma/semicolon/pipe
    alternatives. Routed nodes additionally allow an explicit list of keywords.
    """
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_criteria(item))
        return list(dict.fromkeys(result))
    return [
        item
        for item in (_normalize(part) for part in re.split(r'[,;|]+', str(value or '')))
        if item
    ]


def _contains_criterion(message: str, criterion: str) -> bool:
    if not message or not criterion:
        return False
    # Normalized strings are space-delimited, so padding with spaces gives us
    # token/phrase boundaries and prevents a command such as "a" matching "hola".
    return f' {criterion} ' in f' {message} '


def _matches(command, text: str, mode: str = 'contains') -> bool:
    message = _normalize(text)
    criteria = _criteria(command)
    normalized_mode = _normalize(mode).replace(' ', '_')
    if normalized_mode in {'exact', 'exacta', 'igual'}:
        return any(message == criterion for criterion in criteria)
    return any(_contains_criterion(message, criterion) for criterion in criteria)


def _silence_human_handoff(response: str, action: str | None) -> str:
    return '' if str(action or '').strip().lower() == 'human_help' else str(response)


def _route_terms(route: dict):
    for key in ('palabras', 'keywords', 'terms', 'frases', 'phrases'):
        value = route.get(key)
        if value:
            return value
    return route.get('comando') or route.get('command') or ''


def _route_priority(route: dict) -> int:
    try:
        return int(route.get('prioridad', route.get('priority', 0)) or 0)
    except (TypeError, ValueError):
        return 0


def _route_destination(route: dict, state: str) -> str:
    return str(
        route.get('siguiente')
        or route.get('destino')
        or route.get('next')
        or route.get('destination')
        or state
    )


def _route_action(route: dict) -> str | None:
    action = route.get('accion') or route.get('action')
    return str(action) if action else None


def _route_response(route: dict, nodes: dict, next_state: str) -> str:
    return str(
        route.get('respuesta')
        or route.get('response')
        or (nodes.get(next_state, {}) or {}).get('mensaje')
        or (nodes.get(next_state, {}) or {}).get('message')
        or 'Continuemos.'
    )


def _fallback_result(node: dict, nodes: dict, state: str):
    fallback = node.get('fallback', node.get('default'))
    if not fallback:
        return None

    if isinstance(fallback, str):
        next_state = fallback
        action = None
        response = (nodes.get(next_state, {}) or {}).get('mensaje') or (nodes.get(next_state, {}) or {}).get('message') or 'Continuemos.'
    elif isinstance(fallback, dict):
        next_state = _route_destination(fallback, state)
        action = _route_action(fallback)
        response = _route_response(fallback, nodes, next_state)
    else:
        return None

    return (
        True,
        _silence_human_handoff(str(response), action),
        str(next_state),
        action,
    )


def _match_routed_node(node: dict, nodes: dict, state: str, text: str):
    routes = node.get('rutas') or node.get('routes') or []
    if not isinstance(routes, list):
        routes = []

    # Higher priority wins. Stable sort preserves the dashboard order for ties.
    indexed_routes = list(enumerate(route for route in routes if isinstance(route, dict)))
    indexed_routes.sort(key=lambda row: (-_route_priority(row[1]), row[0]))

    for _, route in indexed_routes:
        terms = _route_terms(route)
        mode = route.get('coincidencia') or route.get('match') or route.get('match_type') or 'contains'
        if not _matches(terms, text, str(mode)):
            continue
        next_state = _route_destination(route, state)
        action = _route_action(route)
        response = _route_response(route, nodes, next_state)
        return (
            True,
            _silence_human_handoff(response, action),
            next_state,
            action,
        )

    # Fallback is intentionally evaluated after normal options. A routed node can
    # therefore keep numeric/menu options and still use a free-text fallback.
    return None


def match_response_with_action(tree: dict, state: str, text: str) -> tuple[bool, str, str, str | None]:
    if not tree:
        return (False, '', state, None)

    nodes = tree.get('nodos') or tree.get('nodes')
    if isinstance(nodes, dict):
        root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
        node = nodes.get(state) or nodes.get(root) or nodes.get('inicio')
        if not node:
            return (False, '', state, None)

        node_type = _normalize(node.get('tipo') or node.get('type') or '')
        is_router = node_type in {
            'router',
            'routing',
            'pregunta con enrutamiento',
            'respuesta general con rutas',
            'pregunta_enrutamiento',
        } or isinstance(node.get('rutas') or node.get('routes'), list)

        if is_router:
            routed = _match_routed_node(node, nodes, state, text)
            if routed is not None:
                return routed

        # Preserve the current option-based behavior exactly for existing trees.
        for option in node.get('opciones', []) or []:
            if _matches(option.get('comando', ''), text):
                next_state = option.get('siguiente') or state
                response = option.get('respuesta') or nodes.get(next_state, {}).get('mensaje') or 'Continuemos.'
                action = option.get('accion') or option.get('action')
                action_value = str(action) if action else None
                return (True, _silence_human_handoff(response, action_value), str(next_state), action_value)

        if is_router:
            fallback = _fallback_result(node, nodes, state)
            if fallback is not None:
                return fallback

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
