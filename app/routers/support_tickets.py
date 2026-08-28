import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import AuditLog, Company, Conversation, Message, Store, SupportEmailRecipient, SupportTicket, User
from ..services.coppel_tree import coppel_decision_tree
from ..services.ticketing import ticket_dict

router = APIRouter(prefix='/api', tags=['tickets-reports'])


class EmailRecipientCreate(BaseModel):
    name: str = Field(default='Soporte', min_length=1, max_length=160)
    email: str = Field(min_length=5, max_length=254)


def _company(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


@router.post('/empresas/{company_key}/plantilla-coppel')
def apply_coppel_template(company_key: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    company.decision_tree = coppel_decision_tree()
    db.add(AuditLog(username=admin.username, action='aplicar_plantilla_coppel', entity='company', entity_id=company_key))
    db.commit()
    return {'status': 'ok', 'structure': company.decision_tree}


@router.get('/empresas/{company_key}/correos-soporte')
def list_support_emails(company_key: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    rows = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company.id,
        SupportEmailRecipient.is_active.is_(True),
    ).order_by(SupportEmailRecipient.name.asc()).all()
    return [{'id': r.id, 'name': r.name, 'email': r.email} for r in rows]


@router.post('/empresas/{company_key}/correos-soporte')
def add_support_email(company_key: str, data: EmailRecipientCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    email = data.email.strip().lower()
    if '@' not in email or email.startswith('@') or email.endswith('@'):
        raise HTTPException(status_code=422, detail='Correo inválido')
    row = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.company_id == company.id,
        SupportEmailRecipient.email == email,
        SupportEmailRecipient.is_active.is_(True),
    ).first()
    if row:
        row.name = data.name.strip()
    else:
        row = SupportEmailRecipient(company_id=company.id, name=data.name.strip(), email=email)
        db.add(row)
        db.flush()
    db.add(AuditLog(username=admin.username, action='agregar_correo_soporte', entity='support_email_recipient', entity_id=str(row.id), details={'company': company_key, 'email': email}))
    db.commit()
    return {'status': 'ok', 'id': row.id, 'name': row.name, 'email': row.email}


@router.delete('/empresas/{company_key}/correos-soporte/{recipient_id}')
def delete_support_email(company_key: str, recipient_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    company = _company(company_key, db)
    row = db.query(SupportEmailRecipient).filter(
        SupportEmailRecipient.id == recipient_id,
        SupportEmailRecipient.company_id == company.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Correo no encontrado')
    row.is_active = False
    db.add(AuditLog(username=admin.username, action='eliminar_correo_soporte', entity='support_email_recipient', entity_id=str(row.id), details={'company': company_key, 'email': row.email}))
    db.commit()
    return {'status': 'ok'}


@router.get('/tickets')
def list_tickets(company_id: int | None = Query(default=None), status: str | None = Query(default=None), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(SupportTicket)
    if company_id is not None:
        query = query.filter(SupportTicket.company_id == company_id)
    if status:
        query = query.filter(SupportTicket.status == status)
    rows = query.order_by(SupportTicket.opened_at.desc()).limit(500).all()
    companies = {c.id: c for c in db.query(Company).all()}
    stores = {s.id: s for s in db.query(Store).all()}
    return [ticket_dict(t, companies.get(t.company_id), stores.get(t.store_id)) for t in rows]


@router.get('/tickets/{ticket_id}/reporte.csv')
def ticket_report(ticket_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail='Ticket no encontrado')
    company = db.get(Company, ticket.company_id)
    store = db.get(Store, ticket.store_id) if ticket.store_id else None
    conversation = db.get(Conversation, ticket.conversation_id)
    messages = db.query(Message).filter(Message.conversation_id == ticket.conversation_id).order_by(Message.created_at.asc()).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['ticket', f'TKT-{ticket.id:06d}'])
    writer.writerow(['empresa', company.name if company else ''])
    writer.writerow(['tienda', store.name if store else 'Tienda sin identificar'])
    writer.writerow(['estado', ticket.status])
    writer.writerow(['contacto', conversation.wa_user_id if conversation else ''])
    writer.writerow(['abierto', ticket.opened_at.isoformat() if ticket.opened_at else ''])
    writer.writerow(['cerrado', ticket.closed_at.isoformat() if ticket.closed_at else ''])
    writer.writerow(['cerrado_por', ticket.closed_by or ''])
    writer.writerow(['resultado', ticket.close_result or ''])
    writer.writerow([])
    writer.writerow(['fecha', 'direccion', 'remitente', 'mensaje'])
    for msg in messages:
        writer.writerow([msg.created_at.isoformat() if msg.created_at else '', msg.direction, msg.sender or '', msg.body])
    data = out.getvalue().encode('utf-8-sig')
    return Response(data, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="TKT-{ticket.id:06d}.csv"'})


@router.get('/reportes/resumen')
def reports_summary(company_id: int | None = Query(default=None), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(SupportTicket)
    if company_id is not None:
        query = query.filter(SupportTicket.company_id == company_id)
    tickets = query.all()
    companies = {c.id: c for c in db.query(Company).all()}
    stores = {s.id: s for s in db.query(Store).all()}
    by_company = defaultdict(lambda: {'open': 0, 'closed': 0, 'total': 0})
    by_store = defaultdict(lambda: {'open': 0, 'closed': 0, 'total': 0, 'company_id': None, 'company_name': ''})
    for t in tickets:
        state = 'closed' if t.status == 'closed' else 'open'
        company = companies.get(t.company_id)
        store = stores.get(t.store_id)
        ck = company.name if company else 'Sin empresa'
        sk = store.name if store else 'Tienda sin identificar'
        by_company[ck][state] += 1
        by_company[ck]['total'] += 1
        key = f'{t.company_id}:{t.store_id or 0}:{sk}'
        by_store[key][state] += 1
        by_store[key]['total'] += 1
        by_store[key]['company_id'] = t.company_id
        by_store[key]['company_name'] = ck
        by_store[key]['store_name'] = sk
    return {
        'totals': {
            'open': sum(1 for t in tickets if t.status != 'closed'),
            'closed': sum(1 for t in tickets if t.status == 'closed'),
            'total': len(tickets),
        },
        'companies': [{'company_name': name, **values} for name, values in sorted(by_company.items())],
        'stores': [values for _, values in sorted(by_store.items(), key=lambda x: (x[1]['company_name'], x[1]['store_name']))],
    }


@router.get('/reportes/general.csv')
def general_report(company_id: int | None = Query(default=None), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    summary = reports_summary(company_id=company_id, _=_, db=db)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['REPORTE GENERAL DE ATENCION'])
    writer.writerow(['abiertos', summary['totals']['open']])
    writer.writerow(['cerrados', summary['totals']['closed']])
    writer.writerow(['total', summary['totals']['total']])
    writer.writerow([])
    writer.writerow(['empresa', 'tienda', 'abiertos', 'cerrados', 'total'])
    for row in summary['stores']:
        writer.writerow([row['company_name'], row['store_name'], row['open'], row['closed'], row['total']])
    data = out.getvalue().encode('utf-8-sig')
    return Response(data, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="reporte_general_phygital.csv"'})
