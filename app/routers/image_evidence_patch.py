from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import AuditLog, CaseAttachment, Company, Conversation, ConversationChannel, Message, Store, SupportTicket, User
from ..services.ticketing import add_ticket_followup, close_ticket, ticket_code
from . import global_entry_sequence_patch, local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-image-evidence'])

IMAGE_CONFIRM_STATE = '__image_evidence_confirm__'
IMAGE_EVIDENCE_ACTION_STATE = '__image_evidence_add_or_replace__'
IMAGE_WAIT_STATE = '__image_evidence_wait_another__'
IMAGE_INCIDENT_STATE = '__image_evidence_incident_description__'
IMAGE_MORE_PROBLEM_STATE = '__image_evidence_more_problem__'
IMAGE_CONFIRM_TEXT = (
    '📷 Recibí una imagen.\n\n'
    '¿Esta foto es la correcta?\n'
    '1️⃣ Sí, cerrar el ticket con esta evidencia\n'
    '2️⃣ No, agregar o cambiar la foto'
)
IMAGE_EVIDENCE_ACTION_TEXT = (
    '📷 ¿Desea agregar o cambiar la foto?\n'
    '1️⃣ Agregar\n'
    '2️⃣ Cambiar'
)
IMAGE_ANOTHER_TEXT = (
    '📎 Perfecto. La foto actual se conserva.\n\n'
    'Envía la nueva evidencia que deseas agregar. '
    'Al recibirla volveré a mostrarte la confirmación de foto recibida.'
)
IMAGE_REPLACE_TEXT = (
    '♻️ Entendido. La foto anterior se retiró del expediente.\n\n'
    'Envía ahora la nueva foto. '
    'Al recibirla volveré a mostrarte la confirmación de foto recibida.'
)
IMAGE_INCIDENT_QUESTION = (
    '✅ La foto quedó registrada en el expediente de tu reporte.\n\n'
    'Ahora cuéntame brevemente: ¿cómo sucedió el problema?'
)
IMAGE_MORE_PROBLEM_TEXT = (
    '✅ Gracias. Registré cómo sucedió el problema.\n\n'
    '¿Deseas reportar otro problema?\n'
    '1️⃣ Sí, reportar otro problema\n'
    '2️⃣ No, enviar este ticket a validación'
)


def _normalized(value: str) -> str:
    return local_bridge._normalize_text(value)


def _is_confirmation_choice(value: str) -> bool:
    text = _normalized(value)
    return text in {
        '1', '2', 'si', 'no', 'correcta', 'correcto', 'esta bien', 'es correcta',
        'esa es', 'esa esta bien', 'esta foto es la correcta', 'si esta foto es la correcta',
        'cerrar', 'cerrar ticket', 'finalizar', 'terminar', 'listo', 'fin', 'salir',
        'otra', 'otra foto', 'otra evidencia', 'enviar otra', 'quiero otra',
        'deseo enviar otra', 'agregar', 'reemplazar', 'remplazar', 'cambiar foto',
    }


def _is_evidence_action_choice(value: str) -> bool:
    text = _normalized(value)
    return text in {
        '1', '2', 'agregar', 'agrega', 'agregar otra', 'agregar evidencia',
        'agregar otra evidencia', 'otra', 'otra foto', 'otra evidencia',
        'conservar', 'conservar esta', 'conservar foto', 'mas evidencia',
        'reemplazar', 'reemplaza', 'reemplazar foto', 'reemplazar evidencia',
        'remplazar', 'remplaza', 'remplazar foto', 'remplazar evidencia',
        'cambiar', 'cambiar foto', 'cambiar evidencia', 'sustituir', 'sustituir foto',
    }


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
    # Si la notificación actual no tiene RemoteInput, se conserva la respuesta
    # pendiente para que el poller Android la reintente en la siguiente notificación
    # activa de la misma conversación.
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


def _validation_closed_text(ticket: SupportTicket | None, company: Company, store: Store) -> str:
    code = ticket_code(ticket, company, store) if ticket else ''
    ticket_line = f'🎫 Ticket: {code}\n' if code else ''
    return (
        '✅ Gracias. Tu reporte quedó registrado correctamente.\n\n'
        f'{ticket_line}'
        'Estado: CERRADO 🟢\n'
        'Seguimiento: PENDIENTE DE VALIDACIÓN 🔎\n\n'
        'El equipo correspondiente podrá revisar la información y evidencias del expediente.'
    )


def _close_for_validation(
    db: Session,
    *,
    operator: User,
    conversation: Conversation,
    ticket: SupportTicket | None,
    result: str,
) -> SupportTicket | None:
    if not ticket:
        return None
    closed = close_ticket(
        db,
        conversation=conversation,
        username=operator.username,
        result=result[:2000],
    )
    if closed:
        add_ticket_followup(
            db,
            ticket=closed,
            username=operator.username,
            status_label='Pendiente de validación',
            message='El usuario terminó el reporte. El expediente y sus evidencias quedaron pendientes de validación.',
        )
    return closed


def _new_conversation_from_old(
    db: Session,
    *,
    old: Conversation,
    company: Company,
    store: Store,
    data: local_bridge.LocalInbound,
) -> Conversation:
    root = local_bridge._root_state(company.decision_tree or {})
    old.status = 'closed'
    old.state = 'closed_previous_ticket'
    new = Conversation(
        company_id=company.id,
        wa_user_id=old.wa_user_id,
        status='open',
        state=root,
    )
    db.add(new)
    db.flush()
    old_channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == old.id).first()
    db.add(ConversationChannel(
        conversation_id=new.id,
        company_id=company.id,
        store_id=store.id,
        phone_number_id=(old_channel.phone_number_id if old_channel and old_channel.phone_number_id else f'android:{data.device_id}')[:80],
    ))
    db.flush()
    return new


def _capture_incident_and_ask_more(
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
        repeat = 'Cuéntame brevemente cómo sucedió el problema.'
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

    # Cualquier texto recibido después de "¿cómo sucedió?" se guarda como explicación.
    # El ticket permanece abierto hasta que el usuario responda si tiene otro problema.
    _save_inbound_text(db, data=data, conversation=conversation, marker='incident_description')

    if ticket:
        base_description = str(ticket.description or '').strip()
        incident_line = f'Cómo sucedió: {explanation}'
        if incident_line.lower() not in base_description.lower():
            ticket.description = f'{base_description}\n\n{incident_line}'.strip()[:4000]

    conversation.status = 'open'
    conversation.state = IMAGE_MORE_PROBLEM_STATE
    outbound = _reply(
        db,
        conversation=conversation,
        company=company,
        store=store,
        data=data,
        text=IMAGE_MORE_PROBLEM_TEXT,
    )
    db.add(AuditLog(
        username=operator.username,
        action='image_incident_captured_waiting_more_problem',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'ticket_id': ticket.id if ticket else None,
            'incident_description': explanation[:2000],
            'reply_capable_at_capture': bool(data.can_reply),
        },
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name,
        'action': 'incident_captured_ask_more_problem',
        'reply_text': IMAGE_MORE_PROBLEM_TEXT if data.can_reply else '',
        'should_reply': bool(data.can_reply), 'outbound_message_id': outbound.id,
        'ticket_id': ticket.id if ticket else None, 'chatbot_paused': False,
        'reply_queued_for_retry': not bool(data.can_reply),
    }


def _handle_more_problem_reply(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
):
    answer = _normalized(data.text)
    yes = answer in {
        '1', 'si', 'yes', 'claro', 'otro', 'otro problema', 'reportar otro',
        'reportar otro problema', 'nuevo', 'nuevo problema', 'tengo otro', 'hay otro',
    }
    no = answer in {
        '2', 'no', 'no gracias', 'ninguno', 'ningun otro', 'nada mas', 'nada',
        'eso es todo', 'solo eso', 'ya no', 'no tengo otro', 'no hay otro',
        'no deseo otro', 'no quiero otro', 'terminar', 'finalizar', 'cerrar', 'listo',
    }

    if not yes and not no:
        outbound = _reply(
            db,
            conversation=conversation,
            company=company,
            store=store,
            data=data,
            text=IMAGE_MORE_PROBLEM_TEXT,
        )
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name,
            'action': 'more_problem_repeat', 'reply_text': IMAGE_MORE_PROBLEM_TEXT if data.can_reply else '',
            'should_reply': bool(data.can_reply), 'outbound_message_id': outbound.id,
            'ticket_id': ticket.id if ticket else None, 'chatbot_paused': False,
        }

    _save_inbound_text(db, data=data, conversation=conversation, marker='another_problem_answer')
    closed = _close_for_validation(
        db,
        operator=operator,
        conversation=conversation,
        ticket=ticket,
        result='Reporte terminado por el usuario y enviado a validación.',
    )

    if no:
        response = _validation_closed_text(closed or ticket, company, store)
        conversation.status = 'closed'
        conversation.state = 'closed_previous_ticket'
        outbound = _reply(
            db,
            conversation=conversation,
            company=company,
            store=store,
            data=data,
            text=response,
        )
        db.add(AuditLog(
            username=operator.username,
            action='image_ticket_closed_for_validation',
            entity='conversation',
            entity_id=str(conversation.id),
            details={'ticket_id': ticket.id if ticket else None, 'answer': answer},
        ))
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name,
            'action': 'ticket_closed_pending_validation',
            'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
            'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
            'chatbot_paused': False, 'pending_validation': True,
            'reply_queued_for_retry': not bool(data.can_reply),
        }

    new_conversation = _new_conversation_from_old(
        db,
        old=conversation,
        company=company,
        store=store,
        data=data,
    )
    response = (
        '✅ El reporte anterior quedó cerrado y pasó a validación.\n\n'
        'Perfecto, iniciaremos un reporte nuevo. Cuéntame cuál es el nuevo problema.'
    )
    outbound = _reply(
        db,
        conversation=new_conversation,
        company=company,
        store=store,
        data=data,
        text=response,
    )
    db.add(AuditLog(
        username=operator.username,
        action='image_new_problem_started_after_validation',
        entity='conversation',
        entity_id=str(new_conversation.id),
        details={
            'previous_conversation_id': conversation.id,
            'previous_ticket_id': ticket.id if ticket else None,
        },
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': new_conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name,
        'action': 'new_problem_started_after_validation',
        'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False, 'pending_validation': True,
        'reply_queued_for_retry': not bool(data.can_reply),
    }


def _remove_latest_image_evidence(
    db: Session,
    *,
    conversation: Conversation,
    ticket: SupportTicket | None,
) -> int:
    if not ticket:
        return 0

    context = _latest_image_context(db, conversation.id)
    try:
        message_id = int(context.get('message_id') or 0)
    except (TypeError, ValueError):
        message_id = 0

    query = db.query(CaseAttachment).filter(
        CaseAttachment.ticket_id == ticket.id,
        CaseAttachment.content_type.like('image/%'),
    )
    if message_id:
        rows = query.filter(CaseAttachment.message_id == message_id).all()
    else:
        latest = query.order_by(CaseAttachment.id.desc()).first()
        rows = [latest] if latest else []

    for row in rows:
        db.delete(row)

    if message_id:
        message = db.get(Message, message_id)
        if message:
            payload = dict(message.raw_payload or {})
            payload['image_evidence_replaced'] = True
            payload['image_confirmation_pending'] = False
            message.raw_payload = payload

    return len(rows)


def _handle_evidence_action_reply(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
):
    answer = _normalized(data.text)
    add = answer in {
        '1', 'agregar', 'agrega', 'agregar otra', 'agregar evidencia',
        'agregar otra evidencia', 'otra', 'otra foto', 'otra evidencia',
        'conservar', 'conservar esta', 'conservar foto', 'mas evidencia',
    }
    replace = answer in {
        '2', 'reemplazar', 'reemplaza', 'reemplazar foto', 'reemplazar evidencia',
        'remplazar', 'remplaza', 'remplazar foto', 'remplazar evidencia',
        'cambiar', 'cambiar foto', 'cambiar evidencia', 'sustituir', 'sustituir foto',
    }

    if not add and not replace:
        outbound = _reply(
            db,
            conversation=conversation,
            company=company,
            store=store,
            data=data,
            text=IMAGE_EVIDENCE_ACTION_TEXT,
        )
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name,
            'action': 'image_evidence_action_repeat',
            'reply_text': IMAGE_EVIDENCE_ACTION_TEXT if data.can_reply else '',
            'should_reply': bool(data.can_reply), 'outbound_message_id': outbound.id,
            'ticket_id': ticket.id if ticket else None, 'chatbot_paused': False,
        }

    _save_inbound_text(db, data=data, conversation=conversation, marker='image_evidence_action_answer')

    removed = 0
    if replace:
        removed = _remove_latest_image_evidence(
            db,
            conversation=conversation,
            ticket=ticket,
        )
        response = IMAGE_REPLACE_TEXT
        action = 'image_evidence_replace_requested'
    else:
        response = IMAGE_ANOTHER_TEXT
        action = 'image_evidence_add_requested'

    conversation.status = 'open'
    conversation.state = IMAGE_WAIT_STATE
    outbound = _reply(
        db,
        conversation=conversation,
        company=company,
        store=store,
        data=data,
        text=response,
    )
    db.add(AuditLog(
        username=operator.username,
        action=action,
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'ticket_id': ticket.id if ticket else None,
            'answer': answer,
            'removed_attachments': removed,
        },
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name, 'action': action,
        'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False, 'removed_attachments': removed,
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
    yes = text in {
        '1', 'si', 'correcta', 'correcto', 'esta bien', 'es correcta', 'esa es', 'esa esta bien',
        'esta foto es la correcta', 'si esta foto es la correcta',
        'cerrar', 'cerrar ticket', 'finalizar', 'terminar', 'listo', 'fin', 'salir',
    }
    no = text in {
        '2', 'no', 'otra', 'otra foto', 'otra evidencia', 'enviar otra', 'quiero otra',
        'deseo enviar otra', 'agregar', 'reemplazar', 'remplazar', 'cambiar foto',
    }
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
        conversation.status = 'open'
        conversation.state = IMAGE_EVIDENCE_ACTION_STATE
        response = IMAGE_EVIDENCE_ACTION_TEXT
        action = 'image_choose_add_or_replace'
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

    closed = _close_for_validation(
        db,
        operator=operator,
        conversation=conversation,
        ticket=ticket,
        result='Evidencia fotográfica confirmada por el usuario. Ticket cerrado y enviado a validación.',
    )
    conversation.status = 'closed'
    conversation.state = 'closed_previous_ticket'
    response = _validation_closed_text(closed or ticket, company, store)
    outbound = _reply(
        db,
        conversation=conversation,
        company=company,
        store=store,
        data=data,
        text=response,
    )
    db.add(AuditLog(
        username=operator.username,
        action='image_confirmed_ticket_closed',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'ticket_id': ticket.id if ticket else None,
            'return_state': context.get('return_state'),
            'answer': text,
        },
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name,
        'action': 'image_confirmed_ticket_closed',
        'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False, 'pending_validation': True,
        'reply_queued_for_retry': not bool(data.can_reply),
    }

@router.post('/inbound')
def image_evidence_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    local_user_id, conversation, company, store, ticket = _active_context(db, data)

    if conversation and company and store and conversation.status not in {'help_pending', 'human_active'}:
        # Menu text is authoritative BEFORE media detection. WhatsApp can retain
        # the previous photo's media metadata on the next notification. Without
        # this guard, replies such as 1/2 were misclassified as another image and
        # then discarded as a duplicate, which looked like the backend stopped.
        if conversation.state == IMAGE_CONFIRM_STATE and _is_confirmation_choice(data.text):
            return _handle_confirmation_reply(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        if conversation.state == IMAGE_EVIDENCE_ACTION_STATE and _is_evidence_action_choice(data.text):
            return _handle_evidence_action_reply(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        # El primer texto después de "¿cómo sucedió?" siempre se guarda como explicación
        # y pasa a la pregunta de si existe otro problema; todavía NO cierra el ticket.
        if conversation.state == IMAGE_INCIDENT_STATE:
            return _capture_incident_and_ask_more(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        # La respuesta a "¿Deseas reportar otro problema?" decide el cierre real.
        if conversation.state == IMAGE_MORE_PROBLEM_STATE:
            return _handle_more_problem_reply(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        # If the action-state message is ordinary text (not a new image), keep
        # repeating the add/change submenu even when it is not a recognized synonym.
        if conversation.state == IMAGE_EVIDENCE_ACTION_STATE and not _is_image(data):
            return _handle_evidence_action_reply(
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
            photo_states = {IMAGE_CONFIRM_STATE, IMAGE_EVIDENCE_ACTION_STATE, IMAGE_WAIT_STATE, IMAGE_INCIDENT_STATE, IMAGE_MORE_PROBLEM_STATE}
            if not return_state or return_state in photo_states:
                return_state = conversation.state if conversation.state not in photo_states else ''
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
