from app.routers import image_evidence_listo_patch, image_evidence_patch


def test_active_image_states_are_owned_by_image_flow():
    assert image_evidence_patch.IMAGE_CONFIRM_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_EVIDENCE_ACTION_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_WAIT_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_INCIDENT_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_MORE_PROBLEM_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES


def test_photo_confirmation_menu_is_the_review_or_evidence_branch():
    text = image_evidence_patch.IMAGE_CONFIRM_TEXT
    assert '1️⃣ Sí, usar esta evidencia y revisar los datos del reporte' in text
    assert '2️⃣ No, agregar o cambiar la foto' in text


def test_second_evidence_menu_is_add_or_change():
    text = image_evidence_patch.IMAGE_EVIDENCE_ACTION_TEXT
    assert '1️⃣ Agregar' in text
    assert '2️⃣ Cambiar' in text


def test_prompt_recovery_maps_the_evidence_menus():
    assert image_evidence_listo_patch._state_from_prompt(
        image_evidence_patch.IMAGE_CONFIRM_TEXT
    ) == image_evidence_patch.IMAGE_CONFIRM_STATE
    assert image_evidence_listo_patch._state_from_prompt(
        image_evidence_patch.IMAGE_EVIDENCE_ACTION_TEXT
    ) == image_evidence_patch.IMAGE_EVIDENCE_ACTION_STATE
    assert image_evidence_listo_patch._state_from_prompt(
        image_evidence_patch.IMAGE_ANOTHER_TEXT
    ) == image_evidence_patch.IMAGE_WAIT_STATE


def test_numeric_photo_menu_choices_override_stale_media_metadata():
    assert image_evidence_patch._is_confirmation_choice('1') is True
    assert image_evidence_patch._is_confirmation_choice('2') is True
    assert image_evidence_patch._is_evidence_action_choice('1') is True
    assert image_evidence_patch._is_evidence_action_choice('2') is True


def test_natural_add_change_choices_override_stale_media_metadata():
    assert image_evidence_patch._is_evidence_action_choice('Agregar') is True
    assert image_evidence_patch._is_evidence_action_choice('Cambiar') is True
    assert image_evidence_patch._is_evidence_action_choice('Reemplazar foto') is True


def test_configured_image_commands_are_exact_and_editable():
    assert image_evidence_patch._command_matches('1', '1, sí, correcta')
    assert image_evidence_patch._command_matches('Agregar', '1, agregar, otra evidencia')
    assert not image_evidence_patch._command_matches('cambiar', '1, agregar')


def test_ticket_mode_detection_for_image_flow():
    class Ticket:
        subject = 'Incidencia preciador'
        description = 'Etiqueta sin precio'
    assert image_evidence_patch._image_mode_from_ticket(Ticket()) == 'preciadores'


def test_ticket_close_path_uses_nonblocking_side_effect_policy():
    import inspect
    from app.routers import case_event_policy_patch

    # At runtime ticketing.close_ticket is intentionally monkey-patched to the
    # milestone policy wrapper. Validate both layers instead of inspecting only
    # the rebound public symbol.
    policy_source = inspect.getsource(case_event_policy_patch._policy_close_ticket)
    original_source = inspect.getsource(case_event_policy_patch._original_close_ticket)

    assert 'case_event_email_error' in policy_source
    assert 'case_learning_error' in policy_source
    assert 'except Exception as exc' in policy_source
    assert 'ticket_close_notification_error' in original_source
    assert 'notify_ticket' in original_source
    assert 'except Exception as exc' in original_source


def test_close_result_is_truncated_to_database_limit():
    import inspect
    from app.routers import case_event_policy_patch
    source = inspect.getsource(case_event_policy_patch._original_close_ticket)
    assert "ticket.close_result = normalized_result[:30]" in source


def test_image_flow_has_runtime_error_capture_and_option2_recovery():
    import inspect
    source = inspect.getsource(image_evidence_patch.image_evidence_inbound)
    assert '_record_image_flow_error' in source
    assert '_fallback_confirmation_no' in source
    assert 'confirm_image_choice' in source


def test_image_flow_route_trace_is_present():
    import inspect
    source = inspect.getsource(image_evidence_patch._trace_flow)
    assert "flow_route_trace" in source
    endpoint = inspect.getsource(image_evidence_patch.image_evidence_inbound)
    assert "inbound_received" in endpoint
    assert "route_selected" in endpoint


def test_ticket_close_side_effects_are_isolated_by_savepoints():
    import inspect
    from app.routers import case_event_policy_patch
    source = inspect.getsource(case_event_policy_patch._policy_close_ticket)
    original = inspect.getsource(case_event_policy_patch._original_close_ticket)
    assert 'with db.begin_nested()' in source
    assert 'with db.begin_nested()' in original


def test_image_confirmation_routes_to_review_trace():
    import inspect
    source = inspect.getsource(image_evidence_patch._handle_confirmation_reply)
    assert "stage='route_selected'" in source
    assert "action='mostrar_resumen_revision'" in source
    assert "next_node='revision_datos_reporte'" in source
    assert "result='ok'" in source


def test_photo_yes_routes_to_report_review_instead_of_closing():
    import inspect
    source = inspect.getsource(image_evidence_patch._handle_confirmation_reply)
    assert 'IMAGE_REPORT_REVIEW_STATE' in source
    assert 'mostrar_resumen_revision' in source
    assert '_close_for_validation' not in source


def test_report_review_confirmation_keeps_ticket_open_for_review():
    import inspect
    source = inspect.getsource(image_evidence_patch._handle_report_review_reply)
    assert "ticket.status = 'open'" in source
    assert "status_label='En revisión'" in source
    assert 'Estado: ABIERTO' in source


def test_report_edit_menu_contains_required_fields():
    text = image_evidence_patch._edit_fields_text()
    for expected in ('Motivo del reporte','Motivo del problema','Evidencia / fotos','Número de contacto','Nombre de tienda y empresa','Nombre de quien se comunica','Fecha'):
        assert expected in text
