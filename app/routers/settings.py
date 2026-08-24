from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import DEFAULT_ROLE_PERMISSIONS, effective_permissions, get_current_user, require_permission, require_primary_admin
from ..database import get_db
from ..models import AuditLog, GlobalSetting, RolePolicy, User

router = APIRouter(prefix='/api/settings', tags=['settings'])

APPEARANCE_KEY = 'dashboard_appearance'
ALLOWED_ROLES = ('admin', 'gerente', 'operador', 'lector')
PERMISSION_LABELS = {
    'operate': 'Responder y modificar conversaciones',
    'admin_access': 'Acceso administrativo general',
    'appearance_edit': 'Editar apariencia global',
    'activity_view': 'Ver actividad y auditoría',
    'manage_companies': 'Administrar empresas y árboles',
    'manage_users': 'Administrar usuarios',
    'manage_roles': 'Editar permisos de roles',
}

DEFAULT_APPEARANCE = {
    'background': '#040814',
    'cards': '#0a1322',
    'text': '#edf6ff',
    'accent': '#4cb6ff',
    'input': '#08111f',
    'backgroundImage': '',
    'backgroundSize': 'cover',
    'contentWidth': '1240',
    'density': 'comfortable',
    'cardRadius': '18',
}


class AppearanceUpdate(BaseModel):
    background: str = Field(default=DEFAULT_APPEARANCE['background'], max_length=30)
    cards: str = Field(default=DEFAULT_APPEARANCE['cards'], max_length=30)
    text: str = Field(default=DEFAULT_APPEARANCE['text'], max_length=30)
    accent: str = Field(default=DEFAULT_APPEARANCE['accent'], max_length=30)
    input: str = Field(default=DEFAULT_APPEARANCE['input'], max_length=30)
    backgroundImage: str = Field(default='', max_length=2000)
    backgroundSize: str = Field(default='cover', pattern='^(cover|contain|auto)$')
    contentWidth: str = Field(default='1240', pattern='^(960|1100|1240|1440|1600)$')
    density: str = Field(default='comfortable', pattern='^(compact|comfortable|spacious)$')
    cardRadius: str = Field(default='18', pattern='^(0|8|12|18|24|32)$')


class RolePolicyUpdate(BaseModel):
    permissions: dict[str, bool]


def _appearance(db: Session) -> dict:
    row = db.get(GlobalSetting, APPEARANCE_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return {**DEFAULT_APPEARANCE, **value}


@router.get('/appearance')
def get_appearance(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _appearance(db)


@router.put('/appearance')
def update_appearance(data: AppearanceUpdate, user: User = Depends(require_permission('appearance_edit')), db: Session = Depends(get_db)):
    value = data.model_dump()
    row = db.get(GlobalSetting, APPEARANCE_KEY)
    if not row:
        row = GlobalSetting(key=APPEARANCE_KEY, value=value, updated_by=user.username)
        db.add(row)
    else:
        row.value = value
        row.updated_by = user.username
    db.add(AuditLog(username=user.username, action='dashboard_appearance_updated', entity='global_setting', entity_id=APPEARANCE_KEY, details=value))
    db.commit()
    return {'status': 'ok', 'appearance': value}


@router.get('/me-permissions')
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {'role': user.role, 'permissions': effective_permissions(db, user.role)}


@router.get('/role-policies')
def list_role_policies(_: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    return {
        'labels': PERMISSION_LABELS,
        'roles': [
            {'role': role, 'permissions': effective_permissions(db, role), 'protected': role == 'admin'}
            for role in ALLOWED_ROLES
        ],
    }


@router.put('/role-policies/{role}')
def update_role_policy(role: str, data: RolePolicyUpdate, admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=404, detail='Rol no reconocido')
    if role == 'admin':
        raise HTTPException(status_code=400, detail='Los permisos del administrador principal están protegidos')

    allowed = set(PERMISSION_LABELS)
    permissions = {key: bool(value) for key, value in data.permissions.items() if key in allowed}
    merged = {**DEFAULT_ROLE_PERMISSIONS[role], **permissions}
    row = db.get(RolePolicy, role)
    if not row:
        row = RolePolicy(role=role, permissions=merged, updated_by=admin.username)
        db.add(row)
    else:
        row.permissions = merged
        row.updated_by = admin.username
    db.add(AuditLog(username=admin.username, action='role_policy_updated', entity='role_policy', entity_id=role, details={'permissions': merged}))
    db.commit()
    return {'status': 'ok', 'role': role, 'permissions': effective_permissions(db, role)}
