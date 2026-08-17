from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import AuditLog, Company, Contact, Conversation, HelpRequest, Message, User
from ..schemas import HelpRequestStatus, UIAuditEvent

router = APIRouter(prefix='/api', tags=['dashboard'])


@router.get('/stats')
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        'empresas': db.query(func.count(Company.id)).filter(Company.is_active.is_(True)).scalar() or 0,
        'contactos': db.query(func.count(Contact.id)).filter(Contact.is_active.is_(True)).scalar() or 0,
        'conversaciones': db.query(func.count(Conversation.id)).scalar() or 0,
        'mensajes': db.query(func.count(Message.id)).scalar() or 0,
        'solicitudes_ayuda_nuevas': db.query(func.count(HelpRequest.id)).filter(HelpRequest.status == 'new').scalar() or 0,
    }


@router.get('/conversaciones')
def conversations(
    company_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Conversation)
    if company_id is not None:
        query = query.filter(Conversation.company_id == company_id)
    rows = query.order_by(Conversation.updated_at.desc()).limit(200).all()
    contact_phones = {c.phone for c in db.query(Contact).filter(Contact.is_active.is_(True)).all()}
    companies = {c.id: c.name for c in db.query(Company).all()}
    return [{
        'id': c.id,
        'company_id': c.company_id,
        'company_name': companies.get(c.company_id, 'Sin empresa'),
        'wa_user_id': c.wa_user_id,
        'known_contact': ''.join(ch for ch in c.wa_user_id if ch.isdigit()) in contact_phones,
        'state': c.state,
        'status': c.status,
        'updated_at': c.updated_at,
    } for c in rows]


@router.get('/help-requests')
def help_requests(
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(HelpRequest)
    if status:
        query = query.filter(HelpRequest.status == status)
    if company_id is not None:
        query = query.filter(HelpRequest.company_id == company_id)
    rows = query.order_by(HelpRequest.created_at.desc()).limit(200).all()
    companies = {c.id: c.name for c in db.query(Company).all()}
    return [{
        'id': r.id,
        'company_id': r.company_id,
        'company_name': companies.get(r.company_id, 'Sin empresa'),
        'wa_user_id': r.wa_user_id,
        'body': r.body,
        'status': r.status,
        'known_contact': r.is_known_contact,
        'is_group': r.is_group,
        'created_at': r.created_at,
    } for r in rows]


@router.patch('/help-requests/{request_id}')
def update_help_request(request_id: int, data: HelpRequestStatus, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(HelpRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail='Solicitud no encontrada')
    previous = row.status
    row.status = data.status
    db.add(AuditLog(
        username=user.username,
        action='actualizar_solicitud_ayuda',
        entity='help_request',
        entity_id=str(row.id),
        details={'status_before': previous, 'status_after': row.status, 'wa_user_id': row.wa_user_id},
    ))
    db.commit()
    return {'status': 'ok', 'id': row.id, 'request_status': row.status}


@router.post('/audit/ui-events')
def audit_ui_event(event: UIAuditEvent, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    details = {
        'element_id': event.element_id,
        'label': event.label,
        'path': event.path,
    }
    db.add(AuditLog(username=user.username, action=event.action, entity='ui', details=details))
    db.commit()
    return {'status': 'ok'}


@router.get('/audit/activity')
def audit_activity(
    username: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if username:
        query = query.filter(AuditLog.username == username)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{
        'id': row.id,
        'username': row.username,
        'action': row.action,
        'entity': row.entity,
        'entity_id': row.entity_id,
        'details': row.details or {},
        'created_at': row.created_at,
    } for row in rows]
