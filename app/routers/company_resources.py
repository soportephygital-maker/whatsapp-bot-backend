from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import AuditLog, Company, CompanyFile, Contact, SupportContact, User
from ..schemas import SupportContactCreate
from ..services.classifier import normalize_phone

router = APIRouter(prefix='/api/empresas', tags=['company-resources'])
MAX_FILE_BYTES = 10 * 1024 * 1024


def _company(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


@router.get('/{company_key}/archivos')
def list_files(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    rows = db.query(CompanyFile).filter(CompanyFile.company_id == company.id).order_by(CompanyFile.created_at.desc()).all()
    return [{'id': r.id, 'filename': r.filename, 'content_type': r.content_type, 'size_bytes': r.size_bytes, 'description': r.description, 'uploaded_by': r.uploaded_by, 'created_at': r.created_at} for r in rows]


@router.post('/{company_key}/archivos')
async def upload_file(
    company_key: str,
    file: UploadFile = File(...),
    description: str = Form(default=''),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = _company(company_key, db)
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail='Archivo demasiado grande. Máximo 10 MB')
    row = CompanyFile(
        company_id=company.id,
        filename=(file.filename or 'archivo').strip()[:255],
        content_type=(file.content_type or 'application/octet-stream')[:120],
        size_bytes=len(data),
        description=description.strip()[:500] or None,
        data=data,
        uploaded_by=admin.username,
    )
    db.add(row)
    db.flush()
    db.add(AuditLog(username=admin.username, action='subir_archivo', entity='company_file', entity_id=str(row.id), details={'company': company_key, 'filename': row.filename}))
    db.commit()
    return {'status': 'ok', 'id': row.id, 'filename': row.filename}


@router.get('/{company_key}/archivos/{file_id}/descargar')
def download_file(company_key: str, file_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    row = db.query(CompanyFile).filter(CompanyFile.id == file_id, CompanyFile.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Archivo no encontrado')
    safe_name = row.filename.replace('"', '')
    return Response(content=row.data, media_type=row.content_type, headers={'Content-Disposition': f'attachment; filename="{safe_name}"'})


@router.delete('/{company_key}/archivos/{file_id}')
def delete_file(company_key: str, file_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    row = db.query(CompanyFile).filter(CompanyFile.id == file_id, CompanyFile.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Archivo no encontrado')
    db.delete(row)
    db.add(AuditLog(username=admin.username, action='eliminar_archivo', entity='company_file', entity_id=str(file_id), details={'company': company_key}))
    db.commit()
    return {'status': 'ok'}


@router.get('/{company_key}/soporte')
def list_support(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    rows = db.query(SupportContact).filter(SupportContact.company_id == company.id, SupportContact.is_active.is_(True)).order_by(SupportContact.role.asc(), SupportContact.priority.asc()).all()
    return [{'id': r.id, 'name': r.name, 'phone': r.phone, 'role': r.role, 'priority': r.priority, 'escalation_after_minutes': r.escalation_after_minutes} for r in rows]


@router.post('/{company_key}/soporte')
def add_support(company_key: str, data: SupportContactCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    phone = normalize_phone(data.phone)
    if not phone:
        raise HTTPException(status_code=422, detail='Teléfono inválido')
    contact = db.query(Contact).filter(Contact.phone == phone, Contact.is_active.is_(True)).first()
    if not contact:
        raise HTTPException(status_code=400, detail='Este número no está en Contactos autorizados. Primero agrégalo desde la app del administrador.')
    row = SupportContact(
        company_id=company.id,
        contact_id=contact.id,
        name=data.name.strip() or contact.display_name or phone,
        phone=phone,
        role=data.role,
        priority=data.priority,
        escalation_after_minutes=data.escalation_after_minutes,
    )
    db.add(row)
    db.flush()
    db.add(AuditLog(username=admin.username, action='agregar_soporte', entity='support_contact', entity_id=str(row.id), details={'company': company_key, 'role': row.role, 'phone': phone, 'authorized_contact_id': contact.id}))
    db.commit()
    return {'status': 'ok', 'id': row.id, 'authorized_contact': True}


@router.delete('/{company_key}/soporte/{support_id}')
def delete_support(company_key: str, support_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    row = db.query(SupportContact).filter(SupportContact.id == support_id, SupportContact.company_id == company.id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Contacto de soporte no encontrado')
    row.is_active = False
    db.add(AuditLog(username=admin.username, action='desactivar_soporte', entity='support_contact', entity_id=str(row.id), details={'company': company_key}))
    db.commit()
    return {'status': 'ok'}
