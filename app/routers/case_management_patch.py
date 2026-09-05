import io
import os
import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin, require_operator
from ..database import get_db
from ..models import AIAdminMessage, AILearningPoint, CaseAttachment, Company, Conversation, Message, Store, SupportTicket, User
from ..services.ai_learning import admin_chat, learning_status
from ..services.case_event_notifications import send_case_event_email
from ..services.case_reports import build_chat_pdf, build_summary_pdf
from ..services.ticketing import add_ticket_followup, ticket_code, ticket_dict, ticket_tracking

router = APIRouter(prefix='/api', tags=['case-management'])
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


class TicketFollowupCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    status_label: str = Field(default='En atención', min_length=1, max_length=80)


class LearningDecision(BaseModel):
    status: str = Field(pattern='^(approved|rejected|pending)$')
    problem: str | None = Field(default=None, max_length=4000)
    solution: str | None = Field(default=None, max_length=4000)
    confidence: int | None = Field(default=None, ge=0, le=100)


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    company_id: int | None = None


def _ticket_or_404(ticket_id: int, db: Session) -> SupportTicket:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail='Ticket no encontrado')
    return ticket


def _ticket_context(ticket: SupportTicket, db: Session):
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    conversation = db.get(Conversation, ticket.conversation_id)
    return company, store, conversation


def _primary_admin(user: User) -> User:
    expected = (os.getenv('BOOTSTRAP_ADMIN_USERNAME') or '').strip()
    if user.role != 'admin' or (expected and user.username != expected):
        raise HTTPException(status_code=403, detail='Esta sección es exclusiva del administrador principal')
    return user


@router.post('/tickets/{ticket_id}/seguimiento')
def add_followup_with_email(ticket_id: int, data: TicketFollowupCreate, operator: User = Depends(require_operator), db: Session = Depends(get_db)):
    ticket = _ticket_or_404(ticket_id, db)
    previous = ticket_tracking(db, ticket).get('status_label')
    add_ticket_followup(db, ticket=ticket, username=operator.username, message=data.message, status_label=data.status_label)
    db.flush()
    if str(previous or '').strip().lower() != data.status_label.strip().lower():
        send_case_event_email(db, ticket=ticket, event='status_changed')
    db.commit()
    company, store, _ = _ticket_context(ticket, db)
    return ticket_dict(ticket, company, store, db=db)


@router.get('/tickets/{ticket_id}/adjuntos')
def list_attachments(ticket_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ticket_or_404(ticket_id, db)
    rows = db.query(CaseAttachment).filter(CaseAttachment.ticket_id == ticket_id).order_by(CaseAttachment.created_at.asc()).all()
    return [{'id': r.id, 'message_id': r.message_id, 'filename': r.filename, 'content_type': r.content_type, 'size_bytes': r.size_bytes, 'source': r.source, 'uploaded_by': r.uploaded_by, 'created_at': r.created_at} for r in rows]


@router.post('/tickets/{ticket_id}/adjuntos')
async def upload_attachment(ticket_id: int, file: UploadFile = File(...), message_id: int | None = None, operator: User = Depends(require_operator), db: Session = Depends(get_db)):
    ticket = _ticket_or_404(ticket_id, db)
    data = await file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail='El archivo excede 15 MB')
    if message_id:
        message = db.get(Message, message_id)
        if not message or message.conversation_id != ticket.conversation_id:
            raise HTTPException(status_code=422, detail='El mensaje no pertenece a este caso')
    row = CaseAttachment(ticket_id=ticket.id, message_id=message_id, filename=(file.filename or 'archivo')[:255], content_type=(file.content_type or 'application/octet-stream')[:120], size_bytes=len(data), data=data, source='dashboard', uploaded_by=operator.username)
    db.add(row); db.commit(); db.refresh(row)
    return {'status': 'ok', 'id': row.id, 'filename': row.filename, 'size_bytes': row.size_bytes}


@router.get('/tickets/{ticket_id}/adjuntos/{attachment_id}')
def download_attachment(ticket_id: int, attachment_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(CaseAttachment).filter(CaseAttachment.id == attachment_id, CaseAttachment.ticket_id == ticket_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Adjunto no encontrado')
    return Response(row.data, media_type=row.content_type, headers={'Content-Disposition': f'attachment; filename="{row.filename}"'})


@router.get('/tickets/{ticket_id}/chat.pdf')
def ticket_chat_pdf(ticket_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = _ticket_or_404(ticket_id, db)
    company, store, conversation = _ticket_context(ticket, db)
    code = ticket_code(ticket, company, store)
    data = build_chat_pdf(db, ticket=ticket, company=company, store=store, conversation=conversation, code=code)
    return Response(data, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{code}-chat-completo.pdf"'})


@router.get('/tickets/{ticket_id}/resumen.pdf')
def ticket_summary_pdf(ticket_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = _ticket_or_404(ticket_id, db)
    company, store, conversation = _ticket_context(ticket, db)
    code = ticket_code(ticket, company, store)
    data = build_summary_pdf(db, ticket=ticket, company=company, store=store, conversation=conversation, code=code)
    return Response(data, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{code}-resumen.pdf"'})


@router.get('/tickets/{ticket_id}/expediente.zip')
def ticket_archive(ticket_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = _ticket_or_404(ticket_id, db)
    company, store, conversation = _ticket_context(ticket, db)
    code = ticket_code(ticket, company, store)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{code}-chat-completo.pdf', build_chat_pdf(db, ticket=ticket, company=company, store=store, conversation=conversation, code=code))
        z.writestr(f'{code}-resumen.pdf', build_summary_pdf(db, ticket=ticket, company=company, store=store, conversation=conversation, code=code))
        rows = db.query(CaseAttachment).filter(CaseAttachment.ticket_id == ticket.id).order_by(CaseAttachment.id.asc()).all()
        for row in rows:
            safe = row.filename.replace('/', '_').replace('\\', '_')
            z.writestr(f'adjuntos/{row.id:04d}-{safe}', row.data)
    return Response(out.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{code}-expediente.zip"'})


@router.get('/admin-ai/status')
def ai_status(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _primary_admin(admin)
    status = learning_status(db)
    status['recent_points'] = [{'id': r.id, 'company_id': r.company_id, 'ticket_id': r.ticket_id, 'problem': r.problem, 'solution': r.solution, 'confidence': r.confidence, 'status': r.status} for r in db.query(AILearningPoint).order_by(AILearningPoint.id.desc()).limit(30).all()]
    return status


@router.patch('/admin-ai/learning/{point_id}')
def update_learning(point_id: int, data: LearningDecision, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _primary_admin(admin)
    row = db.get(AILearningPoint, point_id)
    if not row:
        raise HTTPException(status_code=404, detail='Punto de aprendizaje no encontrado')
    row.status = data.status
    if data.problem is not None: row.problem = data.problem
    if data.solution is not None: row.solution = data.solution
    if data.confidence is not None: row.confidence = data.confidence
    row.approved_by = admin.username if data.status == 'approved' else None
    db.commit()
    return {'status': 'ok', 'point_id': row.id}


@router.post('/admin-ai/chat')
def ai_chat(data: AIChatRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _primary_admin(admin)
    try:
        result = admin_chat(db, username=admin.username, message=data.message, company_id=data.company_id)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f'No se pudo consultar la IA: {str(exc)[:300]}')


@router.get('/admin-ai/chat')
def ai_chat_history(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _primary_admin(admin)
    rows = db.query(AIAdminMessage).filter(AIAdminMessage.username == admin.username).order_by(AIAdminMessage.id.desc()).limit(80).all()
    return [{'id': r.id, 'role': r.role, 'body': r.body, 'created_at': r.created_at} for r in reversed(rows)]
