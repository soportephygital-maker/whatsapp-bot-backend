from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import RolePolicy, User

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')

DEFAULT_ROLE_PERMISSIONS = {
    'admin': {
        'operate': True,
        'admin_access': True,
        'appearance_edit': True,
        'activity_view': True,
        'manage_companies': True,
        'manage_users': True,
        'manage_roles': True,
    },
    'gerente': {
        'operate': True,
        'admin_access': True,
        'appearance_edit': True,
        'activity_view': True,
        'manage_companies': True,
        'manage_users': False,
        'manage_roles': False,
    },
    'operador': {
        'operate': True,
        'admin_access': False,
        'appearance_edit': False,
        'activity_view': False,
        'manage_companies': False,
        'manage_users': False,
        'manage_roles': False,
    },
    'lector': {
        'operate': False,
        'admin_access': False,
        'appearance_edit': False,
        'activity_view': False,
        'manage_companies': False,
        'manage_users': False,
        'manage_roles': False,
    },
}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({'sub': username, 'exp': exp}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido o vencido')
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get('sub')
        if not username:
            raise credentials_exception
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user:
        raise credentials_exception
    return user


def effective_permissions(db: Session, role: str) -> dict[str, bool]:
    defaults = dict(DEFAULT_ROLE_PERMISSIONS.get(role, DEFAULT_ROLE_PERMISSIONS['lector']))
    row = db.get(RolePolicy, role)
    if row and isinstance(row.permissions, dict):
        for key in defaults:
            if key in row.permissions:
                defaults[key] = bool(row.permissions[key])
    if role == 'admin':
        defaults.update({'operate': True, 'admin_access': True, 'appearance_edit': True, 'activity_view': True, 'manage_companies': True, 'manage_users': True, 'manage_roles': True})
    return defaults


def require_permission(permission: str):
    def dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not effective_permissions(db, current_user.role).get(permission, False):
            raise HTTPException(status_code=403, detail=f'El rol {current_user.role} no tiene el permiso {permission}')
        return current_user
    return dependency


def require_operator(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not effective_permissions(db, current_user.role).get('operate', False):
        raise HTTPException(status_code=403, detail='Este rol no puede responder ni modificar conversaciones')
    return current_user


def require_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not effective_permissions(db, current_user.role).get('admin_access', False):
        raise HTTPException(status_code=403, detail='Se requieren permisos administrativos')
    return current_user


def require_primary_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail='Solo el administrador puede administrar usuarios y permisos')
    return current_user
