def _normalize(value: str) -> str:
    return str(value or '').strip().lower()


def match_response(tree: dict, state: str, text: str) -> tuple[bool, str, str]:
    if not tree:
        return (False, '', state)

    nodes = tree.get('nodos') or tree.get('nodes')
    if isinstance(nodes, dict):
        root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
        node = nodes.get(state) or nodes.get(root) or nodes.get('inicio')
        if not node:
            return (False, '', state)

        for option in node.get('opciones', []) or []:
            if _normalize(option.get('comando', '')) == _normalize(text):
                next_state = option.get('siguiente') or state
                response = option.get('respuesta') or nodes.get(next_state, {}).get('mensaje') or 'Continuemos.'