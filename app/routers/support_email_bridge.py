from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import AuditLog, Company, SupportContact, SupportEmailRecipient, User
from ..services.ticketing import _send_email

router = APIRouter(prefix='/api/empresas', tags=['support-email-bridge'])


class SupportPersonEmailUpdate(BaseModel):
    email: str = Field(min_length=5, max_length=254)


def _company(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if '@' not in email or email.startswith('@') or email.endswith('@'):
        raise HTTPException(status_code=422, detail='Correo inválido')
    return email


@router.get('/{company_key}/personal-soporte-correos')
def support_people_emails(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    contacts = db.query(SupportContact).filter(
        SupportContact.company_id == company.id,
        SupportContact.is_active.is_(True),
    ).order_by(SupportContact.role.asc(), SupportContact.priority.asc()).all()
    recipients = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company.id,
        SupportEmailRecipient.is_active.is_(True),
    ).all()
    by_name = {r.name.strip().lower(): r for r in recipients}
    return [
        {
            'support_id': row.id,
            'name': row.name,
            'phone': row.phone,
            'role': row.role,
            'priority': row.priority,
            'email': by_name.get(row.name.strip().lower()).email if by_name.get(row.name.strip().lower()) else '',
        }
        for row in contacts
    ]


@router.put('/{company_key}/personal-soporte-correos/{support_id}')
def set_support_person_email(
    company_key: str,
    support_id: int,
    data: SupportPersonEmailUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = _company(company_key, db)
    support = db.query(SupportContact).filter(
        SupportContact.id == support_id,
        SupportContact.company_id == company.id,
        SupportContact.is_active.is_(True),
    ).first()
    if not support:
        raise HTTPException(status_code=404, detail='Personal de soporte no encontrado')
    email = _normalize_email(data.email)
    row = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company.id,
        SupportEmailRecipient.name == support.name,
        SupportEmailRecipient.is_active.is_(True),
    ).first()
    if row:
        row.email = email
    else:
        row = SupportEmailRecipient(company_id=company.id, name=support.name, email=email, is_active=True)
        db.add(row)
        db.flush()
    db.add(AuditLog(
        username=admin.username,
        action='asignar_correo_personal_soporte',
        entity='support_email_recipient',
        entity_id=str(row.id),
        details={'company': company_key, 'support_id': support.id, 'name': support.name, 'email': email},
    ))
    db.commit()
    return {'status': 'ok', 'support_id': support.id, 'name': support.name, 'email': email}


@router.post('/{company_key}/correo-prueba-soporte')
def test_support_email(company_key: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    recipients = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company.id,
        SupportEmailRecipient.is_active.is_(True),
    ).order_by(SupportEmailRecipient.name.asc()).all()
    emails = [r.email for r in recipients]
    if not emails:
        raise HTTPException(status_code=409, detail='No hay correos configurados para el personal de soporte de esta empresa.')
    sent, result = _send_email(
        f'[Phygital Bot] Prueba de correo - {company.name}',
        'Este es un correo de prueba del sistema Phygital Bot. Si recibiste este mensaje, la conexión SMTP y la lista de destinatarios están funcionando correctamente.',
        emails,
    )
    db.add(AuditLog(
        username=admin.username,
        action='smtp_support_test_sent' if sent else 'smtp_support_test_failed',
        entity='company',
        entity_id=str(company.id),
        details={'company': company_key, 'recipients': emails, 'result': result},
    ))
    db.commit()
    if not sent:
        raise HTTPException(status_code=502, detail=f'No se pudo enviar el correo: {result}')
    return {'status': 'ok', 'recipients': emails, 'result': result}
