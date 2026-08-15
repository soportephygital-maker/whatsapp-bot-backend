from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import Company, Conversation, Message, Store
from ..services.decision_tree import resolve_response
from ..services.whatsapp import extract_messages, send_text_message

router = APIRouter(prefix='/webhooks/whatsapp', tags=['whatsapp'])

@router.get('')
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias='hub.mode'),
    hub_verify_token: str | None = Query(default=None, alias='hub.verify_token'),
    hub_challenge: str | None = Query(default=None, alias='hub.challenge'),
):
    if hub_mode == 'subscribe' and settings.whatsapp_verify_token and hub_verify_token == settings.whatsapp_verify_token:
        return int(hub_challenge or '0')
    raise HTTPException(status_code=403, detail='Verificación de webhook inválida')

@router.post('')
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    for incoming in extract_messages(payload):
        wa_user_id = incoming.get('from')
        if not wa_user_id:
            continue
        store = None
        display_number = incoming.get('display_phone_number')
        if display_number:
            store = db.query(Store).filter(Store.whatsapp_number == display_number).first()
        company = db.get(Company, store.company_id) if store else db.query(Company).filter(Company.is_active.is_(True)).first()
        conversation = db.query(Conversation).filter(Conversation.wa_user_id == wa_user_id, Conversation.status == 'open').order_by(Conversation.id.desc()).first()
        if not conversation:
            conversation = Conversation(company_id=company.id if company else None, wa_user_id=wa_user_id, state='nodo_raiz')
            db.add(conversation)
            db.flush()
        db.add(Message(conversation_id=conversation.id, direction='inbound', sender=wa_user_id, body=incoming.get('text') or '', provider_message_id=incoming.get('id'), raw_payload=incoming.get('raw')))
        response_text, next_state = resolve_response(company.decision_tree if company else {}, conversation.state, incoming.get('text') or '')
        conversation.state = next_state
        send_result = send_text_message(wa_user_id, response_text)
        db.add(Message(conversation_id=conversation.id, direction='outbound', sender='bot', body=response_text, raw_payload=send_result if isinstance(send_result, dict) else None))
    db.commit()
    return {'status': 'ok'}
