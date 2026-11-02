from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import require_case_closer
from ..database import get_db
from ..models import Company, Conversation, HelpRequest, Store, User
from ..schemas import HelpRequestStatus
from ..services.ticketing import close_ticket, ticket_code
from . import conversation_admin, dashboard

router = APIRouter(prefix='/api', tags=['ticket-case-close'])


def _ticket_result(ticket, db: Session) -> dict:
    if not ticket:
        return {}
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    return {
        'ticket_id': ticket.id,
        'ticket_code': ticket_code(ticket, company, store),
    }


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
    ticket = close_ticket(
        db,
        conversation=conversation,
        username=admin.username,
        result=resultado,
    ) if conversation else None
    db.commit()
    result.update(_ticket_result(ticket, db))
    return result


@router.patch('/help-requests/{request_id}')
def update_help_request_with_ticket(
    request_id: int,
    data: HelpRequestStatus,
    user: User = Depends(require_case_closer),
    db: Session = Depends(get_db),
):
    result = dashboard.update_help_request(
        request_id=request_id,
        data=data,
        user=user,
        db=db,
    )
    if data.status in ('resolved', 'ignored'):
        request = db.get(HelpRequest, request_id)
        conversation = db.get(Conversation, request.conversation_id) if request and request.conversation_id else None
        ticket = close_ticket(
            db,
            conversation=conversation,
            username=user.username,
            result=data.status,
        ) if conversation else None
        db.commit()
        result.update(_ticket_result(ticket, db))
    return result
