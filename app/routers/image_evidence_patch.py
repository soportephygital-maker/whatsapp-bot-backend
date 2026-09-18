import re
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import AuditLog, CaseAttachment, Company, Contact, Conversation, ConversationChannel, GlobalSetting, Message, Store, SupportTicket, User
from ..services import ai_learning, ticketing
from ..services.ticketing import add_ticket_followup, ticket_code
from . import global_entry_sequence_patch, local_bridge, ticketed_local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-image-evidence'])

IMAGE_CONFIRM_STATE = '__image_evidence_confirm__'
IMAGE_EVIDENCE_ACTION_STATE = '__image_evidence_add_or_replace__'
IMAGE_WAIT_STATE = '__image_evidence_wait_another__'
IMAGE_INCIDENT_STATE = '__image_evidence_incident_description__'
IMAGE_MORE_PROBLEM_STATE = '__image_evidence_more_problem__'
IMAGE_REPORT_REASON_STATE = '__image_report_reason__'
IMAGE_REPORT_REVIEW_STATE = '__image_report_review__'
IMAGE_REPORT_EDIT_FIELD_STATE = '__image_report_edit_field__'
IMAGE_REPORT_EDIT_VALUE_STATE = '__image_report_edit_value__'
IMAGE_REPORT_UNDER_REVIEW_STATE = '__image_report_under_review__'
IMAGE_CONFIRM_TEXT = (
    '📷 Recibí una imagen.\n\n'
    '¿Esta foto es la correcta?\n'
    '1️⃣ Sí, usar esta evidencia\n'
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

_IMAGE_RUNTIME_DEFAULT = {
    'confirm_text': IMAGE_CONFIRM_TEXT,
    'confirm_yes_commands': '1, sí, si, correcta, es correcta, listo, siguiente',
    'confirm_yes_response': 'Prepararé el resumen del reporte para que confirmes la información.',
    'confirm_yes_action': 'cerrar_ticket_validacion',
    'confirm_no_commands': '2, no, otra, agregar, cambiar',
    'confirm_no_response': '📷 ¿Desea agregar o cambiar la foto?\n1️⃣ Agregar\n2️⃣ Cambiar',
    'confirm_no_action': 'accion_normal',
    'submenu_text': '📷 ¿Desea agregar o cambiar la foto?\n1️⃣ Agregar\n2️⃣ Cambiar',
    'submenu_add_commands': '1, agregar, agregar otra, otra evidencia',
    'submenu_add_response': IMAGE_ANOTHER_TEXT,
    'submenu_add_action': 'esperar_imagen',
    'submenu_change_commands': '2, cambiar, reemplazar, remplazar',
    'submenu_change_response': IMAGE_REPLACE_TEXT,
    'submenu_change_action': 'reemplazar_evidencia',
}


def _command_values(value: str) -> set[str]:
    return {
        _normalized(part)
        for part in str(value or '').replace(';', ',').split(',')
        if _normalized(part)
    }


def _command_matches(text: str, configured: str) -> bool:
    normalized = _normalized(text)
    return normalized in _command_values(configured)


def _image_mode_from_ticket(ticket: SupportTicket | None) -> str:
    text = _normalized(f'{ticket.subject if ticket else ""} {ticket.description if ticket else ""}')
    if any(k in text for k in ('aimms', 'pda')):
        return 'aimms_pda'
    if any(k in text for k in ('gateway', 'gatway')):
        return 'gateway_accesorios'
    if 'accesor' in text:
        return 'accesorios'
    if any(k in text for k in ('preciador', 'precio', 'etiqueta electronica', 'esl')):
        return 'preciadores'
    return 'preciadores'


def _image_runtime_config(db: Session, company: Company, ticket: SupportTicket | None) -> dict:
    mode_key = _image_mode_from_ticket(ticket)
    row = db.get(GlobalSetting, f'image_reception_flow:{company.id}')
    value = row.value if row and isinstance(row.value, dict) else {}
    modes = value.get('modes') if isinstance(value.get('modes'), dict) else {}
    configured = modes.get(mode_key) if isinstance(modes.get(mode_key), dict) else {}
    result = dict(_IMAGE_RUNTIME_DEFAULT)
    for key, val in configured.items():
        if isinstance(val, str) and val.strip():
            result[key] = val.strip()
    result['mode_key'] = mode_key
    return result


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
    existing = db.query(Message).filter(Message.provider_message_id == provider_message_id).first()
    if existing:
        same_text = _normalized(existing.body) == _normalized(data.text)
        if same_text:
            return
        provider_message_id = f'{provider_message_id}:image-menu:{abs(hash(_normalized(data.text))) % 1000000}'
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
    closed = ticketing.close_ticket(
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
    cfg = _image_runtime_config(db, company, ticket)
    answer = _normalized(data.text)
    add = _command_matches(answer, cfg.get('submenu_add_commands', ''))
    replace = _command_matches(answer, cfg.get('submenu_change_commands', ''))

    matched_rule = 'submenu_add' if add else ('submenu_change' if replace else 'no_match')
    _trace_flow(
        db,
        operator=operator,
        conversation=conversation,
        ticket=ticket,
        data=data,
        stage='rule_evaluated',
        node='evidencia_agregar_cambiar',
        rule=matched_rule,
        action=(cfg.get('submenu_add_action') if add else cfg.get('submenu_change_action') if replace else 'repeat_prompt'),
        next_node=(cfg.get('submenu_add_next') if add else cfg.get('submenu_change_next') if replace else 'evidencia_agregar_cambiar'),
        result='matched' if (add or replace) else 'no_match',
        extra={'image_mode': cfg.get('mode_key')},
    )

    if not add and not replace:
        response = cfg.get('submenu_text') or IMAGE_EVIDENCE_ACTION_TEXT
        outbound = _reply(
            db,
            conversation=conversation,
            company=company,
            store=store,
            data=data,
            text=response,
        )
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name,
            'action': 'image_evidence_action_repeat',
            'reply_text': response if data.can_reply else '',
            'should_reply': bool(data.can_reply), 'outbound_message_id': outbound.id,
            'ticket_id': ticket.id if ticket else None, 'chatbot_paused': False,
            'image_mode': cfg.get('mode_key'),
        }

    _save_inbound_text(db, data=data, conversation=conversation, marker='image_evidence_action_answer')

    removed = 0
    if replace:
        if cfg.get('submenu_change_action') in {'reemplazar_evidencia', 'reemplazar_y_esperar_imagen'}:
            removed = _remove_latest_image_evidence(
                db,
                conversation=conversation,
                ticket=ticket,
            )
        response = cfg.get('submenu_change_response') or IMAGE_REPLACE_TEXT
        action = 'image_evidence_replace_requested'
    else:
        response = cfg.get('submenu_add_response') or IMAGE_ANOTHER_TEXT
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
            'image_mode': cfg.get('mode_key'),
        },
    ))
    db.commit()
    return {
        'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
        'company_name': company.name, 'store_name': store.name, 'action': action,
        'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False, 'removed_attachments': removed, 'image_mode': cfg.get('mode_key'),
    }


def _digits(value: str) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _report_overrides(db: Session, conversation_id: int) -> dict:
    rows = db.query(AuditLog).filter(
        AuditLog.action == 'image_report_review_override',
        AuditLog.entity == 'conversation',
        AuditLog.entity_id == str(conversation_id),
    ).order_by(AuditLog.id.asc()).all()
    merged = {}
    for row in rows:
        details = row.details if isinstance(row.details, dict) else {}
        field = str(details.get('field') or '').strip()
        value = str(details.get('value') or '').strip()
        if field and value:
            merged[field] = value
    return merged


def _contact_identity(db: Session, conversation: Conversation, data: local_bridge.LocalInbound) -> tuple[str, str]:
    sender = str(data.sender or '').strip()
    phone = sender if len(_digits(sender)) >= 8 else ''
    latest = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).first()
    payload = latest.raw_payload if latest and isinstance(latest.raw_payload, dict) else {}
    display = str(payload.get('sender_display') or payload.get('sender') or '').strip()
    if not phone and len(_digits(display)) >= 8:
        phone = display
    if not phone:
        phone = conversation.wa_user_id if not str(conversation.wa_user_id or '').startswith('local:') else 'No identificado'

    name = ''
    phone_digits = _digits(phone)
    if phone_digits:
        for row in db.query(Contact).filter(Contact.is_active.is_(True)).all():
            row_digits = _digits(row.phone)
            if row_digits and (row_digits.endswith(phone_digits[-10:]) or phone_digits.endswith(row_digits[-10:])):
                name = str(row.display_name or '').strip()
                if name:
                    break
    if not name and display and _digits(display) != _digits(phone):
        name = display
    return phone, (name or 'No identificado')


def _is_meaningful_text(value: str) -> bool:
    normalized = _normalized(value)
    if not normalized:
        return False
    if re.fullmatch(r'\d+', normalized):
        return False
    if normalized in {
        'si', 'sí', 'no', 'ok', 'listo', 'menu', 'menú', 'cerrar', 'finalizar',
        'continuar', 'siguiente', 'agregar', 'cambiar', 'reemplazar',
    }:
        return False
    return len(normalized) >= 3


def _looks_like_problem_prompt(value: str) -> bool:
    normalized = _normalized(value)
    prompt_markers = (
        'que observ', 'qué observ',
        'que paso', 'qué pasó',
        'que ocurrio', 'qué ocurrió',
        'que sucedio', 'qué sucedió',
        'como sucedio', 'cómo sucedió',
        'que problema', 'qué problema',
        'que falla', 'qué falla',
        'describe el problema', 'describe la falla',
        'que esta pasando', 'qué está pasando',
    )
    return any(marker in normalized for marker in prompt_markers)


def _incident_reason(db: Session, conversation: Conversation, ticket: SupportTicket | None) -> str:
    rows = db.query(Message).filter(
        Message.conversation_id == conversation.id,
    ).order_by(Message.id.asc()).all()

    # 1) Prefer the explicitly marked answer captured by the image flow.
    for message in reversed(rows):
        if message.direction != 'inbound':
            continue
        payload = message.raw_payload if isinstance(message.raw_payload, dict) else {}
        if payload.get('incident_description'):
            value = str(message.body or '').strip()
            if _is_meaningful_text(value):
                return value[:240]

    # 2) Recover the answer to any existing tree prompt such as
    # "¿Qué observas?", "¿Qué pasó?", "¿Qué ocurrió?" or "¿Cómo sucedió?".
    waiting_for_answer = False
    for message in rows:
        body = str(message.body or '').strip()
        if message.direction == 'outbound' and _looks_like_problem_prompt(body):
            waiting_for_answer = True
            continue
        if waiting_for_answer and message.direction == 'inbound':
            if _is_meaningful_text(body):
                return body[:240]
            # Ignore numeric/menu answers and keep looking until a real text answer arrives.

    # 3) Fall back to the structured line stored in the ticket description.
    description = str(ticket.description or '').strip() if ticket else ''
    match = re.search(r'(?im)^\s*(?:Cómo sucedió|Qué pasó|Qué ocurrió|Qué observó|Qué observa)\s*:\s*(.+)$', description)
    if match and _is_meaningful_text(match.group(1)):
        return match.group(1).strip()[:240]

    return 'Sin descripción registrada'



def _company_store_source_text(
    db: Session,
    conversation: Conversation,
    company: Company,
    store: Store,
) -> str:
    rows = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).order_by(Message.id.asc()).limit(25).all()

    company_key = _normalized(company.name)
    store_key = _normalized(store.name)
    company_candidate = ''
    store_candidate = ''

    for row in rows:
        text = str(row.body or '').strip()
        normalized = _normalized(text)
        if not text:
            continue
        if company_key and company_key in normalized and not company_candidate:
            company_candidate = text
        if store_key and store_key not in {'principal', 'general'} and store_key in normalized and not store_candidate:
            store_candidate = text
        if company_candidate and store_candidate:
            break

    if company_candidate and store_candidate and company_candidate != store_candidate:
        return f'{company_candidate} / {store_candidate}'[:240]
    if company_candidate:
        return company_candidate[:240]
    if store_candidate:
        return store_candidate[:240]
    return f'{company.name} - {store.name}'


def _looks_like_report_prompt(value: str) -> bool:
    normalized = _normalized(value)
    markers = (
        'que deseas reportar', 'qué deseas reportar',
        'cual es el problema', 'cuál es el problema',
        'que equipo falla', 'qué equipo falla',
        'que sucede', 'qué sucede',
        'que no funciona', 'qué no funciona',
        'indica la falla', 'describe la falla',
        'motivo del reporte',
    )
    return any(marker in normalized for marker in markers)


def _conversation_report_reason(
    db: Session,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
) -> str:
    rows = db.query(Message).filter(
        Message.conversation_id == conversation.id,
    ).order_by(Message.id.asc()).all()

    customer_name = _normalized(ticketed_local_bridge._conversation_name(db, conversation.id))
    company_key = _normalized(company.name)
    store_key = _normalized(store.name)

    # 1) Prefer the user's direct answer to a report/failure prompt in the tree.
    waiting_for_report = False
    for row in rows:
        raw = str(row.body or '').strip()
        normalized = _normalized(raw)
        if row.direction == 'outbound' and _looks_like_report_prompt(raw):
            waiting_for_report = True
            continue
        if waiting_for_report and row.direction == 'inbound':
            if not _is_meaningful_text(raw):
                continue
            if customer_name and normalized == customer_name:
                continue
            if company_key and company_key in normalized and len(normalized.split()) <= 8:
                continue
            if store_key and store_key not in {'principal','general'} and store_key in normalized and len(normalized.split()) <= 8:
                continue
            return raw[:240]

    # 2) Prefer a specific ticket subject when it is real text, never a number/menu option.
    subject = str(ticket.subject or '').strip() if ticket else ''
    generic = _normalized(subject)
    if (
        _is_meaningful_text(subject)
        and 'incidencia de soporte' not in generic
        and generic not in {_normalized(company.name), _normalized(store.name)}
    ):
        return subject[:240]

    # 3) Fall back to the latest meaningful inbound text, excluding control/menu data.
    excluded_markers = {
        'incident_description',
        'image_confirmation_answer',
        'report_review_confirmed',
        'report_review_edit_requested',
    }
    candidates = []
    for row in rows:
        if row.direction != 'inbound':
            continue
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        if payload.get('image_evidence') or any(payload.get(marker) for marker in excluded_markers):
            continue

        raw = str(row.body or '').strip()
        normalized = _normalized(raw)
        if not _is_meaningful_text(raw):
            continue
        if customer_name and normalized == customer_name:
            continue
        if company_key and company_key in normalized and len(normalized.split()) <= 8:
            continue
        if store_key and store_key not in {'principal','general'} and store_key in normalized and len(normalized.split()) <= 8:
            continue
        if normalized in {'hola','buen dia','buenos dias','buenas tardes','buenas noches'}:
            continue
        candidates.append(raw)

    if candidates:
        return candidates[-1][:240]
    return 'Incidencia reportada'



def _ai_report_reason(
    db: Session,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
) -> str:
    fallback = _conversation_report_reason(db, conversation, company, store, ticket)
    try:
        provider = ai_learning._provider()
        if provider not in {'openai', 'ollama'}:
            return fallback
        result = ai_learning._generate(
            provider,
            instructions=(
                'Resume el síntoma técnico reportado por el usuario en español. '
                'Devuelve únicamente el problema actual, máximo 8 palabras. '
                'Ejemplos: "AIMMS no funciona", "precio incorrecto", "pantalla rota". '
                'No escribas "incidencia de soporte", empresa, tienda, causa ni explicación.'
            ),
            prompt=f'Mensaje del usuario: {fallback}',
        )
        result = re.sub(r'\s+', ' ', str(result or '')).strip(' ."')
        normalized_result = _normalized(result)
        if (
            _is_meaningful_text(result)
            and 'incidencia de soporte' not in normalized_result
            and not re.fullmatch(r'\d+', normalized_result)
        ):
            return result[:180]
    except Exception:
        pass
    return fallback


def _report_date(ticket: SupportTicket | None, data: local_bridge.LocalInbound) -> str:
    try:
        if data.post_time:
            value = datetime.fromtimestamp(data.post_time / 1000, tz=timezone.utc)
        elif ticket and ticket.opened_at:
            value = ticket.opened_at.replace(tzinfo=timezone.utc)
        else:
            value = datetime.now(timezone.utc)
        return value.astimezone(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return datetime.utcnow().strftime('%d/%m/%Y %H:%M')


def _evidence_count(db: Session, conversation: Conversation, ticket: SupportTicket | None) -> int:
    attachment_count = (
        db.query(CaseAttachment)
        .filter(CaseAttachment.ticket_id == ticket.id, CaseAttachment.content_type.ilike('image/%'))
        .count()
        if ticket else 0
    )
    image_messages = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).all()
    message_count = 0
    seen = set()
    for row in image_messages:
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        if not payload.get('image_evidence'):
            continue
        payload_ticket = payload.get('ticket_id')
        if ticket and payload_ticket not in (None, ticket.id):
            continue
        key = row.provider_message_id or f'message:{row.id}'
        if key in seen:
            continue
        seen.add(key)
        message_count += 1
    return max(attachment_count, message_count)


def _report_review_data(
    db: Session,
    *,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
    data: local_bridge.LocalInbound,
) -> dict:
    overrides = _report_overrides(db, conversation.id)
    phone, fallback_contact_name = _contact_identity(db, conversation, data)
    saved_name_and_role = ticketed_local_bridge._conversation_name(db, conversation.id).strip()
    evidence_count = _evidence_count(db, conversation, ticket)

    values = {
        'report_reason': _ai_report_reason(db, conversation, company, store, ticket),
        'evidence': f'{evidence_count} foto' + ('' if evidence_count == 1 else 's'),
        'contact_number': phone,
        'store_company': _company_store_source_text(db, conversation, company, store),
        'contact_name': saved_name_and_role or fallback_contact_name,
        'date': _report_date(ticket, data),
    }
    values.update({k: v for k, v in overrides.items() if k in values and str(v).strip()})
    return values


def _report_review_text(values: dict) -> str:
    return (
        '📋 Se enviará el ticket a revisión por el siguiente caso:\n\n'
        f'• Motivo del reporte: {values["report_reason"]}\n'
        f'• Evidencia: {values["evidence"]}\n'
        f'• Número de contacto: {values["contact_number"]}\n'
        f'• Tienda y empresa: {values["store_company"]}\n'
        f'• Nombre y puesto de quien se comunica: {values["contact_name"]}\n'
        f'• Fecha: {values["date"]}\n\n'
        '¿Es correcta la información?\n'
        '1️⃣ Sí\n'
        '2️⃣ No, deseo cambiar algo'
    )


def _edit_fields_text() -> str:
    return (
        '✏️ ¿Qué dato deseas cambiar?\n'
        '1️⃣ Motivo del reporte\n'
        '2️⃣ Evidencia / fotos\n'
        '3️⃣ Número de contacto\n'
        '4️⃣ Nombre de tienda y empresa\n'
        '5️⃣ Nombre y puesto de quien se comunica\n'
        '6️⃣ Fecha\n'
        '0️⃣ Volver al resumen'
    )


_EDIT_FIELD_MAP = {
    '1': ('report_reason', 'Motivo del reporte'),
    '3': ('contact_number', 'Número de contacto'),
    '4': ('store_company', 'Nombre de tienda y empresa'),
    '5': ('contact_name', 'Nombre y puesto de quien se comunica'),
    '6': ('date', 'Fecha'),
}



def _latest_edit_field(db: Session, conversation_id: int) -> tuple[str, str] | None:
    row = db.query(AuditLog).filter(
        AuditLog.action == 'image_report_edit_field_selected',
        AuditLog.entity == 'conversation',
        AuditLog.entity_id == str(conversation_id),
    ).order_by(AuditLog.id.desc()).first()
    details = row.details if row and isinstance(row.details, dict) else {}
    field = str(details.get('field') or '')
    label = str(details.get('label') or '')
    return (field, label) if field else None


def _capture_report_reason_and_show_summary(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
):
    reason = re.sub(r'\s+', ' ', str(data.text or '')).strip()
    if not reason:
        reason = 'Sin descripción'
    _save_inbound_text(db, data=data, conversation=conversation, marker='report_reason')
    db.add(AuditLog(
        username=operator.username,
        action='image_report_review_override',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'ticket_id': ticket.id if ticket else None,
            'field': 'report_reason',
            'label': 'Motivo del reporte',
            'value': reason[:500],
        },
    ))
    if ticket:
        ticket.subject = reason[:240]
    try:
        with db.begin_nested():
            ai_learning.observe_report_issue(
                db,
                company_id=company.id,
                store_id=store.id,
                ticket_id=ticket.id if ticket else None,
                reason=reason,
            )
            db.flush()
    except Exception:
        pass

    conversation.status = 'open'
    conversation.state = IMAGE_REPORT_REVIEW_STATE
    values = _report_review_data(
        db,
        conversation=conversation,
        company=company,
        store=store,
        ticket=ticket,
        data=data,
    )
    response = _report_review_text(values)
    outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
    db.add(AuditLog(
        username=operator.username,
        action='image_report_summary_presented',
        entity='conversation',
        entity_id=str(conversation.id),
        details={'ticket_id': ticket.id if ticket else None, 'summary': values},
    ))
    db.commit()
    return {
        'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
        'company_name':company.name,'store_name':store.name,'action':'report_review_summary',
        'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
        'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,
        'chatbot_paused':False,'pending_user_review':True,
    }


def _handle_report_review_reply(
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
    if answer in {'1', 'si', 'correcto', 'correcta', 'esta bien', 'confirmar'}:
        _save_inbound_text(db, data=data, conversation=conversation, marker='report_review_confirmed')
        if ticket:
            ticket.status = 'open'
            ticket.closed_at = None
            ticket.closed_by = None
            ticket.close_result = None
            add_ticket_followup(
                db,
                ticket=ticket,
                username=operator.username,
                status_label='Pendiente de validación',
                message='El usuario confirmó los datos del reporte. Expediente abierto y enviado a revisión/validación.',
            )
        conversation.status = 'closed'
        conversation.state = IMAGE_REPORT_UNDER_REVIEW_STATE
        code = ticket_code(ticket, company, store) if ticket else ''
        response = (
            '✅ Tu reporte quedó registrado correctamente.\n\n'
            + (f'🎫 Ticket: {code}\n' if code else '')
            + 'Estado: ABIERTO 🟠\n'
            + 'Seguimiento: PENDIENTE DE VALIDACIÓN 🔎\n\n'
            + 'El equipo correspondiente revisará y validará la información y las evidencias del expediente.'
        )
        outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
        if ticket:
            try:
                with db.begin_nested():
                    ai_learning.learn_from_conversation(db, ticket)
                    db.flush()
            except Exception:
                pass
        db.commit()
        return {
            'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
            'company_name':company.name,'store_name':store.name,'action':'ticket_open_under_review',
            'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
            'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,
            'chatbot_paused':False,'pending_review':True,
        }

    if answer in {'2', 'no', 'cambiar', 'corregir', 'editar', 'no es correcta'}:
        _save_inbound_text(db, data=data, conversation=conversation, marker='report_review_edit_requested')
        conversation.status = 'open'
        conversation.state = IMAGE_REPORT_EDIT_FIELD_STATE
        response = _edit_fields_text()
        outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
        db.commit()
        return {
            'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
            'company_name':company.name,'store_name':store.name,'action':'report_review_edit_menu',
            'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
            'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,'chatbot_paused':False,
        }

    values = _report_review_data(db, conversation=conversation, company=company, store=store, ticket=ticket, data=data)
    response = _report_review_text(values)
    outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
    db.commit()
    return {
        'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
        'company_name':company.name,'store_name':store.name,'action':'report_review_repeat',
        'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
        'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,'chatbot_paused':False,
    }


def _handle_report_edit_field(
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
    if answer in {'0', 'volver', 'regresar', 'resumen'}:
        conversation.state = IMAGE_REPORT_REVIEW_STATE
        values = _report_review_data(db, conversation=conversation, company=company, store=store, ticket=ticket, data=data)
        response = _report_review_text(values)
    elif answer == '2' or answer in {'evidencia', 'foto', 'fotos'}:
        conversation.state = IMAGE_EVIDENCE_ACTION_STATE
        response = '📷 Para corregir la evidencia:\n1️⃣ Agregar otra foto\n2️⃣ Cambiar la foto actual'
    else:
        choice = _EDIT_FIELD_MAP.get(answer)
        if not choice:
            response = _edit_fields_text()
        else:
            field, label = choice
            conversation.state = IMAGE_REPORT_EDIT_VALUE_STATE
            db.add(AuditLog(
                username=operator.username,
                action='image_report_edit_field_selected',
                entity='conversation',
                entity_id=str(conversation.id),
                details={'ticket_id': ticket.id if ticket else None, 'field': field, 'label': label},
            ))
            response = f'✏️ Escribe el nuevo valor para: {label}.'
    outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
    db.commit()
    return {
        'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
        'company_name':company.name,'store_name':store.name,'action':'report_edit_field',
        'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
        'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,'chatbot_paused':False,
    }


def _handle_report_edit_value(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation: Conversation,
    company: Company,
    store: Store,
    ticket: SupportTicket | None,
):
    selected = _latest_edit_field(db, conversation.id)
    value = str(data.text or '').strip()
    if not selected or not value:
        conversation.state = IMAGE_REPORT_EDIT_FIELD_STATE
        response = _edit_fields_text()
    else:
        field, label = selected
        db.add(AuditLog(
            username=operator.username,
            action='image_report_review_override',
            entity='conversation',
            entity_id=str(conversation.id),
            details={'ticket_id': ticket.id if ticket else None, 'field': field, 'label': label, 'value': value[:500]},
        ))
        if ticket:
            if field == 'report_reason':
                ticket.subject = value[:240]
        conversation.state = IMAGE_REPORT_REVIEW_STATE
        values = _report_review_data(db, conversation=conversation, company=company, store=store, ticket=ticket, data=data)
        response = '✅ Dato actualizado.\n\n' + _report_review_text(values)
    outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
    db.commit()
    return {
        'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
        'company_name':company.name,'store_name':store.name,'action':'report_edit_value_saved',
        'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
        'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,'chatbot_paused':False,
    }


def _trace_flow(
    db: Session,
    *,
    operator: User,
    conversation: Conversation | None,
    ticket: SupportTicket | None,
    data: local_bridge.LocalInbound,
    stage: str,
    node: str = '',
    rule: str = '',
    action: str = '',
    next_node: str = '',
    result: str = 'ok',
    blocked_at: str = '',
    extra: dict | None = None,
) -> None:
    details = {
        'stage': stage,
        'text_received': str(data.text or '')[:1000],
        'conversation_id': conversation.id if conversation else None,
        'ticket_id': ticket.id if ticket else None,
        'state_before': conversation.state if conversation else None,
        'node': node,
        'rule': rule,
        'action': action,
        'next_node': next_node,
        'result': result,
        'blocked_at': blocked_at,
        'package_name': data.package_name,
        'device_id': data.device_id,
        'notification_key': data.notification_key,
        'post_time': data.post_time,
        'can_reply': bool(data.can_reply),
    }
    if extra:
        details.update(extra)
    db.add(AuditLog(
        username=operator.username,
        action='flow_route_trace',
        entity='conversation',
        entity_id=str(conversation.id) if conversation else None,
        details=details,
    ))


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
    cfg = _image_runtime_config(db, company, ticket)
    text = _normalized(data.text)
    yes = _command_matches(text, cfg.get('confirm_yes_commands', ''))
    no = _command_matches(text, cfg.get('confirm_no_commands', ''))

    matched_rule = 'confirm_yes' if yes else ('confirm_no' if no else 'no_match')
    _trace_flow(
        db,
        operator=operator,
        conversation=conversation,
        ticket=ticket,
        data=data,
        stage='rule_evaluated',
        node='confirmar_imagen',
        rule=matched_rule,
        action=(cfg.get('confirm_yes_action') if yes else cfg.get('confirm_no_action') if no else 'repeat_prompt'),
        next_node=(cfg.get('confirm_yes_next') if yes else cfg.get('confirm_no_next') if no else 'confirmar_imagen'),
        result='matched' if (yes or no) else 'no_match',
        extra={'image_mode': cfg.get('mode_key')},
    )

    if not yes and not no:
        response = cfg.get('confirm_text') or IMAGE_CONFIRM_TEXT
        outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name, 'action': 'image_confirmation_repeat',
            'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
            'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
            'chatbot_paused': False, 'image_mode': cfg.get('mode_key'),
        }

    _save_inbound_text(db, data=data, conversation=conversation, marker='image_confirmation_answer')
    context = _latest_image_context(db, conversation.id)

    if no:
        conversation.status = 'open'
        conversation.state = IMAGE_EVIDENCE_ACTION_STATE
        response = cfg.get('confirm_no_response') or cfg.get('submenu_text') or IMAGE_EVIDENCE_ACTION_TEXT
        outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=response)
        db.add(AuditLog(
            username=operator.username,
            action='image_choose_add_or_replace',
            entity='conversation',
            entity_id=str(conversation.id),
            details={
                'ticket_id': ticket.id if ticket else None,
                'return_state': context.get('return_state'),
                'image_mode': cfg.get('mode_key'),
            },
        ))
        db.commit()
        return {
            'status': 'ok', 'conversation_id': conversation.id, 'company_key': company.company_key,
            'company_name': company.name, 'store_name': store.name,
            'action': 'image_choose_add_or_replace',
            'reply_text': response if data.can_reply else '', 'should_reply': bool(data.can_reply),
            'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
            'chatbot_paused': False, 'image_mode': cfg.get('mode_key'),
        }

    # A correct photo first asks for a fresh free-text report reason. The answer
    # becomes the authoritative "Motivo del reporte" shown in the final review.
    conversation.status = 'open'
    conversation.state = IMAGE_REPORT_REASON_STATE
    response = '📝 Describe brevemente en un solo mensaje el motivo del reporte.'
    _trace_flow(
        db,
        operator=operator,
        conversation=conversation,
        ticket=ticket,
        data=data,
        stage='route_selected',
        node='confirmar_imagen',
        rule='confirm_yes',
        action='pedir_motivo_reporte',
        next_node='capturar_motivo_reporte',
        result='ok',
    )
    outbound = _reply(
        db,
        conversation=conversation,
        company=company,
        store=store,
        data=data,
        text=response,
    )
    db.commit()
    return {
        'status':'ok','conversation_id':conversation.id,'company_key':company.company_key,
        'company_name':company.name,'store_name':store.name,'action':'ask_report_reason',
        'reply_text':response if data.can_reply else '','should_reply':bool(data.can_reply),
        'outbound_message_id':outbound.id,'ticket_id':ticket.id if ticket else None,
        'chatbot_paused':False,'waiting_report_reason':True,
    }

def _record_image_flow_error(
    db: Session,
    *,
    operator: User,
    conversation: Conversation | None,
    data: local_bridge.LocalInbound,
    stage: str,
    exc: Exception,
) -> None:
    try:
        db.rollback()
    except Exception:
        pass
    try:
        db.add(AuditLog(
            username=operator.username,
            action='image_flow_runtime_error',
            entity='conversation',
            entity_id=str(conversation.id) if conversation else None,
            details={
                'stage': stage,
                'blocked_at': stage,
                'state_before': conversation.state if conversation else None,
                'node': conversation.state if conversation else None,
                'route_status': 'blocked',
                'error_type': type(exc).__name__,
                'error': str(exc)[:3000],
                'traceback': traceback.format_exc()[-12000:],
                'text': str(data.text or '')[:1000],
                'package_name': data.package_name,
                'device_id': data.device_id,
                'notification_key': data.notification_key,
                'post_time': data.post_time,
                'can_reply': bool(data.can_reply),
            },
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _fallback_confirmation_no(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    operator: User,
    conversation_id: int,
) -> dict:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or not conversation.company_id:
        raise RuntimeError('No se pudo recuperar la conversación después del error')
    company = db.get(Company, conversation.company_id)
    channel = db.query(ConversationChannel).filter(
        ConversationChannel.conversation_id == conversation.id
    ).first()
    store = db.get(Store, channel.store_id) if channel and channel.store_id else None
    ticket = db.query(SupportTicket).filter(
        SupportTicket.conversation_id == conversation.id
    ).first()
    if not company or not store:
        raise RuntimeError('No se pudo recuperar empresa/tienda para el submenú')

    cfg = _image_runtime_config(db, company, ticket)
    conversation.status = 'open'
    conversation.state = IMAGE_EVIDENCE_ACTION_STATE
    response = cfg.get('submenu_text') or IMAGE_EVIDENCE_ACTION_TEXT
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
        action='image_flow_recovered_confirmation_no',
        entity='conversation',
        entity_id=str(conversation.id),
        details={
            'ticket_id': ticket.id if ticket else None,
            'text': str(data.text or '')[:500],
            'recovered_to_state': IMAGE_EVIDENCE_ACTION_STATE,
        },
    ))
    db.commit()
    return {
        'status': 'ok',
        'conversation_id': conversation.id,
        'company_key': company.company_key,
        'company_name': company.name,
        'store_name': store.name,
        'action': 'image_choose_add_or_replace_recovered',
        'reply_text': response if data.can_reply else '',
        'should_reply': bool(data.can_reply),
        'outbound_message_id': outbound.id,
        'ticket_id': ticket.id if ticket else None,
        'chatbot_paused': False,
        'recovered_from_error': True,
    }


@router.post('/inbound')
def image_evidence_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    local_user_id, conversation, company, store, ticket = _active_context(db, data)

    if conversation:
        _trace_flow(
            db,
            operator=operator,
            conversation=conversation,
            ticket=ticket,
            data=data,
            stage='inbound_received',
            node=conversation.state or '',
            action='resolve_route',
            next_node=conversation.state or '',
            result='received',
            extra={
                'company_id': company.id if company else None,
                'store_id': store.id if store else None,
                'is_image': _is_image(data),
            },
        )

    if conversation and company and store and conversation.status not in {'help_pending', 'human_active'}:
        # Menu text is authoritative BEFORE media detection. WhatsApp can retain
        # the previous photo's media metadata on the next notification. Without
        # this guard, replies such as 1/2 were misclassified as another image and
        # then discarded as a duplicate, which looked like the backend stopped.
        if conversation.state == IMAGE_CONFIRM_STATE and _is_confirmation_choice(data.text):
            try:
                return _handle_confirmation_reply(
                    db=db,
                    data=data,
                    operator=operator,
                    conversation=conversation,
                    company=company,
                    store=store,
                    ticket=ticket,
                )
            except Exception as exc:
                conversation_id = conversation.id
                _record_image_flow_error(
                    db,
                    operator=operator,
                    conversation=conversation,
                    data=data,
                    stage='confirm_image_choice',
                    exc=exc,
                )
                # Option 2 must never strand the user. Recover the intended state
                # and send the add/change submenu even if an auxiliary write fails.
                if _normalized(data.text) in _command_values(
                    (_image_runtime_config(db, company, ticket).get('confirm_no_commands') or '')
                ):
                    return _fallback_confirmation_no(
                        db,
                        data=data,
                        operator=operator,
                        conversation_id=conversation_id,
                    )
                raise

        if conversation.state == IMAGE_REPORT_REASON_STATE:
            return _capture_report_reason_and_show_summary(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        if conversation.state == IMAGE_REPORT_REVIEW_STATE:
            return _handle_report_review_reply(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        if conversation.state == IMAGE_REPORT_EDIT_FIELD_STATE:
            return _handle_report_edit_field(
                db,
                data=data,
                operator=operator,
                conversation=conversation,
                company=company,
                store=store,
                ticket=ticket,
            )

        if conversation.state == IMAGE_REPORT_EDIT_VALUE_STATE:
            return _handle_report_edit_value(
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
            photo_states = {IMAGE_CONFIRM_STATE, IMAGE_EVIDENCE_ACTION_STATE, IMAGE_WAIT_STATE, IMAGE_INCIDENT_STATE, IMAGE_MORE_PROBLEM_STATE, IMAGE_REPORT_REASON_STATE, IMAGE_REPORT_REVIEW_STATE, IMAGE_REPORT_EDIT_FIELD_STATE, IMAGE_REPORT_EDIT_VALUE_STATE}
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
            previous_state = conversation.state
            conversation.state = IMAGE_CONFIRM_STATE
            _trace_flow(
                db,
                operator=operator,
                conversation=conversation,
                ticket=ticket,
                data=data,
                stage='route_selected',
                node=previous_state or 'image_received',
                rule='image_detected',
                action='save_image_and_confirm',
                next_node='confirmar_imagen',
                result='ok',
            )
            cfg = _image_runtime_config(db, company, ticket)
            confirm_text = cfg.get('confirm_text') or IMAGE_CONFIRM_TEXT
            outbound = _reply(db, conversation=conversation, company=company, store=store, data=data, text=confirm_text)
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
                'reply_text': confirm_text if data.can_reply else '', 'should_reply': bool(data.can_reply),
                'outbound_message_id': outbound.id, 'ticket_id': ticket.id if ticket else None,
                'chatbot_paused': False,
            }

        if conversation.state == IMAGE_CONFIRM_STATE:
            return _handle_confirmation_reply(
                db=db,
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

    if conversation:
        _trace_flow(
            db,
            operator=operator,
            conversation=conversation,
            ticket=ticket,
            data=data,
            stage='route_selected',
            node=conversation.state or '',
            rule='no_image_route_match',
            action='delegate_global_tree',
            next_node='global_entry_sequence',
            result='delegated',
        )
        db.commit()
    return global_entry_sequence_patch.global_entry_sequence_inbound(data=data, operator=operator, db=db)
