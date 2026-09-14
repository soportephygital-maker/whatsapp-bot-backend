import secrets

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..models import User, UserPermission

SUPPORT_USERNAME = 'Soporte'


def ensure_mobile_support_account(db: Session) -> bool:
    """Ensure the dedicated mobile support account exists and is usable by the app.

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
    if permission_row and isinstance(permission_row.permissions, dict) and permission_row.permissions.get('_configured'):
        permissions = dict(permission_row.permissions)
        if not permissions.get('reply_conversations'):
            permissions['reply_conversations'] = True
            permission_row.permissions = permissions
            db.add(permission_row)
            changed = True

    if changed:
        db.add(user)
        db.commit()
    return True
