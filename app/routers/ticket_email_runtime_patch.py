from html import escape

from ..services import case_event_notifications, case_reports, ticketing


def _problem(ticket, company=None, store=None) -> str:
    try:
        return case_reports._problem_summary(ticket, company, store)
    except Exception:
        subject = ' '.join(str(ticket.subject or '').split()).strip()
        if subject and subject.lower() not in {'incidencia', 'incidencia de soporte', 'soporte', 'reporte'}:
            return subject if subject.endswith(('.', '!', '?')) else subject + '.'
        raw = str(ticket.description or '').replace('\r', '\n')
        candidates = []
        for part in raw.split('\n'):
            value = ' '.join(part.split()).strip(' -•')
            if not value or value.isdigit():
                continue
            low = value.lower()
            if low.startswith(('ticket:', 'estado:', 'nuestro equipo', 'regresar al menú', 'hablar con soporte', 'finalizar conversación')):
                continue
            candidates.append(value)
        value = candidates[-1] if candidates else 'Falla reportada sin detalle suficiente'
        return value if value.endswith(('.', '!', '?')) else value + '.'


def _ticket_message(ticket, company, store, conversation, event):
    code = ticketing.ticket_code(ticket, company, store)
    store_name = store.name if store else 'Tienda sin identificar'
    problem = _problem(ticket, company, store)
    status = 'CERRADO' if event == 'closed' else 'ABIERTO'
    subject = (
        f'[{code}] Caso cerrado - {company.name} / {store_name}'
        if event == 'closed'
        else f'[{code}] Nueva incidencia - {company.name} / {store_name}'
    )
    body = (
        f'Ticket: {code}\nEstado: {status}\nEmpresa: {company.name}\nTienda: {store_name}\n'
        f'Contacto: {conversation.wa_user_id}\nFalla reportada: {problem}\n'
    )
    if event == 'closed':
        body += f'Resultado del cierre: {ticket.close_result or "cerrado"}\nCerrado por: {ticket.closed_by or "sistema"}\n'
    html = f'''<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;background:#f6f7f9;padding:24px;color:#202124;">
    <div style="max-width:620px;margin:auto;background:white;border:1px solid #e5e7eb;border-radius:14px;padding:26px;">
      <div style="font-size:13px;color:#6b7280;">Ticket de soporte</div><h2 style="margin:5px 0 18px;">{escape(code)}</h2>
      <p><b>Empresa:</b> {escape(company.name or '')}</p><p><b>Tienda:</b> {escape(store_name)}</p><p><b>Contacto:</b> {escape(conversation.wa_user_id or '')}</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;"><div style="font-size:13px;color:#6b7280;margin-bottom:6px;">Falla reportada</div>
      <div style="font-size:17px;line-height:1.5;font-weight:600;">{escape(problem)}</div>
      {f'<p style="margin-top:18px;"><b>Resultado:</b> {escape(ticket.close_result or "cerrado")}</p>' if event == 'closed' else ''}
    </div></body></html>'''
    return subject, body, html


def _case_plain(event, ticket, company, store, conversation, photo_count):
    code = ticketing.ticket_code(ticket, company, store)
    store_name = store.name if store else 'Tienda sin identificar'
    problem = _problem(ticket, company, store)
    labels = {
        'ticket_opened': 'NUEVA INCIDENCIA', 'human_required': 'REQUIERE ATENCIÓN HUMANA',
        'status_changed': 'CAMBIO DE ESTADO', 'closed_no_human': 'CERRADO SIN ATENCIÓN HUMANA',
        'resolved_success': 'CONCLUIDO CON ÉXITO',
    }
    return (
        f'Ticket: {code}\nEvento: {labels.get(event, event)}\nEmpresa: {company.name}\nTienda: {store_name}\n'
        f'Contacto: {conversation.wa_user_id}\nFalla reportada: {problem}\nResultado: {ticket.close_result or "Pendiente"}\n'
        f'Evidencia fotográfica: {photo_count} foto(s).\n'
        'Se adjuntan el expediente de conversación y el resumen ejecutivo.\n'
    )


def _case_html(event, ticket, company, store, conversation, photo_count):
    code = escape(ticketing.ticket_code(ticket, company, store))
    store_name = escape(store.name if store else 'Tienda sin identificar')
    problem = escape(_problem(ticket, company, store))
    labels = {
        'ticket_opened': ('Nueva incidencia', '#ffedd5', '#9a3412'),
        'human_required': ('Requiere atención humana', '#fee2e2', '#991b1b'),
        'status_changed': ('Cambio de estado', '#dbeafe', '#1d4ed8'),
        'closed_no_human': ('Cerrado', '#dcfce7', '#166534'),
        'resolved_success': ('Resuelto con éxito', '#dcfce7', '#166534'),
    }
    label, bg, fg = labels.get(event, (event, '#f3f4f6', '#374151'))
    return f'''<!doctype html><html><body style="margin:0;padding:24px;background:#f6f7f9;font-family:Arial,Helvetica,sans-serif;color:#202124;">
<table role="presentation" width="100%"><tr><td align="center"><table role="presentation" width="100%" style="max-width:560px;background:#fff;border:1px solid #e5e7eb;border-radius:16px;"><tr><td style="padding:28px;">
<table role="presentation" width="100%"><tr><td><div style="font-size:14px;color:#6b7280">Ticket de soporte</div><div style="font-size:18px;font-weight:700">{code}</div></td><td align="right"><span style="display:inline-block;background:{bg};color:{fg};padding:7px 14px;border-radius:999px;font-weight:600">{escape(label)}</span></td></tr></table>
<div style="height:1px;background:#e5e7eb;margin:20px 0"></div><table role="presentation" width="100%"><tr><td style="padding:7px 0;color:#6b7280">Empresa</td><td align="right"><b>{escape(company.name)}</b></td></tr><tr><td style="padding:7px 0;color:#6b7280">Tienda</td><td align="right"><b>{store_name}</b></td></tr><tr><td style="padding:7px 0;color:#6b7280">Contacto</td><td align="right"><b>{escape(conversation.wa_user_id)}</b></td></tr><tr><td style="padding:7px 0;color:#6b7280">Fotos recibidas</td><td align="right"><b>{photo_count}</b></td></tr></table>
<div style="height:1px;background:#e5e7eb;margin:20px 0"></div><div style="font-size:14px;color:#6b7280;margin-bottom:7px">Falla reportada</div><div style="font-size:16px;line-height:1.5;font-weight:600">{problem}</div>
</td></tr></table></td></tr></table></body></html>'''


ticketing._ticket_message = _ticket_message
case_event_notifications._plain_body = _case_plain
case_event_notifications._html_body = _case_html
