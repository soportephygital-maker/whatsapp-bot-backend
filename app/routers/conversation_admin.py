from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import require_admin
from ..database import get_db
from ..models import AppNotification, AuditLog, Conversation, ConversationChannel, HelpRequest, Message, User

router = APIRouter(prefix='/api', tags=['conversation-admin'])


@router.delete('/conversaciones/{conversation_id}/olvidar')
def forget_conversation(
    conversation_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversación no encontrada')

    help_rows = db.query(HelpRequest).filter(HelpRequest.conversation_id == conversation_id).all()
    help_ids = {row.id for row in help_rows}

    # Remove app notifications tied to these test help requests so they do not
    # continue appearing after an administrator explicitly forgets the case.
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
