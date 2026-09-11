from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Company, SupportEmailRecipient, User
from .super_admin import require_super_admin

router = APIRouter(prefix='/api/super-admin', tags=['super-admin-email'])


class EmailRecipientPauseUpdate(BaseModel):
    paused: bool


class EmailRecipientCreate(BaseModel):
    company_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=5, max_length=254)


class EmailRecipientEdit(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=5, max_length=254)


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if '@' not in email or email.startswith('@') or email.endswith('@'):
        raise HTTPException(status_code=422, detail='Correo inválido')
    return email


def _company_or_404(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


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


@router.post('/email-recipients')
def create_email_recipient(
    data: EmailRecipientCreate,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    company = _company_or_404(data.company_key.strip(), db)
    name = data.name.strip()
    email = _normalize_email(data.email)
    duplicate = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company.id,
        SupportEmailRecipient.email == email,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail='Ese correo ya está registrado para esta empresa')
    recipient = SupportEmailRecipient(
        company_id=company.id,
        name=name,
        email=email,
        is_active=True,
    )
    db.add(recipient)
    db.flush()
    db.add(AuditLog(
        username=admin.username,
        action='crear_destinatario_correo',
        entity='support_email_recipient',
        entity_id=str(recipient.id),
        details={'company': company.company_key, 'name': name, 'email': email},
    ))
    db.commit()
    db.refresh(recipient)
    return {
        'status': 'ok',
        'id': recipient.id,
        'company_key': company.company_key,
        'company_name': company.name,
        'name': recipient.name,
        'email': recipient.email,
        'paused': False,
        'is_active': True,
    }


@router.patch('/email-recipients/{recipient_id}')
def edit_email_recipient(
    recipient_id: int,
    data: EmailRecipientEdit,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    recipient = db.get(SupportEmailRecipient, recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail='Destinatario de correo no encontrado')
    name = data.name.strip()
    email = _normalize_email(data.email)
    duplicate = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == recipient.company_id,
        SupportEmailRecipient.email == email,
        SupportEmailRecipient.id != recipient.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail='Ese correo ya está registrado para esta empresa')
    before = {'name': recipient.name, 'email': recipient.email}
    recipient.name = name
    recipient.email = email
    company = db.get(Company, recipient.company_id)
    db.add(AuditLog(
        username=admin.username,
        action='editar_destinatario_correo',
        entity='support_email_recipient',
        entity_id=str(recipient.id),
        details={
            'company': company.company_key if company else None,
            'before': before,
            'after': {'name': name, 'email': email},
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
