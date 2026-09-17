from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Message, User
from . import image_evidence_patch, local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-image-finish'])

ACTIVE_IMAGE_STATES = {
    image_evidence_patch.IMAGE_CONFIRM_STATE,
    image_evidence_patch.IMAGE_EVIDENCE_ACTION_STATE,
    image_evidence_patch.IMAGE_WAIT_STATE,
    image_evidence_patch.IMAGE_INCIDENT_STATE,
    image_evidence_patch.IMAGE_MORE_PROBLEM_STATE,
}


def _state_from_prompt(text: str) -> str | None:
    low = str(text or '').lower()
    if '¿esta foto es la correcta?' in low or 'esta foto es la correcta?' in low:
        return image_evidence_patch.IMAGE_CONFIRM_STATE
    if '¿desea agregar o cambiar la foto?' in low or 'desea agregar o cambiar la foto?' in low:
        return image_evidence_patch.IMAGE_EVIDENCE_ACTION_STATE
    if 'envía la nueva evidencia que deseas agregar' in low or 'envia la nueva evidencia que deseas agregar' in low:
        return image_evidence_patch.IMAGE_WAIT_STATE
    if 'envía ahora la nueva foto' in low or 'envia ahora la nueva foto' in low:
        return image_evidence_patch.IMAGE_WAIT_STATE
    if '¿cómo sucedió el problema?' in low or 'como sucedio el problema?' in low:
        return image_evidence_patch.IMAGE_INCIDENT_STATE
    if '¿deseas reportar otro problema?' in low or 'deseas reportar otro problema?' in low:
        return image_evidence_patch.IMAGE_MORE_PROBLEM_STATE
    return None


def _recover_image_state(db: Session, conversation) -> str | None:
    """Recover the evidence flow even after a legacy tree message slipped in.

    The image audit proves that this conversation has an evidence session. We
    inspect recent bot prompts instead of only the last message, because an old
    generic-tree reply such as "No entendí" must not permanently steal the flow.
    """
    if not conversation:
        return None
    if conversation.state in ACTIVE_IMAGE_STATES:
        return conversation.state

    if not image_evidence_patch._latest_image_context(db, conversation.id):
        return None

    rows = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'outbound',
    ).order_by(Message.id.desc()).limit(12).all()

    for row in rows:
        low = str(row.body or '').lower()
        if (
            'estado: cerrado' in low
            or 'caso cerrado' in low
            or 'reporte quedó registrado correctamente' in low
            or 'reporte quedo registrado correctamente' in low
        ):
            break
        recovered = _state_from_prompt(row.body or '')
        if recovered:
            conversation.status = 'open'
            conversation.state = recovered
            db.flush()
            return recovered
    return None


@router.post('/inbound')
def image_evidence_finish_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    _, conversation, _, _, _ = image_evidence_patch._active_context(db, data)

    # New image evidence flow always owns its replies. Never let the legacy
    # decision tree consume 1/2, cerrar, finalizar or listo while a photo prompt
    # is active.
    _recover_image_state(db, conversation)
    if conversation and conversation.state in ACTIVE_IMAGE_STATES:
        return image_evidence_patch.image_evidence_inbound(
            data=data,
            operator=operator,
            db=db,
        )

    # Compatibility wrapper only: all non-image traffic continues to the normal
    # image router, which delegates to the global/company decision tree.
    return image_evidence_patch.image_evidence_inbound(
        data=data,
        operator=operator,
        db=db,
    )
