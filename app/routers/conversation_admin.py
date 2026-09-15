from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..auth import require_case_closer
from ..database import get_db
from ..models import AppNotification, AuditLog, Company, Conversation, ConversationChannel, HelpRequest, Message, User

router = APIRouter(prefix='/api', tags=['conversation-admin'])


@router.post('/conversaciones/{conversation_id}/cerrar')
def close_conversation(
    conversation_id: int,
    resultado: str = Query(default='resolved'),
    admin: User = Depends(require_case_closer),
    db: Session = Depends(get_db),
):
    if resultado not in ('resolved', 'ignored'):
        raise HTTPException(status_code=422, detail='Resultado inválido')
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversación no encontrada')

    company = db.get(Company, conversation.company_id) if conversation.company_id else None
    tree = company.decision_tree or {} if company else {}
    previous_status = conversation.status
    conversation.status = 'open'
    conversation.state = tree.get('nodo_raiz') or tree.get('root') or 'inicio'

    help_rows = db.query(HelpRequest).filter(
        HelpRequest.conversation_id == conversation_id,
        HelpRequest.status.in_(['new', 'reviewing']),
    ).all()
    for row in help_rows:
        row.status = resultado

    db.add(AuditLog(
        username=admin.username,
        action='cerrar_conversacion',
        entity='conversation',
        entity_id=str(conversation_id),
        details={
            'status_before': previous_status,
            'status_after': 'open',
            'resultado': resultado,
            'help_requests_closed': [row.id for row in help_rows],
        },
    ))
    db.commit()
    return {
        'status': 'ok',
        'conversation_id': conversation_id,
        'resultado': resultado,
        'help_requests_closed': len(help_rows),
        'chatbot_resumed': True,
    }


@router.delete('/conversaciones/{conversation_id}/olvidar')
def forget_conversation(
    conversation_id: int,
    admin: User = Depends(require_case_closer),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversación no encontrada')

    help_rows = db.query(HelpRequest).filter(HelpRequest.conversation_id == conversation_id).all()
    help_ids = {row.id for row in help_rows}

    for notification in db.query(AppNotification).all():
        details = notification.details or {}
        if details.get('help_request_id') in help_ids:
            db.delete(notification)

    if help_ids:
        help_id_strings = {str(value) for value in help_ids}
        for log in db.query(AuditLog).filter(AuditLog.entity == 'help_request').all():
            if log.entity_id in help_id_strings:
                db.delete(log)

    db.query(AuditLog).filter(
        AuditLog.entity == 'conversation',
        AuditLog.entity_id == str(conversation_id),
    ).delete(synchronize_session=False)
    db.query(Message).filter(Message.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(HelpRequest).filter(HelpRequest.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation_id).delete(synchronize_session=False)
    db.delete(conversation)

    db.add(AuditLog(
        username=admin.username,
        action='olvidar_conversacion',
        entity='maintenance',
        details={'conversation_id': conversation_id, 'help_request_ids': sorted(help_ids)},
    ))
    db.commit()
    return {'status': 'ok', 'forgotten_conversation_id': conversation_id, 'removed_help_requests': len(help_ids)}
