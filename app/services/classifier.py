import re
import unicodedata
from sqlalchemy.orm import Session
from ..models import Contact

HELP_KEYWORDS = (
    'ayuda', 'soporte', 'problema', 'falla', 'no funciona', 'no prende',
    'error', 'averia', 'asistencia', 'urgente', 'tecnico', 'reparar',
    'descompuesto', 'mantenimiento', 'necesito ayuda', 'pueden ayudar',
)


def normalize_phone(value: str | None) -> str:
    return re.sub(r'\D', '', value or '')


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize('NFKD', value or '')
    return ''.join(c for c in text if not unicodedata.combining(c)).lower().strip()


def is_help_request(text: str | None) -> bool:
    normalized = normalize_text(text)
    return any(keyword in normalized for keyword in HELP_KEYWORDS)


def is_group_message(incoming: dict) -> bool:
    sender = str(incoming.get('from') or '')
    raw = incoming.get('raw') or {}
    return bool(incoming.get('is_group') or raw.get('group_id') or sender.endswith('@g.us'))


def is_known_contact(db: Session, phone: str | None) -> bool:
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    return db.query(Contact).filter(Contact.phone == normalized, Contact.is_active.is_(True)).first() is not None


def classify_incoming(db: Session, incoming: dict) -> dict:
    return {
        'is_group': is_group_message(incoming),
        'is_known_contact': is_known_contact(db, incoming.get('from')),
        'help_requested': is_help_request(incoming.get('text')),
    }
