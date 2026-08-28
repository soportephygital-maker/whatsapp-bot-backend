from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import require_case_closer
from ..database import get_db
from ..models import Conversation, HelpRequest, User
from ..schemas import HelpRequestStatus
from ..services.ticketing import close_ticket
from . import conversation_admin, dashboard

router = APIRouter(prefix='/api', tags=['ticket-case-close'])


@router.post('/conversaciones/{conversation_id}/cerrar')
def close_conversation_with_ticket(
    conversation_id: int,
    resultado: str = Query(default='resolved'),
    admin: User = Depends(require_case_closer),
    db: Session = Depends(get_db),
):
    result = conversation_admin.close_conversation(
        conversation_id=conversation_id,
        resultado=resultado,
        admin=admin,
        db=db,
    )
    conversation = db.get(Conversation, conversation_id)
    ticket = close_ticket(db, conversation=conversation, username=admin.username, result=resultado) if conversation else None
    db.commit()
    if ticket:
        result['ticket_id'] = ticket.id
        result['ticket_code'] = f'TKT-{ticket.id:06d}'
    return result


@router.patch('/help-requests/{request_id}')
def update_help_request_with_ticket(
    request_id: int,
    data: HelpRequestStatus,
    user: User = Depends(require_case_closer),
    db: Session = Depends(get_db),
):
    result = dashboard.update_help_request(request_id=request_id, data=data, user=user, db=db)
    if data.status in ('resolved', 'ignored'):
        request = db.get(HelpRequest, request_id)
        conversation = db.get(Conversation, request.conversation_id) if request and request.conversation_id else None
        ticket = close_ticket(db, conversation=conversation, username=user.username, result=data.status) if conversation else None
        db.commit()
        if ticket:
            result['ticket_id'] = ticket.id
            result['ticket_code'] = f'TKT-{ticket.id:06d}'
    return result
