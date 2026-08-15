from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..database import get_db
from ..models import Company, Contact, Conversation, HelpRequest, Message, User
from ..schemas import HelpRequestStatus

router = APIRouter(prefix='/api', tags=['dashboard'])


@router.get('/stats')
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        'empresas': db.query(func.count(Company.id)).scalar() or 0,
        'contactos': db.query(func.count(Contact.id)).filter(Contact.is_active.is_(True)).scalar() or 0,
        'conversaciones': db.query(func.count(Conversation.id)).scalar() or 0,
        'mensajes': db.query(func.count(Message.id)).scalar() or 0,
        'solicitudes_ayuda_nuevas': db.query(func.count(HelpRequest.id)).filter(HelpRequest.status == 'new').scalar() or 0,
    }


@router.get('/conversaciones')
def conversations(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(100).all()
    contact_phones = {c.phone for c in db.query(Contact).filter(Contact.is_active.is_(True)).all()}
    return [{'id': c.id, 'wa_user_id': c.wa_user_id, 'known_contact': ''.join(ch for ch in c.wa_user_id if ch.isdigit()) in contact_phones, 'state': c.state, 'status': c.status, 'updated_at': c.updated_at} for c in rows]


@router.get('/help-requests')
def help_requests(status: str | None = Query(default=None), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(HelpRequest)
    if status:
        query = query.filter(HelpRequest.status == status)
    rows = query.order_by(HelpRequest.created_at.desc()).limit(200).all()
    return [{'id': r.id, 'wa_user_id': r.wa_user_id, 'body': r.body, 'status': r.status, 'known_contact': r.is_known_contact, 'is_group': r.is_group, 'created_at': r.created_at} for r in rows]


@router.patch('/help-requests/{request_id}')
def update_help_request(request_id: int, data: HelpRequestStatus, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(HelpRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail='Solicitud no encontrada')
    row.status = data.status
    db.commit()
    return {'status': 'ok', 'id': row.id, 'request_status': row.status}
