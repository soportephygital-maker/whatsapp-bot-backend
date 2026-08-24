from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import create_access_token, hash_password, require_primary_admin, verify_password
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
        db.add(AuditLog(username=data.username.strip()[:80] or None, action='login_fallido', entity='session', details={'reason': 'credenciales_invalidas'}))
        db.commit()
        raise HTTPException(status_code=401, detail='Credenciales incorrectas')
    db.add(AuditLog(username=user.username, action='login_exitoso', entity='session', entity_id=str(user.id), details={'role': user.role}))
    db.commit()
    # The primary administrator remains an internal role. The dashboard only needs
    # the internal token/session; the role itself is not exposed in user listings.
    return {'access_token': create_access_token(user.username), 'token_type': 'bearer', 'username': user.username, 'rol': user.role}


@router.get('/usuarios')
def list_users(admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    _ = admin
    primary_admin = _bootstrap_admin_username()
    query = db.query(User)
    if primary_admin:
        query = query.filter(User.username != primary_admin)
    rows = query.order_by(User.username.asc()).all()
    return [{
        'id': u.id,
        'username': u.username,
        'role': u.role,
        'is_active': u.is_active,
        'is_primary_admin': False,
        'created_at': u.created_at,
    } for u in rows]


@router.post('/crear-usuario')
def create_user(data: UserCreate, admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail='El usuario no puede estar vacío')
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail='El usuario ya existe')
    user = User(username=username, password_hash=hash_password(data.password), role=data.role, is_active=True)
    db.add(user)
    db.flush()
    db.add(AuditLog(username=admin.username, action='crear_usuario', entity='user', entity_id=str(user.id), details={'target_username': user.username, 'role': data.role}))
    db.commit()
    return {'status': 'ok', 'username': user.username, 'rol': user.role}


@router.patch('/usuarios/{user_id}')
def update_user(user_id: int, data: UserUpdate, admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    primary_admin = _bootstrap_admin_username()
    if primary_admin and user.username == primary_admin:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    before_role = user.role
    before_active = user.is_active
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_password(data.password)
    db.add(AuditLog(
        username=admin.username,
        action='actualizar_usuario',
        entity='user',
        entity_id=str(user.id),
        details={
            'target_username': user.username,
            'role_before': before_role,
            'role_after': user.role,
            'active_before': before_active,
            'active_after': user.is_active,
            'password_changed': bool(data.password),
        },
    ))
    db.commit()
    return {'status': 'ok', 'username': user.username, 'role': user.role, 'is_active': user.is_active}


@router.delete('/usuarios/{user_id}')
def delete_user(user_id: int, admin: User = Depends(require_primary_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    primary_admin = _bootstrap_admin_username()
    if (primary_admin and user.username == primary_admin) or user.id == admin.id:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    target_username = user.username
    target_role = user.role
    db.delete(user)
    db.add(AuditLog(username=admin.username, action='eliminar_usuario', entity='user', entity_id=str(user_id), details={'target_username': target_username, 'role': target_role}))
    db.commit()
    return {'status': 'ok', 'deleted_username': target_username}
