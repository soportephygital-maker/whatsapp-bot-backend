from html import escape

from ..services import ticketing

_original_ticket_message = ticketing._ticket_message


def _problem(ticket) -> str:
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
    problem = _problem(ticket)
    status = 'CERRADO' if event == 'closed' else 'ABIERTO'
    subject = (
        f'[{code}] Caso cerrado - {company.name} / {store_name}'
        if event == 'closed'
        else f'[{code}] Nueva incidencia - {company.name} / {store_name}'
    )
    body = (
        f'Ticket: {code}\n'
        f'Estado: {status}\n'
        f'Empresa: {company.name}\n'
        f'Tienda: {store_name}\n'
        f'Contacto: {conversation.wa_user_id}\n'
        f'Falla reportada: {problem}\n'
    )
    if event == 'closed':
        body += f'Resultado del cierre: {ticket.close_result or "cerrado"}\nCerrado por: {ticket.closed_by or "sistema"}\n'
    html = f'''<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;background:#f6f7f9;padding:24px;color:#202124;">
    <div style="max-width:620px;margin:auto;background:white;border:1px solid #e5e7eb;border-radius:14px;padding:26px;">
      <div style="font-size:13px;color:#6b7280;">Ticket de soporte</div>
      <h2 style="margin:5px 0 18px;">{escape(code)}</h2>
      <p><b>Empresa:</b> {escape(company.name or '')}</p>
      <p><b>Tienda:</b> {escape(store_name)}</p>
      <p><b>Contacto:</b> {escape(conversation.wa_user_id or '')}</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
      <div style="font-size:13px;color:#6b7280;margin-bottom:6px;">Falla reportada</div>
      <div style="font-size:17px;line-height:1.5;font-weight:600;">{escape(problem)}</div>
      {f'<p style="margin-top:18px;"><b>Resultado:</b> {escape(ticket.close_result or "cerrado")}</p>' if event == 'closed' else ''}
    </div></body></html>'''
    return subject, body, html


ticketing._ticket_message = _ticket_message
