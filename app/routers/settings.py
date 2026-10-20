from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import DEFAULT_ROLE_PERMISSIONS, effective_permissions, get_current_user, require_permission, require_primary_admin
from ..database import get_db
from ..models import AuditLog, GlobalSetting, RolePolicy, User

router = APIRouter(prefix='/api/settings', tags=['settings'])

APPEARANCE_KEY = 'dashboard_appearance'
OWNER_ALIAS_KEY = 'owner_display_alias'
DEFAULT_OWNER_ALIAS = 'Zoe Ortiz'
VISIBLE_ROLES = ('gerente', 'operador', 'lector')
PERMISSION_LABELS = {
    'operate': 'Responder y modificar conversaciones',
    'admin_access': 'Acceso administrativo general',
    'appearance_edit': 'Editar apariencia global',
    'activity_view': 'Ver actividad y auditoría',
}

DEFAULT_APPEARANCE = {
    'background': '#040814',
    'cards': '#0a1322',
    'text': '#edf6ff',
    'accent': '#4cb6ff',
    'input': '#08111f',
    'backgroundImage': '',
    'backgroundSize': 'cover',
    'imageRepeatCount': 1,
    'cardOpacity': 90,
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
    imageRepeatCount: int = Field(default=1, ge=1, le=12)
    cardOpacity: int = Field(default=90, ge=10, le=100)
    contentWidth: str = Field(default='1240', pattern='^(960|1100|1240|1440|1600)$')
    density: str = Field(default='comfortable', pattern='^(compact|comfortable|spacious)$')
    cardRadius: str = Field(default='18', pattern='^(0|8|12|18|24|32)$')


class RolePolicyUpdate(BaseModel):
    permissions: dict[str, bool]


class OwnerAliasUpdate(BaseModel):
    alias: str = Field(min_length=2, max_length=80)


def _appearance(db: Session) -> dict:
    row = db.get(GlobalSetting, APPEARANCE_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return {**DEFAULT_APPEARANCE, **value}


def owner_display_alias(db: Session) -> str:
    row = db.get(GlobalSetting, OWNER_ALIAS_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    alias = str(value.get('alias') or DEFAULT_OWNER_ALIAS).strip()
    return alias or DEFAULT_OWNER_ALIAS


@router.get('/appearance')
def get_appearance(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _appearance(db)


@router.put('/appearance')
def update_appearance(data: AppearanceUpdate, user: User = Depends(require_permission('appearance_edit')), db: Session = Depends(get_db)):
    value = data.dict()
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


@router.get('/owner-alias')
def get_owner_alias(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import os
    primary = (os.getenv('BOOTSTRAP_ADMIN_USERNAME') or '').strip()
    payload = {'alias': owner_display_alias(db), 'can_edit': user.role == 'admin'}
    if user.role == 'admin':
        payload['internal_username'] = primary or user.username
    return payload


@router.put('/owner-alias')
def update_owner_alias(data: OwnerAliasUpdate, admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    alias = data.alias.strip()
    if not alias:
        raise HTTPException(status_code=422, detail='El seudónimo no puede estar vacío')
    value = {'alias': alias}
    row = db.get(GlobalSetting, OWNER_ALIAS_KEY)
    if not row:
        row = GlobalSetting(key=OWNER_ALIAS_KEY, value=value, updated_by=admin.username)
        db.add(row)
    else:
        row.value = value
        row.updated_by = admin.username
    db.commit()
    return {'status': 'ok', 'alias': alias, 'internal_username': admin.username}


@router.get('/me-permissions')
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    public_role = 'gerente' if user.role == 'admin' else user.role
    return {'role': public_role, 'permissions': effective_permissions(db, user.role)}


@router.get('/role-policies')
def list_role_policies(_: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    return {
        'labels': PERMISSION_LABELS,
        'roles': [
            {'role': role, 'permissions': effective_permissions(db, role), 'protected': False}
            for role in VISIBLE_ROLES
        ],
    }


@router.put('/role-policies/{role}')
def update_role_policy(role: str, data: RolePolicyUpdate, admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    if role not in VISIBLE_ROLES:
        raise HTTPException(status_code=404, detail='Rol no reconocido')
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