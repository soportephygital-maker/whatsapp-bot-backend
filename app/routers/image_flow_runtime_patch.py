from . import image_evidence_listo_patch, image_evidence_patch


# Keep the image-finish step one-shot. The previous detector also matched the
# final LISTO_TEXT itself, so later messages such as "Continuar" or "Listo"
# re-entered the image finish flow forever.
def _last_outbound_is_image_confirmation(db, conversation_id: int) -> bool:
    from ..models import Message

    row = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'outbound',
    ).order_by(Message.id.desc()).first()
    text = str(row.body or '').lower() if row else ''
    return 'foto quedó registrada' in text or 'recibí una imagen' in text


image_evidence_listo_patch._last_outbound_is_image_confirmation = _last_outbound_is_image_confirmation


# Accept natural confirmations in addition to the numeric option.
_original_handle_confirmation_reply = image_evidence_patch._handle_confirmation_reply
_NATURAL_YES = {
    'es la correcta',
    'esta es la correcta',
    'esta foto es la correcta',
    'esa es la correcta',
    'si es la correcta',
    'si esta es la correcta',
    'correcta esa',
    'es esa',
}


def _handle_confirmation_reply(*, db, data, operator, conversation, company, store, ticket):
    normalized = image_evidence_patch._normalized(data.text)
    if normalized in _NATURAL_YES:
        try:
            patched_data = data.model_copy(update={'text': '1'})
        except AttributeError:
            patched_data = data.copy(update={'text': '1'})
        return _original_handle_confirmation_reply(
            db,
            data=patched_data,
            operator=operator,
            conversation=conversation,
            company=company,
            store=store,
            ticket=ticket,
        )
    return _original_handle_confirmation_reply(
        db,
        data=data,
        operator=operator,
        conversation=conversation,
        company=company,
        store=store,
        ticket=ticket,
    )


image_evidence_patch._handle_confirmation_reply = _handle_confirmation_reply
