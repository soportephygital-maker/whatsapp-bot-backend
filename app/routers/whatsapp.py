import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuditLog, Company, Conversation, HelpRequest, Message, Store
from ..services.classifier import classify_incoming
from ..services.decision_tree import match_response
from ..services.whatsapp import extract_messages, send_text_message

router = APIRouter(prefix='/webhooks/whatsapp', tags=['whatsapp'])


@router.get('')
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias='hub.mode'),
    hub_verify_token: str | None = Query(default=None, alias='hub.verify_token'),
    hub_challenge: str | None = Query(default=None, alias='hub.challenge'),
):
    if hub_mode == 'subscribe' and settings.whatsapp_verify_token and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge or '', media_type='text/plain')
    raise HTTPException(status_code=403, detail='Verificación de webhook inválida')


def verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not settings.whatsapp_app_secret:
        if settings.environment.lower() == 'production':
            raise HTTPException(status_code=503, detail='WHATSAPP_APP_SECRET no configurado')
        return
    if not signature_header or not signature_header.startswith('sha256='):
        raise HTTPException(status_code=401, detail='Firma de webhook faltante')
    expected = hmac.new(settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.split('=', 1)[1]
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail='Firma de webhook inválida')


@router.post('')
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    verify_signature(raw_body, request.headers.get('X-Hub-Signature-256'))
    payload = await request.json()

    for incoming in extract_messages(payload):
        wa_user_id = incoming.get('from')
        if not wa_user_id:
            continue

        classification = classify_incoming(db, incoming)
        if classification['is_group']:
            db.add(AuditLog(action='whatsapp_group_ignored', entity='whatsapp', entity_id=incoming.get('id'), details={'from': wa_user_id}))
            continue

        phone_number_id = incoming.get('phone_number_id')
        store = db.query(Store).filter(Store.whatsapp_phone_number_id == phone_number_id).first() if phone_number_id else None
        company = db.get(Company, store.company_id) if store else None
        if not company:
            db.add(AuditLog(action='whatsapp_message_ignored', entity='whatsapp', entity_id=incoming.get('id'), details={'reason': 'unknown_phone_number_id', 'phone_number_id': phone_number_id, 'from': wa_user_id}))
            continue

        duplicate = db.query(Message).filter(Message.provider_message_id == incoming.get('id')).first() if incoming.get('id') else None
        if duplicate:
            continue

        conversation = db.query(Conversation).filter(
            Conversation.wa_user_id == wa_user_id,
            Conversation.company_id == company.id,
            Conversation.status.in_(['open', 'help_pending']),
        ).order_by(Conversation.id.desc()).first()
        if not conversation:
            initial_state = (company.decision_tree or {}).get('nodo_raiz') or 'inicio'
            conversation = Conversation(company_id=company.id, wa_user_id=wa_user_id, state=initial_state)
            db.add(conversation)
            db.flush()

        db.add(Message(
            conversation_id=conversation.id,
            direction='inbound',
            sender=wa_user_id,
            body=incoming.get('text') or '',
            provider_message_id=incoming.get('id'),
            raw_payload={'provider': incoming.get('raw'), 'classification': classification},
        ))

        # Registered/authorized contacts are intentionally excluded from the bot.
        # They remain visible in the dashboard for human attention.
        if classification['is_known_contact']:
            db.add(AuditLog(
                action='registered_contact_bot_skipped',
                entity='conversation',
                entity_id=str(conversation.id),
                details={'from': wa_user_id, 'company': company.company_key},
            ))
            continue

        # The bot is only eligible for unregistered numbers whose message
        # explicitly matches an option in the configured decision tree.
        matched, response_text, next_state = match_response(
            company.decision_tree or {},
            conversation.state,
            incoming.get('text') or '',
        )

        if matched:
            conversation.state = next_state
            try:
                send_result = send_text_message(
                    wa_user_id,
                    response_text,
                    phone_number_id=phone_number_id,
                    db=db,
                )
            except Exception as exc:
                send_result = {'sent': False, 'error': str(exc)}

            db.add(Message(
                conversation_id=conversation.id,
                direction='outbound',
                sender='bot',
                body=response_text,
                raw_payload=send_result if isinstance(send_result, dict) else None,
            ))
            db.add(AuditLog(
                action='decision_tree_bot_match',
                entity='conversation',
                entity_id=str(conversation.id),
                details={'from': wa_user_id, 'state': conversation.state, 'sent': bool(send_result.get('sent')) if isinstance(send_result, dict) else False},
            ))
            if isinstance(send_result, dict) and not send_result.get('sent'):
                db.add(AuditLog(
                    action='whatsapp_send_blocked',
                    entity='conversation',
                    entity_id=str(conversation.id),
                    details={'to': wa_user_id, 'reason': send_result.get('reason') or send_result.get('error')},
                ))
            continue

        # Unknown numbers that do not match the tree never receive a bot reply.
        # If they are asking for help, create a human-support request.
        if classification['help_requested']:
            conversation.status = 'help_pending'
            existing_help = db.query(HelpRequest).filter(
                HelpRequest.conversation_id == conversation.id,
                HelpRequest.status.in_(['new', 'reviewing']),
            ).first()
            if not existing_help:
                db.add(HelpRequest(
                    company_id=company.id,
                    conversation_id=conversation.id,
                    wa_user_id=wa_user_id,
                    body=incoming.get('text') or '',
                    reason='unknown_contact_help_no_tree_match',
                    status='new',
                    is_known_contact=False,
                    is_group=False,
                ))
            db.add(AuditLog(
                action='unknown_contact_help_request',
                entity='conversation',
                entity_id=str(conversation.id),
                details={'from': wa_user_id, 'reason': 'no_decision_tree_match'},
            ))
        else:
            db.add(AuditLog(
                action='unknown_contact_no_tree_match',
                entity='conversation',
                entity_id=str(conversation.id),
                details={'from': wa_user_id},
            ))

    db.commit()
    return {'status': 'ok'}
