from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import User, UserPermission

SUPPORT_USERNAME = 'Soporte'


def ensure_mobile_support_account(db: Session) -> bool:
    """Normalize an existing mobile support account without changing its password."""
    user = db.query(User).filter(func.lower(User.username) == SUPPORT_USERNAME.lower()).first()
    if not user:
        return False

    changed = False
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
