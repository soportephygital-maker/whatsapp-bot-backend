import re

from . import case_reports

_PHONE_RE = re.compile(r'(\+?\d[\d\s().-]{7,}\d)')


def _phone_only(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    matches = _PHONE_RE.findall(text)
    if not matches:
        return ''
    candidate = matches[-1].strip()
    digits = ''.join(ch for ch in candidate if ch.isdigit())
    if len(digits) < 8:
        return ''
    if candidate.startswith('+'):
        return '+' + digits
    if digits.startswith('52') and len(digits) >= 12:
        return '+' + digits
    return digits


def _patched_contact_label(conversation):
    if not conversation:
        return ''
    raw = str(getattr(conversation, 'wa_user_id', '') or '')
    return _phone_only(raw) or raw.rsplit(':', 1)[-1].strip()


def _patched_customer_name(db, conversation):
    if not conversation:
        return 'No identificado'
    phone = _patched_contact_label(conversation)
    if phone:
        return phone
    rows = db.query(case_reports.Message).filter(
        case_reports.Message.conversation_id == conversation.id,
        case_reports.Message.direction == 'inbound',
    ).order_by(case_reports.Message.id.desc()).limit(80).all()
    for row in rows:
        payload = row.raw_payload or {}
        for key in ('customer_name', 'sender_display', 'contact_name', 'display_name'):
            value = str(payload.get(key) or '').strip()
            number = _phone_only(value)
            if number:
                return number
            if value and value.lower() not in {'contacto', 'whatsapp'} and not value.lower().startswith('local:'):
                return value
    return 'No identificado'


case_reports._contact_label = _patched_contact_label
case_reports._customer_name = _patched_customer_name
