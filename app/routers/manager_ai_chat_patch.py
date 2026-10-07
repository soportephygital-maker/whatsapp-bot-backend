from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import AIAdminMessage, User
from ..services.ai_learning import admin_chat
from ..services.user_access import can_access_company

router = APIRouter(prefix='/api/manager-ai', tags=['manager-ai-training'])


class ManagerAIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    company_id: int | None = None


def _manager(user: User) -> User:
    if user.role != 'gerente':
        raise HTTPException(status_code=403, detail='Acceso no disponible para este perfil')
    return user


@router.post('/chat')
def manager_ai_chat(data: ManagerAIChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _manager(user)
    if data.company_id is not None and not can_access_company(db, user, data.company_id):
        raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
    try:
        result = admin_chat(db, username=user.username, message=data.message, company_id=data.company_id)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f'No se pudo consultar la IA: {str(exc)[:300]}')


@router.get('/chat')
def manager_ai_chat_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _manager(user)
    rows = (
        db.query(AIAdminMessage)
        .filter(AIAdminMessage.username == user.username)
        .order_by(AIAdminMessage.id.desc())
        .limit(80)
        .all()
    )
    return [
        {'id': r.id, 'role': r.role, 'body': r.body, 'created_at': r.created_at}
        for r in reversed(rows)
    ]
