from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import AuditLog, Company, CompanyFile, Conversation, ConversationChannel, HelpRequest, Store, SupportContact, User
from ..services.company_routing import base_decision_tree

router = APIRouter(prefix='/api/empresas', tags=['empresas'])


def _is_default_store(store: Store) -> bool:
    return (
        (store.name or '').strip().lower() == 'principal'
        and not (store.whatsapp_number or '').strip()
        and not (store.whatsapp_phone_number_id or '').strip()
    )


def _delete_if_empty(company: Company, admin: User, db: Session):
    reasons: list[str] = []
    if db.query(Conversation).filter(Conversation.company_id == company.id).first():
        reasons.append('conversaciones')
    if db.query(ConversationChannel).filter(ConversationChannel.company_id == company.id).first():
        reasons.append('canales de conversación')
    if db.query(HelpRequest).filter(HelpRequest.company_id == company.id).first():
        reasons.append('solicitudes de ayuda')
    if db.query(SupportContact).filter(SupportContact.company_id == company.id).first():
        reasons.append('contactos de soporte')
    if db.query(CompanyFile).filter(CompanyFile.company_id == company.id).first():
        reasons.append('archivos')

    stores = db.query(Store).filter(Store.company_id == company.id).all()
    if len(stores) > 1 or any(not _is_default_store(store) for store in stores):
        reasons.append('tiendas configuradas')

    current_tree = company.decision_tree or {}
    if current_tree and current_tree != base_decision_tree():
        reasons.append('árbol de decisiones configurado')

    if reasons:
        raise HTTPException(
            status_code=409,
            detail='No se puede eliminar esta cadena porque ya contiene ' + ', '.join(reasons) + '. Puedes desactivarla si ya no la usarás.',
        )

    company_key = company.company_key
    company_name = company.name
    company_id = company.id
    for store in stores:
        db.delete(store)
    db.delete(company)
    db.add(AuditLog(
        username=admin.username,
        action='eliminar_empresa_vacia',
        entity='company',
        entity_id=str(company_id),
        details={'company_key': company_key, 'company_name': company_name},
    ))
    db.commit()
    return {'status': 'ok', 'deleted_company': company_key, 'deleted_company_id': company_id}


@router.delete('/eliminar-vacia/{company_key}')
def delete_empty_company(
    company_key: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return _delete_if_empty(company, admin, db)


@router.delete('/eliminar-vacia-id/{company_id}')
def delete_empty_company_by_id(
    company_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return _delete_if_empty(company, admin, db)
