from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..database import get_db
from ..models import Company, Conversation, Message, User

router = APIRouter(prefix='/api', tags=['dashboard'])

@router.get('/stats')
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        'empresas': db.query(func.count(Company.id)).scalar() or 0,
        'conversaciones': db.query(func.count(Conversation.id)).scalar() or 0,
        'mensajes': db.query(func.count(Message.id)).scalar() or 0,
    }

@router.get('/conversaciones')
def conversations(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(100).all()
    return [{'id': c.id, 'wa_user_id': c.wa_user_id, 'state': c.state, 'status': c.status, 'updated_at': c.updated_at} for c in rows]
