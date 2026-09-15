from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Company, Contact, Conversation, ConversationChannel, Message, Store, User

router = APIRouter(prefix='/api', tags=['conversation-visibility'])


def _selected_company_ids_from_latest_inbound(db: Session, conversation_id: int) -> set[int]:
    row = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == 'inbound',
    ).order_by(Message.id.desc()).first()
    if not row:
        return set()
    payload = row.raw_payload or {}
    if payload.get('provider') != 'android_notification':
        return set()

    store_ids = []
    raw_ids = payload.get('selected_store_ids') or []
    if isinstance(raw_ids, list):
        store_ids.extend(int(value) for value in raw_ids if str(value).isdigit())
    if payload.get('store_id') is not None and str(payload.get('store_id')).isdigit():
        store_ids.append(int(payload.get('store_id')))
    if not store_ids:
        return set()

    rows = db.query(Store.company_id).filter(Store.id.in_(list(set(store_ids)))).all()
    return {int(row[0]) for row in rows if row and row[0] is not None}


@router.get('/conversaciones')
def conversations_visible_in_phone_context(
    company_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(200).all()

    if company_id is not None:
        visible = []
        for conversation in rows:
            if conversation.company_id == company_id:
                visible.append(conversation)
                continue
            # While the customer is still in the global identification step,
            # preserve visibility in every company whose store is selected on
            # the Android bridge. This prevents a generic "hola" chat from
            # appearing briefly and disappearing when the dashboard restores
            # the company selector.
            if conversation.status == 'open' and company_id in _selected_company_ids_from_latest_inbound(db, conversation.id):
                visible.append(conversation)
        rows = visible

    support_phones = {c.phone for c in db.query(Contact).filter(Contact.is_active.is_(True)).all()}
    companies = {c.id: c.name for c in db.query(Company).all()}
    target_company = db.get(Company, company_id) if company_id is not None else None

    result = []
    for conversation in rows:
        phone_digits = ''.join(ch for ch in conversation.wa_user_id if ch.isdigit())
        candidate_ids = _selected_company_ids_from_latest_inbound(db, conversation.id)
        shown_company_name = companies.get(conversation.company_id, 'Sin empresa')
        shown_company_id = conversation.company_id
        context_pending = False
        if target_company and conversation.company_id != company_id and company_id in candidate_ids:
            shown_company_name = target_company.name
            shown_company_id = company_id
            context_pending = True
        result.append({
            'id': conversation.id,
            'company_id': shown_company_id,
            'company_name': shown_company_name,
            'wa_user_id': conversation.wa_user_id,
            'authorized_support_contact': phone_digits in support_phones,
            'known_contact': phone_digits in support_phones,
            'state': conversation.state,
            'status': conversation.status,
            'updated_at': conversation.updated_at,
            'company_context_pending': context_pending,
        })
    return result
