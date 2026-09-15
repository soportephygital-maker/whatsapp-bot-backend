from app.services.company_routing import base_decision_tree
from app.services.decision_tree import match_response, match_response_with_action


def test_human_help_action_is_exposed():
    tree = base_decision_tree()
    matched, response, next_state, action = match_response_with_action(tree, 'inicio', '3')
    assert matched is True
    assert next_state == 'humano'
    assert action == 'human_help'
    assert response == ''


def test_legacy_three_value_match_remains_compatible():
    tree = base_decision_tree()
    matched, response, next_state = match_response(tree, 'inicio', '1')
    assert matched is True
    assert next_state == 'soporte'
    assert response


def test_unknown_command_does_not_move_state():
    tree = base_decision_tree()
    matched, response, next_state, action = match_response_with_action(tree, 'inicio', '99')
    assert matched is False
    assert response == ''
    assert next_state == 'inicio'
    assert action is None


def routed_tree():
    return {
        'nodo_raiz': 'inicio',
        'nodos': {
            'inicio': {
                'tipo': 'router',
                'mensaje': 'Cuéntame qué necesitas.',
                'rutas': [
                    {'palabras': ['playera', 'textil', 'dtf'], 'siguiente': 'textil', 'prioridad': 5},
                    {'palabras': ['display', 'exhibidor', 'retail'], 'siguiente': 'retail', 'prioridad': 10},
                    {'palabras': ['evento', 'stand', 'activación'], 'siguiente': 'eventos', 'prioridad': 4},
                    {'palabras': ['persona', 'humano', 'asesor'], 'siguiente': 'humano', 'accion': 'human_help', 'prioridad': 50},
                ],
                'fallback': {'siguiente': 'general'},
            },
            'textil': {'mensaje': 'Perfecto. Hablemos de textil.', 'opciones': []},
            'retail': {'mensaje': 'Perfecto. Hablemos de retail.', 'opciones': []},
            'eventos': {'mensaje': 'Perfecto. Hablemos de eventos.', 'opciones': []},
            'general': {'mensaje': 'No logré identificar el servicio.', 'opciones': []},
            'humano': {'mensaje': 'No debe enviarse.', 'opciones': []},
        },
    }


def test_router_matches_contains_and_ignores_accents_case():
    matched, response, next_state, action = match_response_with_action(
        routed_tree(), 'inicio', 'Necesito una ACTIVACIÓN para un evento'
    )
    assert matched is True
    assert next_state == 'eventos'
    assert response == 'Perfecto. Hablemos de eventos.'
    assert action is None


def test_router_uses_priority_when_multiple_routes_match():
    matched, response, next_state, action = match_response_with_action(
        routed_tree(), 'inicio', 'Necesito un exhibidor retail con playeras'
    )
    assert matched is True
    assert next_state == 'retail'
    assert response == 'Perfecto. Hablemos de retail.'
    assert action is None


def test_router_fallback_routes_to_configured_node():
    matched, response, next_state, action = match_response_with_action(
        routed_tree(), 'inicio', 'Tengo una consulta completamente diferente'
    )
    assert matched is True
    assert next_state == 'general'
    assert response == 'No logré identificar el servicio.'
    assert action is None


def test_router_human_help_is_silent():
    matched, response, next_state, action = match_response_with_action(
        routed_tree(), 'inicio', 'Quiero hablar con un asesor humano'
    )
    assert matched is True
    assert next_state == 'humano'
    assert action == 'human_help'
    assert response == ''


def test_router_exact_mode_requires_full_normalized_message():
    tree = routed_tree()
    tree['nodos']['inicio']['rutas'] = [
        {'palabras': ['soporte técnico'], 'siguiente': 'retail', 'coincidencia': 'exact'}
    ]
    tree['nodos']['inicio']['fallback'] = None

    assert match_response_with_action(tree, 'inicio', 'Soporte técnico')[0] is True
    assert match_response_with_action(tree, 'inicio', 'Necesito soporte técnico')[0] is False
