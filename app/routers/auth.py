from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import create_access_token, hash_password, require_admin, verify_password
from ..database import get_db
from ..models import AuditLog, User
from ..schemas import LoginRequest, UserCreate

router = APIRouter(prefix='/api/auth', tags=['auth'])

@router.post('/login')
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username, User.is_active.is_(True)).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Credenciales incorrectas')
    return {'access_token': create_access_token(user.username), 'token_type': 'bearer', 'username': user.username, 'rol': user.role}

@router.post('/crear-usuario')
def create_user(data: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=409, detail='El usuario ya existe')
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.add(AuditLog(username=admin.username, action='crear_usuario', entity='user', entity_id=data.username))
    db.commit()
    return {'status': 'ok', 'username': user.username, 'rol': user.role}
