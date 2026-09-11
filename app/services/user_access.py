from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Company, User, UserCompanyAccess, UserPermission

PERMISSION_CATALOG = {
    'view_requests': 'Ver solicitudes de ayuda',
    'update_requests': 'Cambiar estado de solicitudes',
    'view_conversations': 'Ver conversaciones',
    'reply_conversations': 'Responder conversaciones',
    'close_cases': 'Cerrar casos',
    'delete_conversations': 'Eliminar conversaciones',
    'view_contacts': 'Ver contactos',
    'manage_contacts': 'Administrar contactos',
    'view_companies': 'Ver empresas y tiendas',
    'manage_company_tree': 'Editar árboles de decisión',
    'manage_stores': 'Administrar tiendas',
    'manage_support_contacts': 'Administrar personal de soporte',
    'manage_company_files': 'Administrar archivos de empresa',
    'manage_support_emails': 'Administrar correos de incidencias',
    'simulate_bot': 'Usar simulador del bot',
    'view_reports': 'Ver reportes y gráficas',
    'download_reports': 'Descargar reportes y gráficas',
    'view_activity': 'Ver actividad de usuarios',
    'manage_appearance': 'Modificar apariencia',
    'manage_users': 'Crear y modificar usuarios',
    'manage_user_permissions': 'Configurar permisos de usuarios',
    'manage_user_companies': 'Configurar empresas por usuario',
    'manage_mobile_bridge': 'Configurar puente móvil de WhatsApp',
}

ROLE_TEMPLATES = {
    'gerente': {key: True for key in PERMISSION_CATALOG},
    'operador': {
        **{key: False for key in PERMISSION_CATALOG},
        'view_requests': True, 'update_requests': True,
        'view_conversations': True, 'reply_conversations': True,
        'view_contacts': True, 'view_companies': True,
        'simulate_bot': True,
    },
    'lector': {
        **{key: False for key in PERMISSION_CATALOG},
        'view_requests': True, 'view_conversations': True,
        'view_contacts': True, 'view_companies': True,
        'view_reports': True,
    },
}


def is_super_admin(user: User) -> bool:
    return user.username == 'admin' and user.role == 'admin'


def permissions_for_user(db: Session, user: User) -> dict[str, bool]:
    if is_super_admin(user):
        return {key: True for key in PERMISSION_CATALOG}
    template = dict(ROLE_TEMPLATES.get(user.role, ROLE_TEMPLATES['lector']))
    row = db.get(UserPermission, user.id)
    if row and isinstance(row.permissions, dict) and row.permissions.get('_configured'):
        return {key: bool(row.permissions.get(key, False)) for key in PERMISSION_CATALOG}
    return template


def has_permission(db: Session, user: User, permission: str) -> bool:
    return bool(permissions_for_user(db, user).get(permission, False))


def require_user_permission(db: Session, user: User, permission: str) -> None:
    if not has_permission(db, user, permission):
        raise HTTPException(status_code=403, detail=f'No tienes permiso: {PERMISSION_CATALOG.get(permission, permission)}')


def company_scope_configured(db: Session, user: User) -> bool:
    if is_super_admin(user):
        return False
    row = db.get(UserPermission, user.id)
    return bool(row and isinstance(row.permissions, dict) and row.permissions.get('_company_scope_configured'))


def allowed_company_ids(db: Session, user: User) -> set[int] | None:
    if is_super_admin(user) or not company_scope_configured(db, user):
        return None
    return {row.company_id for row in db.query(UserCompanyAccess).filter(UserCompanyAccess.user_id == user.id).all()}


def can_access_company(db: Session, user: User, company_id: int | None) -> bool:
    if company_id is None:
        return True
    allowed = allowed_company_ids(db, user)
    return allowed is None or company_id in allowed


def require_company_access(db: Session, user: User, company_id: int | None) -> None:
    if not can_access_company(db, user, company_id):
        raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')


def visible_companies_query(db: Session, user: User):
    query = db.query(Company)
    allowed = allowed_company_ids(db, user)
    if allowed is not None:
        if not allowed:
            return query.filter(Company.id == -1)
        query = query.filter(Company.id.in_(allowed))
    return query
