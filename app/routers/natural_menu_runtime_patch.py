import re

from ..services import decision_tree
from . import local_bridge

_original_match = decision_tree.match_response_with_action

_STOP = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'al', 'a',
    'en', 'y', 'o', 'que', 'se', 'es', 'esta', 'este', 'esto', 'por', 'para', 'con',
    'mi', 'tu', 'su', 'me', 'lo', 'le', 'ya', 'muy', 'mas', 'otro', 'otra',
}


def _norm(value: str) -> str:
    return decision_tree._normalize(value)


def _stem(token: str) -> str:
    value = token
    for suffix in ('mente', 'aciones', 'acion', 'iendo', 'ando', 'ados', 'adas', 'ado', 'ada', 'idos', 'idas', 'ido', 'ida', 'os', 'as'):
        if len(value) > len(suffix) + 3 and value.endswith(suffix):
            value = value[:-len(suffix)]
            break
    if len(value) > 4 and value.endswith(('o', 'a')):
        value = value[:-1]
    return value


def _tokens(value: str) -> set[str]:
    return {_stem(x) for x in _norm(value).split() if len(x) >= 3 and x not in _STOP}


def _numeric_options(node: dict) -> dict[str, dict]:
    result = {}
    for option in node.get('opciones', []) or []:
        for command in decision_tree._criteria(option.get('comando', '')):
            if command.isdigit():
                result.setdefault(command, option)
    return result


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


def _visible_labels(node: dict) -> dict[str, str]:
    labels = {}
    raw = str(node.get('mensaje') or node.get('message') or '')
    for line in raw.splitlines():
        normalized = _norm(line)
        match = re.match(r'^(\d+)\s+(.+)$', normalized)
        if match:
            labels[match.group(1)] = match.group(2).strip()
    return labels


def _related(answer: str, label: str) -> bool:
    a = _norm(answer)
    b = _norm(label)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and (a in b or b in a):
        return True
    at = _tokens(a)
    bt = _tokens(b)
    if not at or not bt:
        return False
    common = at & bt
    if len(common) >= 2 and len(common) / min(len(at), len(bt)) >= 0.60:
        return True
    if len(at) == 1 and at <= bt:
        return True
    return False


def _natural_numeric_choice(tree: dict, state: str, text: str):
    nodes = tree.get('nodos') or tree.get('nodes') or {}
    if not isinstance(nodes, dict):
        return None
    root = tree.get('nodo_raiz') or tree.get('root') or 'inicio'
    node = nodes.get(state) or nodes.get(root) or nodes.get('inicio')
    if not isinstance(node, dict):
        return None

    answer = _norm(text)
    if not answer:
        return None

    options = _numeric_options(node)
    if not options:
        return None
    labels = _visible_labels(node)
    message = _norm(node.get('mensaje') or node.get('message') or '')

    yes_words = {
        'si', 'aceptar', 'confirmar', 'correcto', 'correcta', 'finalizar', 'finaliza',
        'terminar', 'termina', 'cerrar', 'cierra', 'solucionado', 'resuelto',
        'ya quedo', 'ya esta', 'esta resuelto', 'esta solucionado',
    }
    no_words = {
        'no', 'continuar', 'continua', 'seguir', 'sigue', 'no continuar', 'aun no',
        'todavia no', 'no esta resuelto', 'no esta solucionado', 'el problema continua',
        'continua el problema',
    }

    confirmation_context = any(term in message for term in (
        'deseas finalizar', 'quieres finalizar', 'finalizar la atencion',
        'problema esta solucionado', 'problema esta resuelto',
        'esta foto es la correcta', 'foto es la correcta',
        'quieres reportar otro problema', 'deseas reportar otro problema',
    ))
    if confirmation_context:
        one = options.get('1')
        two = options.get('2')
        if one and (answer in yes_words or any(term in answer for term in ('finalizar', 'terminar', 'cerrar', 'resuelto', 'solucionado'))):
            return _execute_option(one, nodes, state)
        if two and (answer in no_words or any(term in answer for term in ('continuar', 'seguir', 'todavia no', 'aun no'))):
            return _execute_option(two, nodes, state)

    scored = []
    for number, option in options.items():
        label = labels.get(number, '')
        if not label:
            continue
        if _related(answer, label):
            overlap = len(_tokens(answer) & _tokens(label))
            scored.append((overlap, len(label), number, option))
    if scored:
        scored.sort(key=lambda row: (-row[0], row[1], int(row[2])))
        return _execute_option(scored[0][3], nodes, state)

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


decision_tree.match_response_with_action = match_response_with_action
decision_tree.match_response = match_response
local_bridge.match_response_with_action = match_response_with_action
