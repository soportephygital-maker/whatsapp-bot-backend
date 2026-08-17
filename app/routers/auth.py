from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import create_access_token, hash_password, require_admin, verify_password
from ..database import get_db
from ..models import AuditLog, User
from ..schemas import LoginRequest, UserCreate, UserUpdate

router = APIRouter(prefix='/api/auth', tags=['auth'])


def _bootstrap_admin_username() -> str | None:
    import os
    return os.getenv('BOOTSTRAP_ADMIN_USERNAME')


@router.post('/login')
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username, User.is_active.is_(True)).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Credenciales incorrectas')
    return {'access_token': create_access_token(user.username), 'token_type': 'bearer', 'username': user.username, 'rol': user.role}


@router.get('/usuarios')
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _ = admin
    primary_admin = _bootstrap_admin_username()
    rows = db.query(User).order_by(User.username.asc()).all()
    return [{
        'id': u.id,
        'username': u.username,
        'role': u.role,
        'is_active': u.is_active,
        'is_primary_admin': bool(primary_admin and u.username == primary_admin),
        'created_at': u.created_at,
    } for u in rows]


@router.post('/crear-usuario')
def create_user(data: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=409, detail='El usuario ya existe')
    user = User(username=data.username.strip(), password_hash=hash_password(data.password), role=data.role, is_active=True)
    db.add(user)
    db.add(AuditLog(username=admin.username, action='crear_usuario', entity='user', entity_id=data.username, details={'role': data.role}))
    db.commit()
    return {'status': 'ok', 'username': user.username, 'rol': user.role}


@router.patch('/usuarios/{user_id}')
def update_user(user_id: int, data: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    primary_admin = _bootstrap_admin_username()
    if primary_admin and user.username == primary_admin:
        if data.role is not None or data.is_active is False:
            raise HTTPException(status_code=400, detail='El administrador principal no puede perder permisos ni desactivarse')
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_password(data.password)
    db.add(AuditLog(username=admin.username, action='actualizar_usuario', entity='user', entity_id=user.username, details={'role': user.role, 'is_active': user.is_active, 'password_changed': bool(data.password)}))
    db.commit()
    return {'status': 'ok', 'username': user.username, 'role': user.role, 'is_active': user.is_active}
