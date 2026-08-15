def resolve_response(tree: dict, state: str, text: str) -> tuple[str, str]:
    if not tree:
        return ('No hay un flujo configurado para esta empresa.', state)

    nodes = tree.get('nodos') or tree.get('nodes')
    if isinstance(nodes, dict):
        node = nodes.get(state) or nodes.get(tree.get('nodo_raiz')) or nodes.get('inicio')
        if not node:
            return ('No pude encontrar el paso actual del flujo.', state)
        options = node.get('opciones', [])
        for option in options:
            if str(option.get('comando', '')).strip().lower() == text.strip().lower():
                next_state = option.get('siguiente') or state
                response = option.get('respuesta') or nodes.get(next_state, {}).get('mensaje') or 'Continuemos.'
                return (response, next_state)
        return (node.get('mensaje') or 'Selecciona una opción válida.', state)

    options = tree.get('opciones', [])
    for option in options:
        if str(option.get('comando', '')).strip().lower() == text.strip().lower():
            return (option.get('respuesta') or 'Continuemos.', option.get('siguiente') or state)
    return ('Selecciona una opción válida.', state)
