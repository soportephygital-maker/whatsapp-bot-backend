from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import (
    AppNotification,
    AuditLog,
    Company,
    CompanyFile,
    Conversation,
    ConversationChannel,
    HelpRequest,
    Message,
    Store,
    SupportContact,
    User,
)
from ..schemas import CompanyCreate, CompanyIdentificationUpdate, CompanyUpdate, DecisionTreeUpdate, StoreCreate, StoreUpdate
from ..services.company_routing import base_decision_tree, identification_profile

router = APIRouter(prefix='/api/empresas', tags=['empresas'])


def _company(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


def _merge_base_template(current: dict) -> tuple[dict, int, int]:
    base = base_decision_tree()
    merged = deepcopy(current or {})
    if 'identificacion' not in merged:
        merged['identificacion'] = deepcopy(base.get('identificacion') or {})
    if not merged.get('nodo_raiz'):
        merged['nodo_raiz'] = base.get('nodo_raiz') or 'inicio'

    nodes = deepcopy(merged.get('nodos') or {})
    added_nodes = 0
    added_options = 0
    for node_key, base_node in (base.get('nodos') or {}).items():
        if node_key not in nodes:
            nodes[node_key] = deepcopy(base_node)
            added_nodes += 1
            added_options += len(base_node.get('opciones') or [])
            continue

        node = deepcopy(nodes[node_key] or {})
        if not str(node.get('mensaje') or '').strip():
            node['mensaje'] = base_node.get('mensaje') or ''
        options = list(node.get('opciones') or [])
        existing_commands = {
            str(option.get('comando') or '').strip().lower()
            for option in options
            if str(option.get('comando') or '').strip()
        }
        for option in base_node.get('opciones') or []:
            command = str(option.get('comando') or '').strip().lower()
            if command and command not in existing_commands:
                options.append(deepcopy(option))
                existing_commands.add(command)
                added_options += 1
        node['opciones'] = options
        nodes[node_key] = node

    merged['nodos'] = nodes
    return merged, added_nodes, added_options


@router.get('/listar')
def list_companies(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    companies = db.query(Company).order_by(Company.name.asc()).all()
    return [{
        'id': c.id,
        'empresa_id': c.company_key,
        'nombre': c.name,
        'activa': c.is_active,
        'tiendas': [{'id': s.id, 'nombre': s.name, 'whatsapp': s.whatsapp_number, 'phone_number_id': s.whatsapp_phone_number_id} for s in c.stores],
        'arbol_decisiones': c.decision_tree,
        'identificacion': identification_profile(c),
    } for c in companies]


@router.post('/crear')
def create_company(data: CompanyCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Company).filter(Company.company_key == data.company_key).first():
        raise HTTPException(status_code=409, detail='La empresa ya existe')
    company = Company(company_key=data.company_key.strip(), name=data.name.strip(), decision_tree=base_decision_tree())
    db.add(company)
    db.flush()
    count = max(len(data.stores), len(data.whatsapp_numbers), len(data.phone_number_ids))
    if count == 0:
        db.add(Store(company_id=company.id, name='Principal'))
    else:
        for i in range(count):
            name = data.stores[i] if i < len(data.stores) else f'Tienda {i + 1}'
            number = data.whatsapp_numbers[i] if i < len(data.whatsapp_numbers) else None
            phone_number_id = data.phone_number_ids[i] if i < len(data.phone_number_ids) else None
            db.add(Store(company_id=company.id, name=name.strip(), whatsapp_number=(number or '').strip() or None, whatsapp_phone_number_id=(phone_number_id or '').strip() or None))
    db.add(AuditLog(username=admin.username, action='crear_empresa', entity='company', entity_id=data.company_key, details={'template': 'base_v1'}))
    db.commit()
    return {'status': 'ok', 'empresa_id': company.company_key}


@router.get('/{company_key}/tiendas')
def list_stores(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    return [{'id': s.id, 'nombre': s.name} for s in sorted(company.stores, key=lambda row: (row.name or '').lower())]


@router.post('/{company_key}/tiendas')
def create_store(company_key: str, data: StoreCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    name = data.name.strip()
    if db.query(Store).filter(Store.company_id == company.id, Store.name == name).first():
        raise HTTPException(status_code=409, detail='Ya existe una tienda con ese nombre')
    store = Store(company_id=company.id, name=name)
    db.add(store)
    db.flush()
    db.add(AuditLog(username=admin.username, action='crear_tienda', entity='store', entity_id=str(store.id), details={'company': company_key, 'name': name}))
    db.commit()
    return {'status': 'ok', 'id': store.id, 'nombre': store.name}


@router.patch('/{company_key}/tiendas/{store_id}')
def update_store(company_key: str, store_id: int, data: StoreUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    store = db.query(Store).filter(Store.id == store_id, Store.company_id == company.id).first()
    if not store:
        raise HTTPException(status_code=404, detail='Tienda no encontrada')
    store.name = data.name.strip()
    db.add(AuditLog(username=admin.username, action='actualizar_tienda', entity='store', entity_id=str(store.id), details={'company': company_key, 'name': store.name}))
    db.commit()
    return {'status': 'ok', 'id': store.id, 'nombre': store.name}


@router.delete('/{company_key}/tiendas/{store_id}')
def delete_store(company_key: str, store_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    store = db.query(Store).filter(Store.id == store_id, Store.company_id == company.id).first()
    if not store:
        raise HTTPException(status_code=404, detail='Tienda no encontrada')
    if db.query(Store).filter(Store.company_id == company.id).count() <= 1:
        raise HTTPException(status_code=400, detail='La empresa debe conservar al menos una tienda')
    db.query(ConversationChannel).filter(ConversationChannel.store_id == store.id).update({'store_id': None}, synchronize_session=False)
    name = store.name
    db.delete(store)
    db.add(AuditLog(username=admin.username, action='eliminar_tienda', entity='store', entity_id=str(store_id), details={'company': company_key, 'name': name}))
    db.commit()
    return {'status': 'ok'}


@router.patch('/{company_key}')
def update_company(company_key: str, data: CompanyUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    if data.name is not None:
        company.name = data.name.strip() or company.name
    if data.is_active is not None:
        company.is_active = data.is_active
    db.add(AuditLog(username=admin.username, action='actualizar_empresa', entity='company', entity_id=company_key, details={'name': company.name, 'is_active': company.is_active}))
    db.commit()
    return {'status': 'ok', 'empresa_id': company.company_key, 'nombre': company.name, 'activa': company.is_active}


@router.delete('/{company_key}')
def delete_company(company_key: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    company_id = company.id
    company_name = company.name

    conversations = db.query(Conversation).filter(Conversation.company_id == company_id).all()
    conversation_ids = [row.id for row in conversations]
    help_rows = db.query(HelpRequest).filter(HelpRequest.company_id == company_id).all()
    help_ids = [row.id for row in help_rows]

    if conversation_ids:
        db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(ConversationChannel).filter(ConversationChannel.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(HelpRequest).filter(HelpRequest.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)
    db.query(HelpRequest).filter(HelpRequest.company_id == company_id).delete(synchronize_session=False)
    db.query(SupportContact).filter(SupportContact.company_id == company_id).delete(synchronize_session=False)
    db.query(CompanyFile).filter(CompanyFile.company_id == company_id).delete(synchronize_session=False)
    db.query(Store).filter(Store.company_id == company_id).delete(synchronize_session=False)

    for notification in db.query(AppNotification).all():
        details = notification.details or {}
        if details.get('help_request_id') in help_ids or details.get('company') == company_name:
            db.delete(notification)

    db.delete(company)
    db.add(AuditLog(
        username=admin.username,
        action='eliminar_empresa',
        entity='company',
        entity_id=company_key,
        details={'company_name': company_name, 'conversations_deleted': len(conversation_ids), 'help_requests_deleted': len(help_ids)},
    ))
    db.commit()
    return {'status': 'ok', 'deleted_company': company_key}


@router.get('/{company_key}/identificacion')
def get_identification(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return identification_profile(_company(company_key, db))


@router.put('/{company_key}/identificacion')
def update_identification(company_key: str, data: CompanyIdentificationUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    tree = dict(company.decision_tree or {})
    profile = {
        'aliases': list(dict.fromkeys(v.strip() for v in data.aliases if v.strip())),
        'keywords': list(dict.fromkeys(v.strip() for v in data.keywords if v.strip())),
        'tags': list(dict.fromkeys(v.strip() for v in data.tags if v.strip())),
    }
    tree['identificacion'] = profile
    company.decision_tree = tree
    db.add(AuditLog(username=admin.username, action='actualizar_identificacion_empresa', entity='company', entity_id=company_key, details=profile))
    db.commit()
    return {'status': 'ok', 'identificacion': profile}


@router.post('/{company_key}/plantilla-base')
def apply_base_template(company_key: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    merged, added_nodes, added_options = _merge_base_template(company.decision_tree or {})
    company.decision_tree = merged
    db.add(AuditLog(
        username=admin.username,
        action='combinar_plantilla_base',
        entity='company',
        entity_id=company_key,
        details={'added_nodes': added_nodes, 'added_options': added_options},
    ))
    db.commit()
    return {'status': 'ok', 'structure': merged, 'added_nodes': added_nodes, 'added_options': added_options}


@router.get('/{company_key}/arbol')
def get_tree(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _company(company_key, db).decision_tree or {}


@router.put('/{company_key}/arbol')
def update_tree(company_key: str, data: DecisionTreeUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    current = company.decision_tree or {}
    incoming = dict(data.structure or {})
    if 'identificacion' not in incoming and current.get('identificacion'):
        incoming['identificacion'] = current['identificacion']
    company.decision_tree = incoming
    db.add(AuditLog(username=admin.username, action='actualizar_arbol', entity='company', entity_id=company_key))
    db.commit()
    return {'status': 'ok'}
