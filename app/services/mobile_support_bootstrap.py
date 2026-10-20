import secrets

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..models import User, UserPermission
from .user_access import ROLE_TEMPLATES

SUPPORT_USERNAME = 'Soporte'


def ensure_mobile_support_account(db: Session) -> bool:
    """Ensure the dedicated mobile support account exists and can configure the bridge.

    A missing account is created with a random one-time password hash so no default
    credential is stored in source code. The dashboard can then set the real
    password explicitly.
    """
    user = db.query(User).filter(func.lower(User.username) == SUPPORT_USERNAME.lower()).first()
    changed = False

    if not user:
        user = User(
            username=SUPPORT_USERNAME,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role='operador',
            is_active=True,
        )
        db.add(user)
        db.flush()
        changed = True

    if user.username != SUPPORT_USERNAME:
        user.username = SUPPORT_USERNAME
        changed = True
    if user.role != 'operador':
        user.role = 'operador'
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True

    permission_row = db.get(UserPermission, user.id)
    if permission_row is None:
        permissions = dict(ROLE_TEMPLATES['operador'])
        permissions['_configured'] = True
        permissions['reply_conversations'] = True
        permissions['manage_mobile_bridge'] = True
        permission_row = UserPermission(
            user_id=user.id,
            permissions=permissions,
            updated_by='system_mobile_support',
        )
        db.add(permission_row)
        changed = True
    else:
        permissions = dict(permission_row.permissions or {})
        if not permissions.get('_configured'):
            permissions = {**ROLE_TEMPLATES['operador'], **permissions, '_configured': True}
        desired = {
            'reply_conversations': True,
            'manage_mobile_bridge': True,
            'view_companies': True,
        }
        needs_update = any(bool(permissions.get(key, False)) != value for key, value in desired.items())
        if needs_update or permission_row.permissions != permissions:
            permissions.update(desired)
            permission_row.permissions = permissions
            permission_row.updated_by = 'system_mobile_support'
            db.add(permission_row)
            changed = True

    if changed:
        db.add(user)
        db.commit()
    return True
