from sqlalchemy.orm import Session
from ..models import AppNotification


def emit_notification(
    db: Session,
    *,
    audience: str,
    event_type: str,
    title: str,
    body: str,
    event_key: str,
    details: dict | None = None,
) -> AppNotification | None:
    existing = db.query(AppNotification).filter(AppNotification.event_key == event_key).first()
    if existing:
        return None
    row = AppNotification(
        audience=audience,
        event_type=event_type,
        title=title[:200],
        body=body,
        event_key=event_key[:180],
        details=details or {},
    )
    db.add(row)
    return row


def audience_for_role(role: str) -> tuple[str, ...]:
    if role == 'admin':
        return ('admin', 'all')
    if role == 'operador':
        return ('operator', 'all')
    return ('reader',)
