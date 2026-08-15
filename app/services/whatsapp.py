import requests
from .config import settings

def send_text_message(to: str, text: str) -> dict:
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return {'sent': False, 'reason': 'WhatsApp no configurado'}
    url = f'https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages'
    headers = {'Authorization': f'Bearer {settings.whatsapp_access_token}', 'Content-Type': 'application/json'}
    payload = {'messaging_product': 'whatsapp', 'to': to, 'type': 'text', 'text': {'body': text}}
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()

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
