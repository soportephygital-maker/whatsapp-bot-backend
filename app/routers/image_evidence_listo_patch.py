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


def _latest_outbound_text(db: Session, conversation_id: int) -> str:
    row = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'outbound',
    ).order_by(Message.id.desc()).first()
    return str(row.body or '') if row else ''


def _recover_image_state(db: Session, conversation) -> str | None:
    """Recover an image-flow state when a legacy tree response moved it away.

    The visible bot prompt is authoritative. This lets an already-open
    conversation recover without asking the user to delete/restart the ticket.
    """
    if not conversation:
        return None

    text = _latest_outbound_text(db, conversation.id).lower()
    recovered = None

    if '¿esta foto es la correcta?' in text or 'esta foto es la correcta?' in text:
        recovered = image_evidence_patch.IMAGE_CONFIRM_STATE
    elif '¿desea agregar o cambiar la foto?' in text or 'desea agregar o cambiar la foto?' in text:
        recovered = image_evidence_patch.IMAGE_EVIDENCE_ACTION_STATE
    elif 'envía la nueva evidencia que deseas agregar' in text or 'envia la nueva evidencia que deseas agregar' in text:
        recovered = image_evidence_patch.IMAGE_WAIT_STATE
    elif 'envía ahora la nueva foto' in text or 'envia ahora la nueva foto' in text:
        recovered = image_evidence_patch.IMAGE_WAIT_STATE

    if recovered and conversation.state != recovered:
        conversation.status = 'open'
        conversation.state = recovered
        db.flush()
    return recovered


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
