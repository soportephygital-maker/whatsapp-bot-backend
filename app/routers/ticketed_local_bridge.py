import re
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_operator
from ..database import get_db
from ..models import AuditLog, Company, Conversation, ConversationChannel, Message, Store, SupportTicket, User
from ..services.company_routing import detect_company, normalize
from ..services.ticketing import close_ticket, ensure_ticket, notify_ticket, ticket_code, ticket_tracking
from . import local_bridge
from .global_entry import global_entry_settings

router = APIRouter(prefix='/api/local-bridge', tags=['local-bridge-tickets'])


def _global_welcome(db: Session, *, retry: bool = False) -> str:
    config = global_entry_settings(db)
    if not config.get('enabled', True):
        return ''
    if retry:
        return str(config.get('unmatched_message') or '').strip()
    parts = [
        str(config.get('entry_message') or '').strip(),
        str(config.get('request_message') or '').strip(),
    ]
    return '\n\n'.join(part for part in parts if part)


def _set_reply(
    db: Session,
    result: dict,
    text: str,
    data: local_bridge.LocalInbound,
    *,
    conversation: Conversation,
    company: Company | None,
    store: Store | None,
) -> None:
    """Replace the queued bridge reply or create one when the base bridge stayed silent."""
    text = str(text or '').strip()
    outbound_id = result.get('outbound_message_id')
    outbound = db.get(Message, outbound_id) if outbound_id else None
    if outbound:
        outbound.body = text
        payload = dict(outbound.raw_payload or {})
        if company:
            payload['company'] = company.company_key
        if store:
            payload['store'] = store.name
        outbound.raw_payload = payload
    elif text and company and store:
        outbound = local_bridge._queue_outbound(
            db,
            conversation=conversation,
            text=text,
            data=data,
            company=company,
            store=store,
        )
        result['outbound_message_id'] = outbound.id
    result['reply_text'] = text if text and data.can_reply else ''
    result['should_reply'] = bool(text and data.can_reply and result.get('outbound_message_id'))


def _selected_store_ids(data: local_bridge.LocalInbound) -> list[int]:
    return list(dict.fromkeys([*(data.selected_store_ids or []), *([data.store_id] if data.store_id else [])]))


def _selected_company_stores(data: local_bridge.LocalInbound, company_id: int, db: Session) -> list[Store]:
    ids = _selected_store_ids(data)
    if not ids:
        return []
    return db.query(Store).filter(
        Store.id.in_(ids),
        Store.company_id == company_id,
    ).order_by(Store.name.asc(), Store.id.asc()).all()


def _selected_context_store(
    data: local_bridge.LocalInbound,
    db: Session,
    company_id: int | None = None,
) -> Store | None:
    if data.store_id:
        row = db.get(Store, data.store_id)
        if row and (company_id is None or row.company_id == company_id):
            return row
    ids = _selected_store_ids(data)
    if not ids:
        return None
    query = db.query(Store).filter(Store.id.in_(ids))
    if company_id is not None:
        query = query.filter(Store.company_id == company_id)
    rows = query.order_by(Store.id.asc()).all()
    if not rows:
        return None
    if company_id is not None:
        return rows[0] if len(rows) == 1 else None
    return rows[0] if len({row.company_id for row in rows}) == 1 else None


def _store_match_score(store: Store, text: str) -> int:
    message = normalize(text)
    padded = f' {message} '
    name = normalize(store.name)
    score = 0
    if name and f' {name} ' in padded:
        score += 200
    message_digits = set(re.findall(r'\d+', message))
    store_digits = set(re.findall(r'\d+', name))
    if message_digits and store_digits:
        score += 100 * len(message_digits.intersection(store_digits))
    ignored = {'coppel', 'tienda', 'sucursal', 'centro', 'plaza', 'the', 'principal'}
    for word in name.split():
        if len(word) >= 4 and word not in ignored and f' {word} ' in padded:
            score += 10
    return score


def _match_selected_store(
    data: local_bridge.LocalInbound,
    company: Company,
    db: Session,
) -> Store | None:
    rows = _selected_company_stores(data, company.id, db)
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    normalized_choice = normalize(data.text)
    if normalized_choice.isdigit():
        index = int(normalized_choice) - 1
        if 0 <= index < len(rows):
            return rows[index]
    scored = sorted(
        ((_store_match_score(row, data.text), row) for row in rows),
        key=lambda item: (-item[0], item[1].id),
    )
    return scored[0][1] if scored and scored[0][0] > 0 else None


def _store_prompt(data: local_bridge.LocalInbound, company: Company, db: Session) -> str:
    rows = _selected_company_stores(data, company.id, db)
    if not rows:
        return (
            f'Identifiqué {company.name}, pero este teléfono no tiene una tienda de esa empresa seleccionada.\n'
            'Abre Configuración en Phygital Bot, selecciona la tienda correspondiente y vuelve a intentarlo.'
        )
    options = '\n'.join(f'{index}️⃣ {row.name}' for index, row in enumerate(rows, start=1))
    return (
        f'✅ Ya identifiqué {company.name}.\n'
        '📍 Ahora indícame el número o nombre de tu tienda.\n'
        f'{options}\n\n'
        'También puedes escribir ASESOR para hablar con una persona.'
    )


def _company_is_selected(data: local_bridge.LocalInbound, company: Company, db: Session) -> bool:
    return bool(_selected_company_stores(data, company.id, db))


def _active_conversation(db: Session, local_user_id: str) -> Conversation | None:
    return db.query(Conversation).filter(
        Conversation.wa_user_id == local_user_id,
        Conversation.status.in_(['open', 'help_pending', 'human_active']),
    ).order_by(Conversation.updated_at.desc(), Conversation.id.desc()).first()


def _explicit_company_match(db: Session, text: str) -> tuple[Company | None, dict]:
    return detect_company(db, text, fallback=None)


def _previous_explicit_company(
    db: Session,
    conversation_id: int,
    current_message_id: int | None = None,
) -> Company | None:
    query = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'inbound',
    )
    if current_message_id:
        query = query.filter(Message.id < current_message_id)
    rows = query.order_by(Message.id.asc()).all()
    identified = None
    for row in rows:
        company, routing = _explicit_company_match(db, row.body or '')
        if company and routing.get('matched'):
            identified = company
    return identified


def _prepare_pending_company_context(data: local_bridge.LocalInbound, db: Session) -> None:
    """Keep the global intake in one conversation when the user names the company later."""
    company, routing = _explicit_company_match(db, data.text)
    if not company or not routing.get('matched') or not _company_is_selected(data, company, db):
        return
    local_user_id = local_bridge._local_user_id(data)
    active = _active_conversation(db, local_user_id)
    if not active or active.status != 'open':
        return
    if _previous_explicit_company(db, active.id) is not None:
        return
    active.company_id = company.id
    active.state = local_bridge._root_state(company.decision_tree or {})
    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == active.id).first()
    if channel:
        channel.company_id = company.id
        matched_store = _match_selected_store(data, company, db)
        if matched_store:
            channel.store_id = matched_store.id
    db.flush()


def _sticky_company_input(data: local_bridge.LocalInbound, db: Session) -> local_bridge.LocalInbound:
    local_user_id = local_bridge._local_user_id(data)
    active = _active_conversation(db, local_user_id)
    if not active or not active.company_id:
        return data
    _, routing = detect_company(db, data.text, fallback=None)
    if routing.get('matched'):
        return data
    matching_stores = _selected_company_stores(data, active.company_id, db)
    if not matching_stores:
        return data
    payload = data.dict()
    payload['selected_store_ids'] = [row.id for row in matching_stores]
    if len(matching_stores) == 1:
        payload['store_id'] = matching_stores[0].id
    return local_bridge.LocalInbound(**payload)


def _action_parts(value: str | None) -> tuple[str, str]:
    raw = str(value or '').strip()
    if not raw:
        return '', ''
    base, separator, detail = raw.partition(':')
    return base.strip().lower(), detail.strip() if separator else ''


def _conversation_name(db: Session, conversation_id: int) -> str:
    rows = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).limit(40).all()
    for row in rows:
        value = str((row.raw_payload or {}).get('customer_name') or '').strip()
        if value:
            return value
    return ''


def _remember_customer_name(message: Message | None, text: str) -> str:
    name = ' '.join(str(text or '').split()).strip(' -.,')[:120]
    if message and name:
        payload = dict(message.raw_payload or {})
        payload['customer_name'] = name
        message.raw_payload = payload
    return name


def _render_placeholders(text: str, *, name: str = '', code: str = '') -> str:
    value = str(text or '')
    if name:
        value = value.replace('[NOMBRE]', name)
    else:
        value = value.replace(', [NOMBRE]', '').replace('[NOMBRE]', '')
    if code:
        value = value.replace('[NUMERO_TICKET]', code)
    return value


def _ticket_for_conversation(
    db: Session,
    *,
    company: Company,
    store: Store | None,
    conversation: Conversation,
    description: str,
    reopen: bool = False,
) -> SupportTicket:
    ticket = db.query(SupportTicket).filter(SupportTicket.conversation_id == conversation.id).first()
    if not ticket:
        return ensure_ticket(
            db,
            company=company,
            store=store,
            conversation=conversation,
            description=description,
        )
    if reopen and ticket.status == 'closed':
        return ensure_ticket(
            db,
            company=company,
            store=store,
            conversation=conversation,
            description=description,
        )
    if ticket.company_id != company.id:
        ticket.company_id = company.id
    if store and ticket.store_id != store.id:
        ticket.store_id = store.id
    return ticket


def _set_ticket_reason(ticket: SupportTicket, reason: str, text: str = '') -> None:
    if reason:
        ticket.subject = reason[:240]
    new_text = str(text or '').strip()
    current = str(ticket.description or '').strip()
    if new_text and new_text not in current:
        ticket.description = (current + ('\n\n' if current else '') + new_text)[:4000]


def _ticket_id_from_text(text: str) -> int | None:
    raw = str(text or '').strip()
    for token in re.split(r'\s+', raw):
        clean = token.strip('.,;:()[]{}<>"\'').upper()
        if clean.startswith('EDM-'):
            tail = clean.rsplit('-', 1)[-1]
            if tail.isdigit():
                return int(tail)
    exact = re.fullmatch(r'\s*(?:ticket\s*)?#?\s*(\d{1,9})\s*', raw, re.IGNORECASE)
    return int(exact.group(1)) if exact else None


def _ticket_from_text(db: Session, text: str, company_id: int) -> SupportTicket | None:
    ticket_id = _ticket_id_from_text(text)
    if ticket_id is None:
        return None
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.company_id != company_id:
        return None
    return ticket


def _remember_ticket_context(db: Session, conversation: Conversation, ticket: SupportTicket, kind: str) -> None:
    db.add(AuditLog(
        action='ticket_query_context',
        entity='conversation',
        entity_id=str(conversation.id),
        details={'ticket_id': ticket.id, 'kind': kind},
    ))


def _context_ticket(db: Session, conversation: Conversation, company_id: int) -> SupportTicket | None:
    row = db.query(AuditLog).filter(
        AuditLog.action == 'ticket_query_context',
        AuditLog.entity == 'conversation',
        AuditLog.entity_id == str(conversation.id),
    ).order_by(AuditLog.id.desc()).first()
    ticket_id = (row.details or {}).get('ticket_id') if row else None
    ticket = db.get(SupportTicket, int(ticket_id)) if str(ticket_id or '').isdigit() else None
    return ticket if ticket and ticket.company_id == company_id else None


def _ticket_status_message(db: Session, ticket: SupportTicket) -> tuple[str, str]:
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    code = ticket_code(ticket, company, store)
    tracking = ticket_tracking(db, ticket)
    reason = ticket.subject or 'Incidencia de soporte'
    if ticket.status == 'closed':
        return (
            'Encontré tu reporte.\n'
            f'🎫 Ticket: {code}\n'
            'Estado: CERRADO 🟢\n'
            f'📌 Motivo: {reason}\n'
            f'Seguimiento: {tracking["status_label"]}\n'
            f'{tracking["message"]}\n\n'
            '❓ ¿El problema está solucionado?\n'
            '1️⃣ ✅ Sí\n'
            '2️⃣ ❌ No, el problema continúa',
            'ticket_cerrado_confirmar',
        )
    return (
        'Encontré tu reporte.\n'
        f'🎫 Ticket: {code}\n'
        'Estado: ABIERTO 🟠\n'
        f'📌 Motivo: {reason}\n'
        f'Seguimiento: {tracking["status_label"]}\n'
        f'{tracking["message"]}\n\n'
        '1️⃣ Agregar información\n'
        '2️⃣ Agregar una foto o captura\n'
        '3️⃣ Hablar con soporte\n'
        '4️⃣ Regresar al menú',
        'ticket_resultado',
    )


def _visit_status_message(db: Session, ticket: SupportTicket) -> str:
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    code = ticket_code(ticket, company, store)
    tracking = ticket_tracking(db, ticket)
    updated = tracking.get('updated_at')
    if isinstance(updated, datetime):
        updated_text = updated.strftime('%d/%m/%Y %H:%M')
    else:
        updated_text = str(updated or 'Sin fecha registrada')
    return (
        'Encontré información relacionada con tu reporte.\n'
        f'🎫 Ticket: {code}\n'
        f'Estatus: {tracking["status_label"]}\n'
        f'Última actualización: {updated_text}\n'
        f'Detalle: {tracking["message"]}\n\n'
        'La fecha programada solo se mostrará cuando el equipo de soporte la registre en el seguimiento del ticket.\n\n'
        '1️⃣ Consultar otro ticket\n'
        '2️⃣ Hablar con soporte\n'
        '3️⃣ Regresar al menú'
    )


def _human_handoff(
    db: Session,
    *,
    data: local_bridge.LocalInbound,
    result: dict,
    conversation: Conversation,
    company: Company,
    store: Store,
    reason: str,
) -> dict:
    ticket = _ticket_for_conversation(
        db,
        company=company,
        store=store,
        conversation=conversation,
        description=data.text,
        reopen=True,
    )
    reason = reason or 'Solicitud de atención humana'
    _set_ticket_reason(ticket, reason, data.text)
    code = ticket_code(ticket, company, store)
    name = _conversation_name(db, conversation.id)
    response = _render_placeholders(result.get('reply_text') or '', name=name, code=code)
    if not response:
        response = (
            '👤 Claro. Voy a canalizarte con un integrante del equipo de soporte.\n'
            'Conservaré la información que ya me proporcionaste para que no tengas que repetirla.\n\n'
            f'🎫 Ticket: {code}\n'
            'Estado: ABIERTO 🟠\n'
            f'📌 Motivo: {reason}\n'
            'Enseguida continuarás la atención con nuestro equipo de soporte.'
        )
    _set_reply(
        db,
        result,
        response,
        data,
        conversation=conversation,
        company=company,
        store=store,
    )
    local_bridge._ensure_help_request(
        db,
        conversation=conversation,
        company=company,
        store=store,
        local_user_id=conversation.wa_user_id,
        body=data.text,
        reason='decision_tree_human_help',
    )
    conversation.state = 'humano'
    result.update({
        'action': f'human_help_ack:{reason}',
        'ticket_id': ticket.id,
        'ticket_code': code,
        'chatbot_paused': True,
    })
    db.commit()
    return result


@router.post('/inbound')
def ticketed_local_inbound(
    data: local_bridge.LocalInbound,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    _prepare_pending_company_context(data, db)
    effective_data = _sticky_company_input(data, db)

    pre_local_user_id = local_bridge._local_user_id(effective_data)
    pre_conversation = _active_conversation(db, pre_local_user_id)
    pre_state = pre_conversation.state if pre_conversation else None

    result = local_bridge.local_inbound(data=effective_data, operator=operator, db=db)
    conversation_id = result.get('conversation_id') if isinstance(result, dict) else None
    if not conversation_id or result.get('status') in {'duplicate', 'ignored_group', 'known_support_skipped'}:
        return result

    conversation = db.get(Conversation, conversation_id)
    if not conversation or not conversation.company_id:
        return result

    current_inbound = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).first()
    current_inbound_id = current_inbound.id if current_inbound else None
    action_base, action_detail = _action_parts(result.get('action'))

    if result.get('status') == 'human_support_paused' or conversation.status in ('help_pending', 'human_active'):
        result['should_reply'] = False
        result['reply_text'] = ''
        return result

    explicit_company, explicit_routing = _explicit_company_match(db, effective_data.text)
    previous_company = _previous_explicit_company(db, conversation.id, current_inbound_id)

    if explicit_company and explicit_routing.get('matched') and not _company_is_selected(effective_data, explicit_company, db):
        message = (
            f'Identifiqué {explicit_company.name}, pero este teléfono no tiene una tienda de esa empresa seleccionada.\n'
            'Abre Configuración en Phygital Bot, selecciona la tienda correspondiente y vuelve a intentarlo.'
        )
        fallback_company = db.get(Company, conversation.company_id)
        fallback_store = _selected_context_store(effective_data, db, fallback_company.id if fallback_company else None)
        _set_reply(
            db,
            result,
            message,
            effective_data,
            conversation=conversation,
            company=fallback_company,
            store=fallback_store,
        )
        result['action'] = 'company_not_enabled_on_device'
        db.commit()
        return result

    if previous_company is None and not explicit_routing.get('matched'):
        attempts = db.query(func.count(Message.id)).filter(
            Message.conversation_id == conversation.id,
            Message.direction == 'inbound',
        ).scalar() or 1
        message = _global_welcome(db, retry=attempts > 1)
        fallback_company = db.get(Company, conversation.company_id)
        fallback_store = _selected_context_store(effective_data, db, fallback_company.id if fallback_company else None)
        if message:
            _set_reply(
                db,
                result,
                message,
                effective_data,
                conversation=conversation,
                company=fallback_company,
                store=fallback_store,
            )
        result.update({
            'action': 'global_entry',
            'company_identified': False,
            'ticket_id': None,
            'ticket_code': None,
        })
        db.commit()
        return result

    company = explicit_company if explicit_company and explicit_routing.get('matched') else previous_company
    if not company:
        company = db.get(Company, conversation.company_id)
    if not company:
        return result

    channel = db.query(ConversationChannel).filter(ConversationChannel.conversation_id == conversation.id).first()
    if not channel:
        channel = ConversationChannel(conversation_id=conversation.id, company_id=company.id)
        db.add(channel)
        db.flush()

    switching_company = bool(explicit_company and conversation.company_id != explicit_company.id)
    if switching_company:
        company = explicit_company
        conversation.company_id = company.id
        channel.company_id = company.id
        conversation.state = 'identificar_tienda'
        pre_state = None

    selected_store = _match_selected_store(effective_data, company, db)
    current_store = db.get(Store, channel.store_id) if channel.store_id else None
    if current_store and current_store.company_id != company.id:
        current_store = None

    first_company_identification = previous_company is None and bool(explicit_routing.get('matched'))
    needs_store = switching_company or first_company_identification or pre_state == 'identificar_tienda' or conversation.state == 'identificar_tienda'

    if needs_store:
        if selected_store is None:
            conversation.company_id = company.id
            channel.company_id = company.id
            channel.store_id = None
            conversation.state = 'identificar_tienda'
            prompt = _store_prompt(effective_data, company, db)
            support_stores = _selected_company_stores(effective_data, company.id, db)
            _set_reply(
                db,
                result,
                prompt,
                effective_data,
                conversation=conversation,
                company=company,
                store=support_stores[0] if support_stores else None,
            )
            result.update({
                'action': 'company_store_required',
                'company_key': company.company_key,
                'company_name': company.name,
                'company_identified': True,
                'store_name': None,
                'ticket_id': None,
                'ticket_code': None,
            })
            db.commit()
            return result

        channel.company_id = company.id
        channel.store_id = selected_store.id
        conversation.company_id = company.id
        conversation.state = local_bridge._root_state(company.decision_tree or {})
        tree = company.decision_tree or {}
        root = local_bridge._root_state(tree)
        root_message = str((tree.get('nodos') or {}).get(root, {}).get('mensaje') or '').strip()
        _set_reply(
            db,
            result,
            root_message,
            effective_data,
            conversation=conversation,
            company=company,
            store=selected_store,
        )
        ticket = _ticket_for_conversation(
            db,
            company=company,
            store=selected_store,
            conversation=conversation,
            description=effective_data.text,
        )
        result.update({
            'action': 'company_welcome',
            'routing': explicit_routing if explicit_routing.get('matched') else result.get('routing'),
            'company_key': company.company_key,
            'company_name': company.name,
            'company_identified': True,
            'store_name': selected_store.name,
            'ticket_id': ticket.id,
            'ticket_code': ticket_code(ticket, company, selected_store),
        })
        db.commit()
        return result

    store = current_store or selected_store or _selected_context_store(effective_data, db, company.id)
    if store:
        channel.company_id = company.id
        channel.store_id = store.id

    if action_base in {'human_help', 'human_help_ack'} and not store:
        conversation.state = 'identificar_tienda'
        prompt = _store_prompt(effective_data, company, db)
        support_stores = _selected_company_stores(effective_data, company.id, db)
        _set_reply(
            db,
            result,
            prompt,
            effective_data,
            conversation=conversation,
            company=company,
            store=support_stores[0] if support_stores else None,
        )
        result['action'] = 'human_help_store_required'
        db.commit()
        return result

    if action_base in {'human_help', 'human_help_ack'} and store:
        return _human_handoff(
            db,
            data=effective_data,
            result=result,
            conversation=conversation,
            company=company,
            store=store,
            reason=action_detail,
        )

    tree = company.decision_tree or {}
    root = local_bridge._root_state(tree)

    if pre_state == root and action_base.startswith('no_match'):
        name = _remember_customer_name(current_inbound, effective_data.text)
        menu_message = str((tree.get('nodos') or {}).get('menu', {}).get('mensaje') or 'Gracias. ¿En qué puedo ayudarte?')
        menu_message = _render_placeholders(menu_message, name=name)
        conversation.state = 'menu'
        _set_reply(
            db,
            result,
            menu_message,
            effective_data,
            conversation=conversation,
            company=company,
            store=store,
        )
        ticket = _ticket_for_conversation(
            db,
            company=company,
            store=store,
            conversation=conversation,
            description=effective_data.text,
        )
        db.add(AuditLog(
            action='capture_customer_name',
            entity='conversation',
            entity_id=str(conversation.id),
            details={'name': name, 'company': company.company_key, 'store': store.name if store else None},
        ))
        result.update({
            'action': 'capture_name',
            'company_identified': True,
            'ticket_id': ticket.id,
            'ticket_code': ticket_code(ticket, company, store),
        })
        db.commit()
        return result

    result['company_identified'] = True
    action_base, action_detail = _action_parts(result.get('action'))
    reopen = action_base == 'ticket_open'
    conversation_ticket = _ticket_for_conversation(
        db,
        company=company,
        store=store,
        conversation=conversation,
        description=effective_data.text,
        reopen=reopen,
    )

    target_ticket = conversation_ticket
    if action_base in {'ticket_add_info', 'ticket_reopen'}:
        target_ticket = _context_ticket(db, conversation, company.id) or conversation_ticket

    if action_base in {'ticket_open', 'ticket_reopen', 'ticket_close'}:
        _set_ticket_reason(target_ticket, action_detail, effective_data.text)

    if action_base == 'ticket_close':
        close_ticket(
            db,
            conversation=conversation,
            username='chatbot',
            result=action_detail or 'solucionado',
        )
    elif action_base == 'ticket_reopen':
        if target_ticket.status == 'closed':
            target_company = db.get(Company, target_ticket.company_id)
            target_store = db.get(Store, target_ticket.store_id) if target_ticket.store_id else None
            target_conversation = db.get(Conversation, target_ticket.conversation_id)
            target_ticket.status = 'open'
            target_ticket.opened_at = datetime.utcnow()
            target_ticket.closed_at = None
            target_ticket.closed_by = None
            target_ticket.close_result = None
            if target_company and target_conversation:
                notify_ticket(db, target_ticket, target_company, target_store, target_conversation, 'opened')
    elif action_base == 'ticket_add_info':
        _set_ticket_reason(target_ticket, target_ticket.subject or 'Incidencia de soporte', effective_data.text)
        db.add(AuditLog(
            username=operator.username,
            action='ticket_customer_information_added',
            entity='support_ticket',
            entity_id=str(target_ticket.id),
            details={'conversation_id': conversation.id, 'text': effective_data.text[:1000]},
        ))
    elif action_base == 'finish':
        conversation.status = 'closed'
        conversation.state = 'fin'

    name = _conversation_name(db, conversation.id)
    target_company = db.get(Company, target_ticket.company_id) or company
    target_store = db.get(Store, target_ticket.store_id) if target_ticket.store_id else store
    target_code = ticket_code(target_ticket, target_company, target_store)
    rendered = _render_placeholders(result.get('reply_text') or '', name=name, code=target_code)
    if rendered != str(result.get('reply_text') or ''):
        _set_reply(
            db,
            result,
            rendered,
            effective_data,
            conversation=conversation,
            company=company,
            store=store,
        )

    if action_base == 'ticket_status':
        requested = _ticket_from_text(db, effective_data.text, company.id)
        if not requested:
            message = (
                'No encontré un ticket con ese número.\n'
                'Revisa que esté escrito correctamente e inténtalo nuevamente.\n\n'
                '1️⃣ Escribir otro número\n'
                '2️⃣ Hablar con soporte\n'
                '3️⃣ Regresar al menú'
            )
            conversation.state = 'consulta_ticket'
            _set_reply(
                db,
                result,
                message,
                effective_data,
                conversation=conversation,
                company=company,
                store=store,
            )
            result['action'] = 'ticket_not_found'
        else:
            message, next_state = _ticket_status_message(db, requested)
            conversation.state = next_state
            _remember_ticket_context(db, conversation, requested, 'ticket')
            _set_reply(
                db,
                result,
                message,
                effective_data,
                conversation=conversation,
                company=company,
                store=store,
            )
            requested_company = db.get(Company, requested.company_id)
            requested_store = db.get(Store, requested.store_id) if requested.store_id else None
            result.update({
                'ticket_id': requested.id,
                'ticket_code': ticket_code(requested, requested_company, requested_store),
                'action': 'ticket_status',
            })
    elif action_base == 'visit_status':
        requested = _ticket_from_text(db, effective_data.text, company.id)
        if not requested:
            message = (
                'No encontré un ticket con ese número.\n'
                'Revisa que esté escrito correctamente.\n\n'
                '1️⃣ Consultar otro ticket\n'
                '2️⃣ Hablar con soporte\n'
                '3️⃣ Regresar al menú'
            )
            conversation.state = 'consulta_visita'
            _set_reply(
                db,
                result,
                message,
                effective_data,
                conversation=conversation,
                company=company,
                store=store,
            )
            result['action'] = 'visit_ticket_not_found'
        else:
            conversation.state = 'visita_resultado'
            _remember_ticket_context(db, conversation, requested, 'visit')
            _set_reply(
                db,
                result,
                _visit_status_message(db, requested),
                effective_data,
                conversation=conversation,
                company=company,
                store=store,
            )
            requested_company = db.get(Company, requested.company_id)
            requested_store = db.get(Store, requested.store_id) if requested.store_id else None
            result.update({
                'ticket_id': requested.id,
                'ticket_code': ticket_code(requested, requested_company, requested_store),
                'action': 'visit_status',
            })

    result.setdefault('ticket_id', target_ticket.id)
    result.setdefault('ticket_code', target_code)
    db.commit()
    return result
