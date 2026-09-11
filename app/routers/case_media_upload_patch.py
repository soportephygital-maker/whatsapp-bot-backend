from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import CaseAttachment, Message, SupportTicket, User

router = APIRouter(prefix='/api', tags=['case-media-upload'])
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def _latest_unlinked_image_message(db: Session, ticket: SupportTicket) -> Message | None:
    rows = db.query(Message).filter(
        Message.conversation_id == ticket.conversation_id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).limit(40).all()
    for row in rows:
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
        is_image = bool(payload.get('image_evidence')) or str(metadata.get('media_capture') or '').lower() in {'available', 'detected'} or bool(metadata.get('media_source'))
        if not is_image:
            continue
        linked = db.query(CaseAttachment.id).filter(CaseAttachment.message_id == row.id).first()
        if not linked:
            return row
    return None


@router.post('/tickets/{ticket_id}/adjuntos')
async def upload_case_media(
    ticket_id: int,
    file: UploadFile = File(...),
    message_id: int | None = None,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail='Ticket no encontrado')

    data = await file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail='El archivo excede 15 MB')
    if not data:
        raise HTTPException(status_code=422, detail='El archivo está vacío')

    content_type = (file.content_type or 'application/octet-stream')[:120]
    is_image = content_type.lower().startswith('image/')
    message = None
    if message_id:
        message = db.get(Message, message_id)
        if not message or message.conversation_id != ticket.conversation_id:
            raise HTTPException(status_code=422, detail='El mensaje no pertenece a este caso')
    elif is_image:
        message = _latest_unlinked_image_message(db, ticket)

    row = CaseAttachment(
        ticket_id=ticket.id,
        message_id=message.id if message else None,
        filename=(file.filename or ('evidencia.jpg' if is_image else 'archivo'))[:255],
        content_type=content_type,
        size_bytes=len(data),
        data=data,
        source='android_notification' if is_image else 'dashboard',
        uploaded_by=operator.username,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'status': 'ok',
        'id': row.id,
        'filename': row.filename,
        'content_type': row.content_type,
        'size_bytes': row.size_bytes,
        'message_id': row.message_id,
        'source': row.source,
        'is_image': is_image,
    }
