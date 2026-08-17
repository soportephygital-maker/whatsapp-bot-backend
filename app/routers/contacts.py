from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..database import get_db
from ..models import AuditLog, Contact, User
from ..schemas import ContactSync
from ..services.classifier import normalize_phone

router = APIRouter(prefix='/api/contacts', tags=['contacts'])


@router.post('/sync')
def sync_contacts(data: ContactSync, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    db.query(Contact).update({Contact.is_active: False})
    synced = 0
    skipped = 0
    for item in data.contacts:
        phone = normalize_phone(item.phone)
        if not phone:
            skipped += 1
            continue
        contact = db.query(Contact).filter(Contact.phone == phone).first()
        if not contact:
            contact = Contact(phone=phone)
            db.add(contact)
        contact.display_name = (item.name or '').strip() or None
        contact.source = 'mobile'
        contact.is_active = True
        contact.synced_at = now
        synced += 1
    db.add(AuditLog(username=user.username, action='sync_contacts', entity='contacts', details={'synced': synced, 'skipped': skipped}))
    db.commit()
    return {'status': 'ok', 'synced': synced, 'skipped': skipped}


@router.get('')
def list_contacts(
    search: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    query = db.query(Contact).filter(Contact.is_active.is_(True))
    if search:
        term = f'%{search.strip()}%'
        query = query.filter((Contact.phone.ilike(term)) | (Contact.display_name.ilike(term)))
    rows = query.order_by(Contact.display_name.asc().nullslast(), Contact.phone.asc()).limit(500).all()
    return [{'id': c.id, 'phone': c.phone, 'name': c.display_name, 'synced_at': c.synced_at} for c in rows]
