import re

from app.services.coppel_tree import TREE_SOURCE, TREE_VERSION, coppel_decision_tree
from app.services.decision_tree import match_response_with_action


def _destinations(node: dict):
    for option in node.get('opciones', []) or []:
        yield option.get('siguiente')
    for route in node.get('rutas', []) or []:
        yield route.get('siguiente')
    fallback = node.get('fallback')
    if isinstance(fallback, str):
        yield fallback
    elif isinstance(fallback, dict):
        yield fallback.get('siguiente')


def test_coppel_v5_metadata_and_scope():
    tree = coppel_decision_tree()
    assert tree['version'] == TREE_VERSION == 5
    assert tree['fuente'] == TREE_SOURCE
    assert '3 niveles' in tree['descripcion']
    assert len(tree['nodos']) >= 80


def test_all_coppel_destinations_exist():
    tree = coppel_decision_tree()
    nodes = tree['nodos']
    missing = [
        (key, destination)
        for key, node in nodes.items()
        for destination in _destinations(node)
        if destination and destination not in nodes
    ]
    assert missing == []


def test_company_identification_requires_explicit_coppel_term():
    tree = coppel_decision_tree()
    profile = tree['identificacion']
    all_terms = ' '.join(profile['aliases'] + profile['keywords'] + profile['tags']).lower()
    assert 'coppel' in all_terms
    assert 'preciadores' not in profile['tags']
    assert 'aims' not in profile['tags']


def test_numeric_menu_options_win_before_free_text_fallback():
    tree = coppel_decision_tree()

    matched, response, next_state, action = match_response_with_action(tree, 'menu', '7')
    assert matched is True
    assert next_state == 'pda_menu'
    assert 'PDA' in response
    assert action is None

    matched, response, next_state, action = match_response_with_action(tree, 'menu', '8')
    assert matched is True
    assert next_state == 'humano'
    assert action.startswith('human_help_ack:')
    assert '[NUMERO_TICKET]' in response


def test_free_text_menu_routes_cover_the_three_support_levels():
    tree = coppel_decision_tree()
    samples = {
        'el preciador no prende y está en blanco': 'apagado_dano',
        'AIMS indica batería baja': 'bateria_baja',
        'la PDA no abre AIMS Manager': 'pda_menu',
        'varios preciadores aparecen offline': 'varios_cantidad',
        'la base está rota': 'accesorio',
    }
    for text, expected_state in samples.items():
        matched, _, next_state, _ = match_response_with_action(tree, 'menu', text)
        assert matched is True, text
        assert next_state == expected_state, text


def test_ticket_number_is_processed_by_runtime_action():
    tree = coppel_decision_tree()
    matched, _, next_state, action = match_response_with_action(
        tree,
        'consulta_ticket',
        'EDM-CPP-20260904-123-000001',
    )
    assert matched is True
    assert next_state == 'ticket_resultado'
    assert action == 'ticket_status'


def test_only_supported_runtime_placeholders_are_sent():
    tree = coppel_decision_tree()
    placeholders = set()
    for node in tree['nodos'].values():
        texts = [node.get('mensaje', '')]
        texts.extend(option.get('respuesta', '') for option in node.get('opciones', []) or [])
        texts.extend(route.get('respuesta', '') for route in node.get('rutas', []) or [])
        fallback = node.get('fallback')
        if isinstance(fallback, dict):
            texts.append(fallback.get('respuesta', ''))
        for text in texts:
            placeholders.update(re.findall(r'\[[A-Z_]+\]', text or ''))
    assert placeholders <= {'[NOMBRE]', '[NUMERO_TICKET]'}
