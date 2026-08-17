import requests
from ..config import settings
from ..database import SessionLocal
from ..models import WhatsAppTestRecipient


def normalize_whatsapp_number(value: str) -> str:
    return ''.join(char for char in (value or '') if char.isdigit())


def is_recipient_allowed(to: str) -> bool:
    configured = settings.whatsapp_allowed_numbers
    normalized_to = normalize_whatsapp_number(to)
    if not normalized_to:
        return False

    if '*' not in configured:
        allowed = {normalize_whatsapp_number(number) for number in configured}
        allowed.discard('')
        if normalized_to not in allowed:
            return False

    test_mode = getattr(settings, 'whatsapp_test_mode', False)
    if test_mode:
        db = SessionLocal()
        try:
            return db.query(WhatsAppTestRecipient).filter(
                WhatsAppTestRecipient.phone == normalized_to,
                WhatsAppTestRecipient.is_active.is_(True),
            ).first() is not None
        finally:
            db.close()

    return True


def send_text_message(to: str, text: str, phone_number_id: str | None = None) -> dict:
    if not settings.whatsapp_send_enabled:
        return {'sent': False, 'blocked': True, 'reason': 'WHATSAPP_SEND_ENABLED=false'}
    if not is_recipient_allowed(to):
        reason = 'test_recipient_not_authorized' if getattr(settings, 'whatsapp_test_mode', False) else 'recipient_not_allowed'
        return {'sent': False, 'blocked': True, 'reason': reason}
    sender_id = phone_number_id or settings.whatsapp_phone_number_id
    if not settings.whatsapp_access_token or not sender_id:
        return {'sent': False, 'blocked': True, 'reason': 'WhatsApp no configurado'}
    url = f'https://graph.facebook.com/{settings.whatsapp_api_version}/{sender_id}/messages'
    headers = {'Authorization': f'Bearer {settings.whatsapp_access_token}', 'Content-Type': 'application/json'}
    payload = {
        'messaging_product': 'whatsapp',
        'to': normalize_whatsapp_number(to),
        'type': 'text',
        'text': {'body': text},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    return {'sent': True, 'provider': response.json(), 'phone_number_id': sender_id}


def extract_messages(payload: dict) -> list[dict]:
    messages = []
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            metadata = value.get('metadata', {})
            for message in value.get('messages', []) or []:
                text = (message.get('text') or {}).get('body', '')
                messages.append({
                    'from': message.get('from'),
                    'id': message.get('id'),
                    'text': text,
                    'phone_number_id': metadata.get('phone_number_id'),
                    'display_phone_number': metadata.get('display_phone_number'),
                    'raw': message,
                })
    return messages
