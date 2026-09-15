from ..services import decision_tree
from . import local_bridge

_original_match = decision_tree.match_response_with_action


def _norm(value: str) -> str:
    return decision_tree._normalize(value)


def _numeric_option(node: dict, number: str):
    for option in node.get('opciones', []) or []:
        commands = decision_tree._criteria(option.get('comando', ''))
        if number in commands:
            return option
    return None


def _execute_option(option: dict, nodes: dict, state: str):
    next_state = option.get('siguiente') or state
    response = option.get('respuesta') or (nodes.get(next_state, {}) or {}).get('mensaje') or 'Continuemos.'
    action = option.get('accion') or option.get('action')
    action_value = str(action) if action else None
    return (
        True,
        decision_tree._silence_human_handoff(response, action_value),
        str(next_state),
        action_value,
    )


def _natural_numeric_choice(tree: dict, state: str, text: str):
    nodes = tree.get('nodos') or tree.get('nodes') or {}
    if not isinstance(nodes, dict):
        return None
    root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
    node = nodes.get(state) or nodes.get(root) or nodes.get('inicio')
    if not isinstance(node, dict):
        return None

    message = _norm(node.get('mensaje') or node.get('message') or '')
    answer = _norm(text)
    if not answer:
        return None

    yes_words = {
        'si', 'sí', 'aceptar', 'confirmar', 'correcto', 'correcta', 'finalizar',
        'finaliza', 'terminar', 'termina', 'cerrar', 'cierra', 'solucionado',
        'ya quedo', 'ya esta', 'esta resuelto', 'esta solucionado',
    }
    no_words = {
        'no', 'continuar', 'continua', 'seguir', 'sigue', 'no continuar',
        'aun no', 'todavia no', 'no esta resuelto', 'no esta solucionado',
        'el problema continua', 'continua el problema',
    }

    one = _numeric_option(node, '1')
    two = _numeric_option(node, '2')
    if not one and not two:
        return None

    # Explicit menu semantics for confirmation/finalization questions.
    confirmation_context = any(term in message for term in (
        'deseas finalizar', 'quieres finalizar', 'finalizar la atencion',
        'problema esta solucionado', 'problema esta resuelto',
        'esta foto es la correcta', 'foto es la correcta',
        'quieres reportar otro problema', 'deseas reportar otro problema',
    ))

    if confirmation_context:
        if one and (answer in yes_words or any(term in answer for term in ('finalizar', 'terminar', 'cerrar', 'si '))):
            return _execute_option(one, nodes, state)
        if two and (answer in no_words or any(term in answer for term in ('continuar', 'seguir', 'todavia no', 'aun no'))):
            return _execute_option(two, nodes, state)

    # Generic label matching: derive visible text from numbered lines in the node message.
    lines = [_norm(line) for line in str(node.get('mensaje') or node.get('message') or '').splitlines()]
    for number, option in (('1', one), ('2', two)):
        if not option:
            continue
        for line in lines:
            if not line.startswith(number + ' '):
                continue
            label = line[len(number) + 1:].strip()
            if label and (answer == label or answer in label or label in answer):
                return _execute_option(option, nodes, state)

    return None


def match_response_with_action(tree: dict, state: str, text: str):
    matched = _original_match(tree, state, text)
    if matched[0]:
        return matched
    natural = _natural_numeric_choice(tree, state, text)
    return natural if natural is not None else matched


def match_response(tree: dict, state: str, text: str):
    matched, response, next_state, _ = match_response_with_action(tree, state, text)
    return matched, response, next_state


# Patch both the service module and the function imported by local_bridge.
decision_tree.match_response_with_action = match_response_with_action
decision_tree.match_response = match_response
local_bridge.match_response_with_action = match_response_with_action
