def _normalize(value: str) -> str:
    return str(value or '').strip().lower()


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
            if _normalize(option.get('comando', '')) == _normalize(text):
                next_state = option.get('siguiente') or state
                response = option.get('respuesta') or nodes.get(next_state, {}).get('mensaje') or 'Continuemos.'
                action = option.get('accion') or option.get('action')
                return (True, str(response), str(next_state), str(action) if action else None)

        return (False, '', state, None)

    # Legacy flat dictionary format: {state: {message: ..., options: {...}}}
    node = tree.get(state) or tree.get('inicio')
    if not isinstance(node, dict):
        return (False, '', state, None)
    options = node.get('options') or node.get('opciones') or {}
    if isinstance(options, dict):
        selected = options.get(_normalize(text)) or options.get(text)
        if isinstance(selected, dict):
            next_state = selected.get('next') or selected.get('siguiente') or state
            response = selected.get('response') or selected.get('respuesta') or ''
            action = selected.get('action') or selected.get('accion')
            return (True, str(response), str(next_state), str(action) if action else None)
        if isinstance(selected, str):
            return (True, selected, state, None)
    return (False, '', state, None)


def match_response(tree: dict, state: str, text: str) -> tuple[bool, str, str]:
    matched, response, next_state, _ = match_response_with_action(tree, state, text)
    return matched, response, next_state
