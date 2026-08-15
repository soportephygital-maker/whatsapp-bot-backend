from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import AuditLog, Company, Store, User
from ..schemas import CompanyCreate, DecisionTreeUpdate

router = APIRouter(prefix='/api/empresas', tags=['empresas'])

@router.get('/listar')
def list_companies(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    companies = db.query(Company).filter(Company.is_active.is_(True)).all()
    return [{
        'id': c.id,
        'empresa_id': c.company_key,
        'nombre': c.name,
        'tiendas': [{'id': s.id, 'nombre': s.name, 'whatsapp': s.whatsapp_number} for s in c.stores],
        'arbol_decisiones': c.decision_tree,
    } for c in companies]

@router.post('/crear')
def create_company(data: CompanyCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Company).filter(Company.company_key == data.company_key).first():
        raise HTTPException(status_code=409, detail='La empresa ya existe')
    company = Company(company_key=data.company_key, name=data.name, decision_tree={})
    db.add(company)
    db.flush()
    count = max(len(data.stores), len(data.whatsapp_numbers))
    for i in range(count):
        name = data.stores[i] if i < len(data.stores) else f'Tienda {i + 1}'
        number = data.whatsapp_numbers[i] if i < len(data.whatsapp_numbers) else None
        db.add(Store(company_id=company.id, name=name.strip(), whatsapp_number=(number or '').strip() or None))
    db.add(AuditLog(username=admin.username, action='crear_empresa', entity='company', entity_id=data.company_key))
    db.commit()
    return {'status': 'ok', 'empresa_id': company.company_key}

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
