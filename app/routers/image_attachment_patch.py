from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import CaseAttachment, Message, SupportTicket, User

router = APIRouter(prefix='/api', tags=['case-image-attachments'])
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def _latest_image_message(db: Session, ticket: SupportTicket) -> Message | None:
    rows = db.query(Message).filter(
        Message.conversation_id == ticket.conversation_id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).limit(20).all()
    for row in rows:
        payload = row.raw_payload or {}
        metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
        if payload.get('image_evidence') or str(metadata.get('media_capture') or '').lower() == 'available' or metadata.get('media_source'):
            already_linked = db.query(CaseAttachment.id).filter(CaseAttachment.message_id == row.id).first()
            if not already_linked:
                return row
    return None


@router.post('/tickets/{ticket_id}/adjuntos')
async def upload_image_attachment(
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

    message = None
    if message_id:
        message = db.get(Message, message_id)
        if not message or message.conversation_id != ticket.conversation_id:
            raise HTTPException(status_code=422, detail='El mensaje no pertenece a este caso')
    elif str(file.content_type or '').lower().startswith('image/'):
        message = _latest_image_message(db, ticket)

    row = CaseAttachment(
        ticket_id=ticket.id,
        message_id=message.id if message else None,
        filename=(file.filename or 'imagen')[:255],
        content_type=(file.content_type or 'application/octet-stream')[:120],
        size_bytes=len(data),
        data=data,
        source='android_notification' if message else 'dashboard',
        uploaded_by=operator.username,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'status': 'ok',
        'id': row.id,
        'filename': row.filename,
        'size_bytes': row.size_bytes,
        'message_id': row.message_id,
        'source': row.source,
        'is_image': str(row.content_type or '').lower().startswith('image/'),
    }
