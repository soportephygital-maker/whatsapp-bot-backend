from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import AuditLog, Company, Conversation, ConversationChannel, Message, Store, SupportTicket, User
from ..services.ticketing import close_ticket, ticket_code
from . import global_entry_sequence_patch, local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-image-evidence'])

IMAGE_CONFIRM_STATE = '__image_evidence_confirm__'
IMAGE_WAIT_STATE = '__image_evidence_wait_another__'
IMAGE_INCIDENT_STATE = '__image_evidence_incident_description__'
IMAGE_CONFIRM_TEXT = (
    '📷 Recibí una imagen.\n\n'
    '¿Esta foto es la correcta o deseas enviar otra?\n'
    '1️⃣ Sí, esta foto es la correcta\n'
    '2️⃣ Deseo enviar otra foto\n\n'
    'Todas las fotos que compartas quedarán asociadas al expediente de tu reporte.'
)
IMAGE_ANOTHER_TEXT = (
    '📷 Claro. Envía la siguiente foto cuando quieras.\n\n'
    'Cuando la reciba te preguntaré nuevamente si es la correcta. '
    'Las imágenes recibidas quedarán asociadas al expediente de tu reporte.'
)
IMAGE_INCIDENT_QUESTION = (
    '✅ La foto quedó registrada en el expediente de tu reporte.\n\n'
    'Ahora cuéntame brevemente: ¿cómo sucedió el problema?'
)


def _normalized(value: str) -> str:
    return local_bridge._normalize_text(value)


def _is_image(data: local_bridge.LocalInbound) -> bool:
    metadata = data.metadata or {}
    capture = str(metadata.get('media_capture') or '').strip().lower()
    source = str(metadata.get('media_source') or '').strip().lower()
    if capture == 'available' or source:
        return True
    text = _normalized(data.text)
    return text in {
        'imagen recibida', 'image received', 'foto', 'photo', 'imagen', 'image',
        'foto recibida', 'photo received',
    }


def _active_context(db: Session, data: local_bridge.LocalInbound):
    local_user_id = local_bridge._local_user_id(data)
    conversation = ticketed_local_bridge._active_conversation(db, local_user_id)
    if not conversation or not conversation.company_id:
        return local_user_id, None, None, None, None
    company = db.get(Company, conversation.company_id)
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    store = db.get(Store, channel.store_id) if channel and channel.store_id else None
    if not store and company:
        store = ticketed_local_bridge._selected_context_store(data, db, company.id)
    ticket = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    return local_user_id, conversation, company, store, ticket


def _latest_image_context(db: Session, conversation_id: int) -> dict:
    row = db.query(AuditLog).filter(
        AuditLog.action == 'image_evidence_context',
        AuditLog.entity == 'conversation',
        AuditLog.entity_id == str(conversation_id),
    ).order_by(AuditLog.id.desc()).first()
    return dict(row.details or {}) if row and isinstance(row.details, dict) else {}


def _reply(db: Session, *, conversation: Conversation, company: Company, store: Store, data: local_bridge.LocalInbound, text: str):
    outbound = local_bridge._queue_outbound(
        db,
        conversation=conversation,
        text=text,
        data=data,
        company=company,
        store=store,
    )
    payload = dict(outbound.raw_payload or {})
    payload['package_name'] = data.package_name
    payload['sender_display'] = data.sender
    payload['sender_key'] = data.sender_key
    # If the current WhatsApp notification has no inline reply action, keep the
    # message pending so the Android poller can retry it against the next active
    # notification for the same conversation instead of silently losing it.
    if not data.can_reply:
        payload['delivery_status'] = 'requested'
        payload['manual_dashboard'] = True
        payload['retry_inline'] = True
    outbound.raw_payload = payload
    return outbound


def _save_inbound_text(db: Session, *, data: local_bridge.LocalInbound, conversation: Conversation, marker: str) -> None:
    provider_message_id = local_bridge._provider_message_id(data)
    if db.query(Message).filter(Message.provider_message_id == provider_message_id).first():
        return
    db.add(Message(
        conversation_id=conversation.id,
        direction='inbound',
        sender=local_bridge._local_user_id(data),
        body=data.text,
        provider_message_id=provider_message_id,
        raw_payload={
            'provider': 'android_notification',
            'package_name': data.package_name,
            'device_id': data.device_id,
            'notification_key': data.notification_key,
            'post_time': data.post_time,
            'sender_display': data.sender,
            'sender_key': data.sender_key,
            'reply_capable': data.can_reply,
            'metadata': dict(data.metadata or {}),
            marker: True,
        },
    ))


def _save_image_message(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
    return_state: str,
):
    provider_message_id = local_bridge._provider_message_id(data)
    duplicate = db.query(Message).filter(Message.provider_message_id == provider_message_id).first()
    if duplicate:
        return duplicate, True

    payload = {
        'provider': 'android_notification',
        'package_name': data.package_name,
        'device_id': data.device_id,
        'notification_key': data.notification_key,
        'post_time': data.post_time,
        'sender_display': data.sender,
        'sender_key': data.sender_key,
        'reply_capable': data.can_reply,
        'store_id': store.id,
        'selected_store_ids': list(data.selected_store_ids or []),
        'metadata': dict(data.metadata or {}),
        'image_evidence': True,
        'image_confirmation_pending': True,
        'image_return_state': return_state,
        'ticket_id': ticket.id if ticket else None,
    }
    message = Message(
        conversation_id=conversation.id,
        direction='inbound',
        sender=local_bridge._local_user_id(data),
        body=data.text,
        provider_message_id=provider_message_id,
        raw_payload=payload,
    )
    db.add(message)
    db.flush()
    db.add(AuditLog(
        username=operator.username,
        action='image_evidence_context',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'message_id': message.id,
            'ticket_id': ticket.id if ticket else None,
            'return_state': return_state,
            'media_capture': (data.metadata or {}).get('media_capture'),
            'media_source': (data.metadata or {}).get('media_source'),
        },
    ))
    return message, False


def _closed_text(ticket: SupportTicket | None, company: Company, store: Store) -> str:
    code = ticket_code(ticket, company, store) if ticket else ''
    ticket_line = f'🎫 Ticket: {code}\n' if code else ''
    return (
        '✅ Gracias. Registré cómo sucedió el problema.\n\n'
        f'{ticket_line}'
        'Estado: CERRADO 🟢\n\n'
        '¿Quieres reportar otro problema?\n'
        '1️⃣ Sí, abrir un reporte nuevo\n'
        '2️⃣ No'
    )


def _capture_incident_and_close(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
):
    explanation = str(data.text or '').strip()
    if not explanation:
        repeat = 'Cuéntame brevemente cómo sucedió el problema para poder cerrar el ticket.'
        outbound = _reply(
            db,
            conversation=conversation,
            company=company,
            store=store,
            data=data,
            text=repeat,
        )
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name, 'action': 'incident_description_repeat',
            'reply_text': repeat if data.can_reply else '',
            'should_reply': bool(data.can_reply), 'outbound_message_id': outbound.id,
            'ticket_id': ticket.id if ticket else None, 'chatbot_paused': False,
        }

    # Cualquier texto recibido después de "¿cómo sucedió?" es la explicación.
    # No se requiere enviar "Finalizar" ni ninguna palabra adicional.
    _save_inbound_text(db, data=data, conversation=conversation, marker='incident_description')

    if ticket:
        base_description = str(ticket.description or '').strip()
        incident_line = f'Cómo sucedió: {explanation}'
        if incident_line.lower() not in base_description.lower():
            ticket.description = f'{base_description}\n\n{incident_line}'.strip()[:4000]
        close_ticket(
            db,
            conversation=conversation,
            username=operator.username,
            result=f'Cierre automático después de evidencia. Cómo sucedió: {explanation}'[:2000],
        )

    conversation.status = 'open'
    conversation.state = 'post_close_prompt'
    close_text = _closed_text(ticket, company, store)
    outbound = _reply(
        db,
        conversation=conversation,
        company=company,
        store=store,
        data=data,
        text=close_text,
    )
    db.add(AuditLog(
        username=operator.username,
        action='image_incident_captured_and_ticket_closed',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'ticket_id': ticket.id if ticket else None,
            'incident_description': explanation[:2000],
            'ticket_closed': bool(ticket),
            'reply_capable_at_capture': bool(data.can_reply),
        },
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name,
        'action': 'incident_captured_ticket_closed' if ticket else 'incident_captured_no_ticket',
        'reply_text': close_text if data.can_reply else '', 'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False, 'post_close_prompt': True,
        'reply_queued_for_retry': not bool(data.can_reply),
    }


def _handle_confirmation_reply(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
):
    text = _normalized(data.text)
    yes = text in {'1', 'si', 'sí', 'correcta', 'correcto', 'esta bien', 'es correcta', 'esa es', 'esa esta bien'}
    no = text in {'2', 'no', 'otra', 'otra foto', 'enviar otra', 'quiero otra', 'deseo enviar otra'}
    if not yes and not no:
        outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=IMAGE_CONFIRM_TEXT)
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name, 'action': 'image_confirmation_repeat',
            'reply_text': IMAGE_CONFIRM_TEXT if data.can_reply else '', 'should_reply': bool(data.can_reply),
            'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
            'chatbot_paused': False,
        }

    _save_inbound_text(db, data=data, conversation=conversation, marker='image_confirmation_answer')

    context = _latest_image_context(db, conversation.id)
    if no:
        conversation.state = IMAGE_WAIT_STATE
        response = IMAGE_ANOTHER_TEXT
        action = 'image_request_another'
    else:
        conversation.state = IMAGE_INCIDENT_STATE
        response = IMAGE_INCIDENT_QUESTION
        action = 'image_confirmed_ask_incident'

    outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
    db.add(AuditLog(
        username=operator.username,
        action=action,
        entity='conversation',
        entity_id=str(conversation.id),
        details={'ticket_id': ticket.id if ticket else None, 'return_state': context.get('return_state')},
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name, 'action': action,
        'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False,
    }


@router.post('/inbound')
def image_evidence_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    local_user_id, conversation, company, store, ticket = _active_context(db, data)

    if conversation and company and store and conversation.status not in {'help_pending', 'human_active'}:
        # Esta condición va antes de cualquier otra clasificación: el primer texto
        # después de la pregunta "¿cómo sucedió?" siempre captura la explicación,
        # cierra el ticket y genera la confirmación de cierre.
        if conversation.state == IMAGE_INCIDENT_STATE:
            return _capture_incident_and_close(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        if _is_image(data):
            context = _latest_image_context(db, conversation.id)
            return_state = str(context.get('return_state') or '').strip()
            if not return_state or return_state in {IMAGE_CONFIRM_STATE, IMAGE_WAIT_STATE, IMAGE_INCIDENT_STATE}:
                return_state = conversation.state if conversation.state not in {IMAGE_CONFIRM_STATE, IMAGE_WAIT_STATE, IMAGE_INCIDENT_STATE} else ''
            message, duplicate = _save_image_message(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
                return_state=return_state,
            )
            if duplicate:
                db.rollback()
                return {'status': 'duplicate', 'conversation_id': conversation.id, 'should_reply': False, 'ticket_id': ticket.id if ticket else None}
            conversation.state = IMAGE_CONFIRM_STATE
            outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=IMAGE_CONFIRM_TEXT)
            db.add(AuditLog(
                username=operator.username,
                action='image_evidence_received',
                entity='conversation',
                entity_id=str(conversation.id),
                details={'message_id': message.id, 'ticket_id': ticket.id if ticket else None, 'return_state': return_state},
            ))
            db.commit()
            return {
                'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
                'company_name': company.name, 'store_name': store.name, 'action': 'image_confirmation',
                'reply_text': IMAGE_CONFIRM_TEXT if data.can_reply else '', 'should_reply': bool(data.can_reply),
                'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
                'chatbot_paused': False,
            }

        if conversation.state == IMAGE_CONFIRM_STATE:
            return _handle_confirmation_reply(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        if conversation.state == IMAGE_WAIT_STATE:
            response = IMAGE_ANOTHER_TEXT
            outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
            db.commit()
            return {
                'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
                'company_name': company.name, 'store_name': store.name, 'action': 'waiting_for_image',
                'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
                'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
                'chatbot_paused': False,
            }

    return global_entry_sequence_patch.global_entry_sequence_inbound(data=data, operator=operator, db=db)
