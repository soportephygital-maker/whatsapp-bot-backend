import re
import unicodedata
from sqlalchemy.orm import Session
from ..models import Contact

HUMAN_HELP_PHRASES = (
    'humano',
    'persona',
    'hablar con alguien',
    'hablar con una persona',
    'quiero hablar con alguien',
    'quiero hablar con una persona',
    'asesor',
    'asesora',
    'agente humano',
    'atencion humana',
    'atencion con una persona',
    'comunicarme con alguien',
    'comunicarme con una persona',
)


def normalize_phone(value: str | None) -> str:
    return re.sub(r'\D', '', value or '')


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize('NFKD', value or '')
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower().strip()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def is_help_request(text: str | None) -> bool:
    normalized = f' {normalize_text(text)} '
    return any(f' {phrase} ' in normalized for phrase in HUMAN_HELP_PHRASES)


def is_group_message(incoming: dict) -> bool:
    sender = str(incoming.get('from') or '')
    raw = incoming.get('raw') or {}
    return bool(incoming.get('is_group') or raw.get('group_id') or sender.endswith('@g.us'))


def is_authorized_support_contact(db: Session, phone: str | None) -> bool:
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    return db.query(Contact).filter(Contact.phone == normalized, Contact.is_active.is_(True)).first() is not None


def is_known_contact(db: Session, phone: str | None) -> bool:
    # Backward-compatible alias. Contact rows now represent only the
    # administrator-managed authorized support pool, not customers.
    return is_authorized_support_contact(db, phone)


def classify_incoming(db: Session, incoming: dict) -> dict:
    support_contact = is_authorized_support_contact(db, incoming.get('from'))
    return {
        'is_group': is_group_message(incoming),
        'is_authorized_support_contact': support_contact,
        'is_known_contact': support_contact,
        # This flag is intentionally limited to an explicit request for a human.
        # Generic words such as "ayuda", "problema" or "soporte" remain in the bot flow.
        'help_requested': is_help_request(incoming.get('text')),
    }
