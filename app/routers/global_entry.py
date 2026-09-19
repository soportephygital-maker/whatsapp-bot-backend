from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_permission
from ..database import get_db
from ..models import AuditLog, GlobalSetting, User

router = APIRouter(prefix='/api/settings', tags=['global-entry'])

GLOBAL_ENTRY_KEY = 'global_entry_block'
DEFAULT_GLOBAL_ENTRY = {
    'enabled': True,
    'entry_message': 'Hola. Gracias por comunicarte con nosotros.',
    'request_message': 'Para ayudarte mejor, indícame por favor la cadena o empresa, el nombre o número de tienda y una breve descripción del problema o solicitud.',
    'matched_message': '',
    'unmatched_message': 'No logré identificar la empresa o cadena. Por favor indícame el nombre exacto de la empresa, el número o nombre de tienda y tu problema.',
}


class GlobalEntryUpdate(BaseModel):
    enabled: bool = True
    entry_message: str = Field(default=DEFAULT_GLOBAL_ENTRY['entry_message'], max_length=4000)
    request_message: str = Field(default=DEFAULT_GLOBAL_ENTRY['request_message'], max_length=4000)
    matched_message: str = Field(default='', max_length=4000)
    unmatched_message: str = Field(default=DEFAULT_GLOBAL_ENTRY['unmatched_message'], max_length=4000)


def global_entry_settings(db: Session) -> dict:
    row = db.get(GlobalSetting, GLOBAL_ENTRY_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return {**DEFAULT_GLOBAL_ENTRY, **value}


@router.get('/global-entry')
def get_global_entry(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return global_entry_settings(db)


@router.put('/global-entry')
def update_global_entry(
    data: GlobalEntryUpdate,
    user: User = Depends(require_permission('admin_access')),
    db: Session = Depends(get_db),
):
    value = data.dict()
    row = db.get(GlobalSetting, GLOBAL_ENTRY_KEY)
    if not row:
        row = GlobalSetting(key=GLOBAL_ENTRY_KEY, value=value, updated_by=user.username)
        db.add(row)
    else:
        row.value = value
        row.updated_by = user.username

    db.add(AuditLog(
        username=user.username,
        action='global_entry_updated',
        entity='global_setting',
        entity_id=GLOBAL_ENTRY_KEY,
        details={'enabled': value['enabled']},
    ))
    db.commit()
    return {'status': 'ok', 'global_entry': value}
