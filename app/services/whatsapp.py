import requests
from ..config import settings


def normalize_whatsapp_number(value: str) -> str:
    return ''.join(char for char in (value or '') if char.isdigit())


def is_recipient_allowed(to: str) -> bool:
    configured = settings.whatsapp_allowed_numbers
    if '*' in configured:
        return True
    normalized_to = normalize_whatsapp_number(to)
    allowed = {normalize_whatsapp_number(number) for number in configured}
    allowed.discard('')
    return bool(normalized_to) and normalized_to in allowed


def send_text_message(to: str, text: str) -> dict:
    if not settings.whatsapp_send_enabled:
        return {'sent': False, 'blocked': True, 'reason': 'WHATSAPP_SEND_ENABLED=false'}
    if not is_recipient_allowed(to):
        return {'sent': False, 'blocked': True, 'reason': 'recipient_not_allowed'}
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return {'sent': False, 'blocked': True, 'reason': 'WhatsApp no configurado'}
    url = f'https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages'
    headers = {'Authorization': f'Bearer {settings.whatsapp_access_token}', 'Content-Type': 'application/json'}
    payload = {
        'messaging_product': 'whatsapp',
        'to': normalize_whatsapp_number(to),
        'type': 'text',
        'text': {'body': text},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    return {'sent': True, 'provider': response.json()}


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
