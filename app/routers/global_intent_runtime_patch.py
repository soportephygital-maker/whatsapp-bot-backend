from ..models import AuditLog, Message
from ..services.ticketing import close_ticket, ticket_code
from . import image_evidence_listo_patch, image_evidence_patch, local_bridge, ticketed_local_bridge


_HUMAN_TERMS = (
    'humano', 'asesor', 'asesora', 'soporte', 'persona', 'agente',
    'hablar con alguien', 'atencion humana', 'atencion con persona',
    'quiero un asesor', 'quiero soporte', 'quiero hablar con soporte',
)
_FINISH_TERMS = (
    'fin', 'finalizar', 'finaliza', 'terminar', 'termina', 'cerrar', 'cierra',
    'resuelto', 'resuelta', 'solucionado', 'solucionada', 'ya quedo', 'ya quedo bien',
    'ya funciona', 'problema resuelto', 'caso resuelto', 'todo listo',
)


def _normalized(value: str) -> str:
    return local_bridge._normalize_text(value)


def _contains_intent(text: str, terms: tuple[str, ...]) -> bool:
    value = _normalized(text)
    padded = f' {value} '
    for term in terms:
        normalized = _normalized(term)
        if value == normalized or f' {normalized} ' in padded:
            return True
    return False


def _human_requested(value: str) -> bool:
    return _contains_intent(value, _HUMAN_TERMS)


def _finish_requested(value: str) -> bool:
    return _contains_intent(value, _FINISH_TERMS)


# Extend the base bridge human detector globally so all lower-level flows agree.
_original_explicit_human_request = local_bridge._explicit_human_request


def _explicit_human_request(value: str) -> bool:
    return _human_requested(value) or _original_explicit_human_request(value)


local_bridge._explicit_human_request = _explicit_human_request


_original_endpoint = image_evidence_listo_patch.image_evidence_finish_inbound


def _save_global_inbound(db, data, conversation, kind: str) -> None:
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
            'global_intent': kind,
        },
    ))


def _global_endpoint(data, operator, db):
    # HUMAN / ASESOR / SOPORTE always has first priority, regardless of the
    # current tree node or photo-confirmation state.
    if _human_requested(data.text):
        result = ticketed_local_bridge.ticketed_local_inbound(data=data, operator=operator, db=db)
        if isinstance(result, dict):
            result['global_intent'] = 'human'
        return result

    # FIN / FINALIZAR / RESUELTO also works from any state. Close the current
    # ticket as resolved, preserve it, and move the conversation to the
    # post-close question instead of deleting/reusing the old ticket.
    if _finish_requested(data.text):
        _, conversation, company, store, ticket = image_evidence_patch._active_context(db, data)
        if conversation and company and store and ticket:
            _save_global_inbound(db, data, conversation, 'resolved_close')
            close_ticket(db, conversation=conversation, username='chatbot', result='resuelto')
            code = ticket_code(ticket, company, store)
            conversation.status = 'open'
            conversation.state = 'post_close_prompt'
            response = (
                '✅ Caso cerrado como resuelto.\n'
                f'🎫 Ticket: {code}\n\n'
                '¿Quieres reportar otro problema?\n'
                '1️⃣ Sí, abrir un reporte nuevo\n'
                '2️⃣ No'
            )
            outbound = image_evidence_patch._reply(
                db,
                conversation=conversation,
                company=company,
                store=store,
                data=data,
                text=response,
            )
            db.add(AuditLog(
                username=operator.username,
                action='global_resolved_close',
                entity='support_ticket',
                entity_id=str(ticket.id),
                details={'conversation_id': conversation.id, 'ticket_code': code, 'text': data.text[:500]},
            ))
            db.commit()
            return {
                'status': 'ok',
                'conversation_id': conversation.id,
                'company_key': company.company_key,
                'company_name': company.name,
                'store_name': store.name,
                'action': 'ticket_close_global',
                'global_intent': 'finish',
                'reply_text': response if data.can_reply else '',
                'should_reply': bool(data.can_reply),
                'outbound_message_id': outbound.id,
                'ticket_id': ticket.id,
                'ticket_code': code,
                'chatbot_paused': False,
                'post_close_prompt': True,
            }

    return _original_endpoint(data=data, operator=operator, db=db)


# FastAPI stores the route callable when the decorator runs. Replace both the
# module symbol and the already-created APIRoute callable before this router is
# included by the dashboard/main router hierarchy.
image_evidence_listo_patch.image_evidence_finish_inbound = _global_endpoint
for route in image_evidence_listo_patch.router.routes:
    if getattr(route, 'path', '') == '/api/local-bridge/inbound' and 'POST' in getattr(route, 'methods', set()):
        route.endpoint = _global_endpoint
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _global_endpoint
