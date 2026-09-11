from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_primary_admin
from ..database import get_db
from ..models import AuditLog, Company, Conversation, HelpRequest, User, UserCompanyAccess, UserPermission
from ..services.company_routing import identification_profile
from ..services.user_access import (
    PERMISSION_CATALOG,
    ROLE_TEMPLATES,
    allowed_company_ids,
    can_access_company,
    permissions_for_user,
    visible_companies_query,
)

router = APIRouter(tags=['access-control'])


class AccessUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    permissions: dict[str, bool] = Field(default_factory=dict)
    company_ids: list[int] = Field(default_factory=list)


@router.get('/api/access-control/me')
def my_access(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_company_ids(db, user)
    return {
        'username': user.username,
        'role': user.role,
        'dashboard': True,
        'permissions': permissions_for_user(db, user),
        'company_ids': None if allowed is None else sorted(allowed),
    }


@router.get('/api/access-control/catalog')
def access_catalog(_: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    companies = db.query(Company).order_by(Company.name.asc()).all()
    return {
        'permissions': [{'key': key, 'label': label} for key, label in PERMISSION_CATALOG.items()],
        'roles': sorted(ROLE_TEMPLATES.keys()),
        'role_templates': ROLE_TEMPLATES,
        'companies': [{'id': c.id, 'key': c.company_key, 'name': c.name, 'active': c.is_active} for c in companies],
    }


@router.get('/api/access-control/users')
def access_users(_: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.username != 'admin').order_by(User.username.asc()).all()
    result = []
    for user in users:
        permission_row = db.get(UserPermission, user.id)
        configured = bool(permission_row and isinstance(permission_row.permissions, dict) and permission_row.permissions.get('_configured'))
        company_configured = bool(permission_row and isinstance(permission_row.permissions, dict) and permission_row.permissions.get('_company_scope_configured'))
        company_ids = [row.company_id for row in db.query(UserCompanyAccess).filter(UserCompanyAccess.user_id == user.id).all()]
        result.append({
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'is_active': user.is_active,
            'permissions': permissions_for_user(db, user),
            'permissions_configured': configured,
            'company_scope_configured': company_configured,
            'company_ids': sorted(company_ids),
            'created_at': user.created_at,
        })
    return result


@router.put('/api/access-control/users/{user_id}')
def update_access(
    user_id: int,
    data: AccessUpdate,
    admin: User = Depends(require_primary_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.username == 'admin':
        raise HTTPException(status_code=404, detail='Usuario no encontrado')

    if data.role is not None:
        if data.role not in ROLE_TEMPLATES:
            raise HTTPException(status_code=422, detail='Rol inválido')
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    normalized = {key: bool(data.permissions.get(key, False)) for key in PERMISSION_CATALOG}
    normalized['_configured'] = True
    normalized['_company_scope_configured'] = True
    permission_row = db.get(UserPermission, user.id)
    if permission_row:
        permission_row.permissions = normalized
        permission_row.updated_by = admin.username
    else:
        db.add(UserPermission(user_id=user.id, permissions=normalized, updated_by=admin.username))

    valid_company_ids = {row[0] for row in db.query(Company.id).filter(Company.id.in_(data.company_ids or [-1])).all()}
    db.query(UserCompanyAccess).filter(UserCompanyAccess.user_id == user.id).delete(synchronize_session=False)
    for company_id in sorted(valid_company_ids):
        db.add(UserCompanyAccess(user_id=user.id, company_id=company_id))

    db.add(AuditLog(
        username=admin.username,
        action='configurar_acceso_usuario',
        entity='user',
        entity_id=str(user.id),
        details={
            'target_username': user.username,
            'role': user.role,
            'company_ids': sorted(valid_company_ids),
            'permissions': normalized,
        },
    ))
    db.commit()
    return {'status': 'ok'}


@router.get('/api/empresas/listar')
def scoped_companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    companies = visible_companies_query(db, user).order_by(Company.name.asc()).all()
    return [{
        'id': c.id,
        'empresa_id': c.company_key,
        'nombre': c.name,
        'activa': c.is_active,
        'tiendas': [{'id': s.id, 'nombre': s.name, 'whatsapp': s.whatsapp_number, 'phone_number_id': s.whatsapp_phone_number_id} for s in c.stores],
        'arbol_decisiones': c.decision_tree,
        'identificacion': identification_profile(c),
    } for c in companies]


@router.get('/api/conversaciones')
def scoped_conversations(company_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Conversation)
    allowed = allowed_company_ids(db, user)
    if allowed is not None:
        if not allowed:
            return []
        query = query.filter(Conversation.company_id.in_(allowed))
    if company_id is not None:
        if not can_access_company(db, user, company_id):
            raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
        query = query.filter(Conversation.company_id == company_id)
    rows = query.order_by(Conversation.updated_at.desc()).limit(200).all()
    companies = {c.id: c.name for c in visible_companies_query(db, user).all()}
    return [{'id': c.id, 'company_id': c.company_id, 'company_name': companies.get(c.company_id, 'Sin empresa'), 'wa_user_id': c.wa_user_id, 'authorized_support_contact': False, 'known_contact': False, 'state': c.state, 'status': c.status, 'updated_at': c.updated_at} for c in rows]


@router.get('/api/help-requests')
def scoped_help_requests(status: str | None = None, company_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(HelpRequest)
    allowed = allowed_company_ids(db, user)
    if allowed is not None:
        if not allowed:
            return []
        query = query.filter(HelpRequest.company_id.in_(allowed))
    if status:
        query = query.filter(HelpRequest.status == status)
    if company_id is not None:
        if not can_access_company(db, user, company_id):
            raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
        query = query.filter(HelpRequest.company_id == company_id)
    rows = query.order_by(HelpRequest.created_at.desc()).limit(200).all()
    companies = {c.id: c.name for c in visible_companies_query(db, user).all()}
    return [{'id': r.id, 'company_id': r.company_id, 'company_name': companies.get(r.company_id, 'Sin empresa'), 'store_name': 'Tienda sin identificar', 'conversation_id': r.conversation_id, 'wa_user_id': r.wa_user_id, 'body': r.body, 'status': r.status, 'authorized_support_contact': r.is_known_contact, 'known_contact': r.is_known_contact, 'is_group': r.is_group, 'created_at': r.created_at} for r in rows]
