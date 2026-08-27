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
