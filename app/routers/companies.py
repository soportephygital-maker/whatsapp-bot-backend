from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import AuditLog, Company, Store, User
from ..schemas import CompanyCreate, CompanyUpdate, DecisionTreeUpdate

router = APIRouter(prefix='/api/empresas', tags=['empresas'])


@router.get('/listar')
def list_companies(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    companies = db.query(Company).order_by(Company.name.asc()).all()
    return [{
        'id': c.id,
        'empresa_id': c.company_key,
        'nombre': c.name,
        'activa': c.is_active,
        'tiendas': [{'id': s.id, 'nombre': s.name, 'whatsapp': s.whatsapp_number, 'phone_number_id': s.whatsapp_phone_number_id} for s in c.stores],
        'arbol_decisiones': c.decision_tree,
    } for c in companies]


@router.post('/crear')
def create_company(data: CompanyCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Company).filter(Company.company_key == data.company_key).first():
        raise HTTPException(status_code=409, detail='La empresa ya existe')
    company = Company(company_key=data.company_key.strip(), name=data.name.strip(), decision_tree={})
    db.add(company)
    db.flush()
    count = max(len(data.stores), len(data.whatsapp_numbers), len(data.phone_number_ids))
    for i in range(count):
        name = data.stores[i] if i < len(data.stores) else f'Tienda {i + 1}'
        number = data.whatsapp_numbers[i] if i < len(data.whatsapp_numbers) else None
        phone_number_id = data.phone_number_ids[i] if i < len(data.phone_number_ids) else None
        db.add(Store(company_id=company.id, name=name.strip(), whatsapp_number=(number or '').strip() or None, whatsapp_phone_number_id=(phone_number_id or '').strip() or None))
    db.add(AuditLog(username=admin.username, action='crear_empresa', entity='company', entity_id=data.company_key))
    db.commit()
    return {'status': 'ok', 'empresa_id': company.company_key}


@router.patch('/{company_key}')
def update_company(company_key: str, data: CompanyUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    if data.name is not None:
        company.name = data.name.strip() or company.name
    if data.is_active is not None:
        company.is_active = data.is_active
    db.add(AuditLog(username=admin.username, action='actualizar_empresa', entity='company', entity_id=company_key, details={'name': company.name, 'is_active': company.is_active}))
    db.commit()
    return {'status': 'ok', 'empresa_id': company.company_key, 'nombre': company.name, 'activa': company.is_active}


@router.get('/{company_key}/arbol')
def get_tree(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company.decision_tree or {}


@router.put('/{company_key}/arbol')
def update_tree(company_key: str, data: DecisionTreeUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    company.decision_tree = data.structure
    db.add(AuditLog(username=admin.username, action='actualizar_arbol', entity='company', entity_id=company_key))
    db.commit()
    return {'status': 'ok'}
