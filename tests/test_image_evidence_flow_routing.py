from app.routers import image_evidence_listo_patch, image_evidence_patch


def test_active_image_states_are_owned_by_image_flow():
    assert image_evidence_patch.IMAGE_CONFIRM_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_EVIDENCE_ACTION_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_WAIT_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_INCIDENT_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES
    assert image_evidence_patch.IMAGE_MORE_PROBLEM_STATE in image_evidence_listo_patch.ACTIVE_IMAGE_STATES


def test_photo_confirmation_menu_is_the_close_or_evidence_branch():
    text = image_evidence_patch.IMAGE_CONFIRM_TEXT
    assert '1️⃣ Sí, cerrar el ticket con esta evidencia' in text
    assert '2️⃣ No, agregar o cambiar la foto' in text


def test_second_evidence_menu_is_add_or_change():
    text = image_evidence_patch.IMAGE_EVIDENCE_ACTION_TEXT
    assert '1️⃣ Agregar' in text
    assert '2️⃣ Cambiar' in text
