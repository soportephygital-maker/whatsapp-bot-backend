from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import Message, User
from . import image_evidence_patch, local_bridge

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-image-finish'])

LISTO_WORDS = {
    'listo', 'lista', 'ya', 'continuar', 'continua', 'continuemos', 'terminar', 'finalizar',
    'siguiente', 'seguir', 'adelante', 'es solo esa', 'solo esa', 'solo es esa',
    'esa es la unica', 'es la unica', 'es la unica foto', 'solo esa foto', 'nada mas',
    'no hay otra', 'no tengo otra', 'esa nada mas', 'esa nomas', 'esa es todo',
    'ya estan', 'ya estan las fotos', 'ya estan todas', 'ya mande las fotos',
    'ya envie las fotos', 'son todas', 'son todas las fotos', 'esas son todas',
    'esas son las fotos', 'ya no hay mas', 'no hay mas fotos', 'termine las fotos',
    'termine de enviar', 'termine de mandar', 'fueron todas',
}
LISTO_TEXT = '✅ Listo. La evidencia quedó registrada en el reporte.'


def _save_listo_message(db: Session, data: local_bridge.LocalInbound, conversation) -> None:
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
            'image_evidence_finish': True,
        },
    ))


def _last_outbound_is_image_confirmation(db: Session, conversation_id: int) -> bool:
    row = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'outbound',
    ).order_by(Message.id.desc()).first()
    text = str(row.body or '') if row else ''
    low = text.lower()
    return 'foto quedó registrada' in low or 'evidencia quedó registrada' in low or 'recibí una imagen' in low


def _is_finish_phrase(value: str) -> bool:
    text = image_evidence_patch._normalized(value)
    if text in LISTO_WORDS:
        return True
    phrases = (
        'es solo esa', 'solo esa', 'solo es esa', 'esa es la unica', 'es la unica foto',
        'no tengo otra', 'no hay otra', 'esa nada mas', 'esa nomas', 'podemos seguir',
        'puedes seguir', 'continua con la atencion', 'continuar con la atencion',
        'ya estan las foto', 'ya estan todas', 'ya mande las foto', 'ya envie las foto',
        'son todas las foto', 'esas son todas', 'ya no hay mas', 'no hay mas foto',
        'termine de enviar', 'termine de mandar',
    )
    return any(phrase in text for phrase in phrases)


def _next_node_message(company, state: str) -> str:
    tree = company.decision_tree or {}
    nodes = tree.get('nodos') or tree.get('nodes') or {}
    if not isinstance(nodes, dict):
        return ''
    node = nodes.get(state)
    if not isinstance(node, dict):
        return ''
    return str(node.get('mensaje') or node.get('message') or '').strip()


@router.post('/inbound')
def image_evidence_finish_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    local_user_id, conversation, company, store, ticket = image_evidence_patch._active_context(db, data)
    if conversation and company and store and _is_finish_phrase(data.text):
        in_photo_state = conversation.state in {image_evidence_patch.IMAGE_CONFIRM_STATE, image_evidence_patch.IMAGE_WAIT_STATE}
        just_confirmed = _last_outbound_is_image_confirmation(db, conversation.id)
        if in_photo_state or just_confirmed:
            context = image_evidence_patch._latest_image_context(db, conversation.id)
            return_state = str(context.get('return_state') or '').strip()
            if return_state and return_state not in {image_evidence_patch.IMAGE_CONFIRM_STATE, image_evidence_patch.IMAGE_WAIT_STATE}:
                conversation.state = return_state
            _save_listo_message(db, data, conversation)

            next_prompt = _next_node_message(company, conversation.state)
            response = LISTO_TEXT
            if next_prompt:
                response += '\n\n' + next_prompt
            else:
                response += '\n\nContinuamos con la atención.'

            outbound = image_evidence_patch._reply(
                db,
                conversation=conversation,
                company=company,
                store=store,
                data=data,
                text=response,
            )
            db.commit()
            return {
                'status': 'ok',
                'conversation_id': conversation.id,
                'company_key': company.company_key,
                'company_name': company.name,
                'store_name': store.name,
                'action': 'image_evidence_finished',
                'reply_text': response if data.can_reply else '',
                'should_reply': bool(data.can_reply),
                'outbound_message_id': outbound.id,
                'ticket_id': ticket.id if ticket else None,
                'chatbot_paused': False,
                'restored_state': conversation.state,
            }
    return image_evidence_patch.image_evidence_inbound(data=data, operator=operator, db=db)
