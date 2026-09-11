from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Company, SupportEmailRecipient, User
from .super_admin import require_super_admin

router = APIRouter(prefix='/api/super-admin', tags=['super-admin-email'])


class EmailRecipientPauseUpdate(BaseModel):
    paused: bool


@router.get('/email-recipients')
def list_email_recipients(_: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    rows = db.query(SupportEmailRecipient, Company).join(
        Company, Company.id == SupportEmailRecipient.company_id
    ).order_by(Company.name.asc(), SupportEmailRecipient.name.asc(), SupportEmailRecipient.email.asc()).all()
    return [{
        'id': recipient.id,
        'company_id': company.id,
        'company_key': company.company_key,
        'company_name': company.name,
        'name': recipient.name,
        'email': recipient.email,
        'paused': not bool(recipient.is_active),
        'is_active': bool(recipient.is_active),
        'created_at': recipient.created_at,
    } for recipient, company in rows]


@router.patch('/email-recipients/{recipient_id}/pause')
def set_email_recipient_pause(
    recipient_id: int,
    data: EmailRecipientPauseUpdate,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    recipient = db.get(SupportEmailRecipient, recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail='Destinatario de correo no encontrado')

    recipient.is_active = not data.paused
    company = db.get(Company, recipient.company_id)
    db.add(AuditLog(
        username=admin.username,
        action='pausar_destinatario_correo' if data.paused else 'reanudar_destinatario_correo',
        entity='support_email_recipient',
        entity_id=str(recipient.id),
        details={
            'company': company.company_key if company else None,
            'company_name': company.name if company else None,
            'name': recipient.name,
            'email': recipient.email,
            'paused': data.paused,
        },
    ))
    db.commit()
    return {
        'status': 'ok',
        'id': recipient.id,
        'name': recipient.name,
        'email': recipient.email,
        'paused': not recipient.is_active,
        'is_active': recipient.is_active,
    }
