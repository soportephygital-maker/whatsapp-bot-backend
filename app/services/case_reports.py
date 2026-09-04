from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from sqlalchemy.orm import Session

from ..models import AuditLog, CaseAttachment, Company, Conversation, Message, Store, SupportTicket


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CaseSmall', parent=styles['BodyText'], fontSize=8.5, leading=11))
    styles.add(ParagraphStyle(name='CaseBody', parent=styles['BodyText'], fontSize=10, leading=14))
    styles.add(ParagraphStyle(name='CaseHeading', parent=styles['Heading2'], fontSize=14, leading=18, spaceAfter=8))
    return styles


def _operator_names(db: Session, conversation_id: int) -> list[str]:
    names: list[str] = []
    rows = db.query(Message).filter(Message.conversation_id == conversation_id, Message.direction == 'outbound').order_by(Message.id.asc()).all()
    for row in rows:
        payload = row.raw_payload or {}
        name = str(payload.get('operator') or '').strip()
        if not name and row.sender and row.sender != 'bot':
            name = str(row.sender).strip()
        if name and name not in names:
            names.append(name)
    return names


def _latest_followup(db: Session, ticket_id: int) -> tuple[str, str]:
    row = db.query(AuditLog).filter(AuditLog.entity == 'support_ticket', AuditLog.entity_id == str(ticket_id), AuditLog.action == 'ticket_followup').order_by(AuditLog.id.desc()).first()
    details = row.details if row and isinstance(row.details, dict) else {}
    return str(details.get('status_label') or ''), str(details.get('message') or '')


def _header_table(ticket: SupportTicket, company: Company | None, store: Store | None, conversation: Conversation | None, code: str, db: Session):
    operators = ', '.join(_operator_names(db, ticket.conversation_id)) or 'Sin operador humano registrado'
    status_label, followup = _latest_followup(db, ticket.id)
    rows = [['Ticket', code], ['Empresa', company.name if company else 'Sin empresa'], ['Tienda', store.name if store else 'Tienda sin identificar'], ['Contacto', conversation.wa_user_id if conversation else ''], ['Estado', ticket.status], ['Operador(es)', operators], ['Seguimiento', status_label or 'Sin cambio de estado registrado']]
    if followup:
        rows.append(['Nota de seguimiento', followup])
    table = Table(rows, colWidths=[38 * mm, 132 * mm])
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')), ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4b5563')), ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    return table


def _image_flowable(attachment: CaseAttachment):
    if not str(attachment.content_type or '').lower().startswith('image/'):
        return None
    try:
        image = RLImage(BytesIO(attachment.data))
        max_w, max_h = 155 * mm, 95 * mm
        scale = min(max_w / float(image.imageWidth), max_h / float(image.imageHeight), 1.0)
        image.drawWidth = float(image.imageWidth) * scale
        image.drawHeight = float(image.imageHeight) * scale
        return image
    except Exception:
        return None


def build_chat_pdf(db: Session, *, ticket: SupportTicket, company: Company | None, store: Store | None, conversation: Conversation | None, code: str) -> bytes:
    buffer = BytesIO(); styles = _styles()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = [Paragraph('Expediente completo de conversación', styles['Title']), Spacer(1, 6), _header_table(ticket, company, store, conversation, code, db), Spacer(1, 12)]
    messages = db.query(Message).filter(Message.conversation_id == ticket.conversation_id).order_by(Message.created_at.asc(), Message.id.asc()).all()
    attachments = db.query(CaseAttachment).filter(CaseAttachment.ticket_id == ticket.id).order_by(CaseAttachment.created_at.asc(), CaseAttachment.id.asc()).all()
    by_message: dict[int, list[CaseAttachment]] = {}
    unlinked: list[CaseAttachment] = []
    for attachment in attachments:
        if attachment.message_id:
            by_message.setdefault(attachment.message_id, []).append(attachment)
        else:
            unlinked.append(attachment)
    if not messages:
        story.append(Paragraph('No hay mensajes registrados.', styles['CaseBody']))
    for row in messages:
        when = row.created_at.strftime('%d/%m/%Y %H:%M:%S') if row.created_at else ''
        direction = 'Cliente' if row.direction == 'inbound' else ('Bot' if row.sender == 'bot' else f'Operador: {row.sender or ""}')
        payload = row.raw_payload or {}; operator = str(payload.get('operator') or '').strip()
        if operator and row.direction == 'outbound':
            direction = f'Operador: {operator}'
        story.append(Paragraph(f'<b>{escape(direction)}</b> · {escape(when)}', styles['CaseSmall']))
        story.append(Paragraph(escape(row.body or '').replace('\n', '<br/>'), styles['CaseBody']))
        for attachment in by_message.get(row.id, []):
            story.append(Paragraph(f'<i>Adjunto: {escape(attachment.filename)}</i>', styles['CaseSmall']))
            image = _image_flowable(attachment)
            if image:
                story.extend([Spacer(1, 4), image])
        story.append(Spacer(1, 8))
    if unlinked:
        story.extend([PageBreak(), Paragraph('Archivos adjuntos del caso', styles['CaseHeading'])])
        for attachment in unlinked:
            story.append(Paragraph(escape(attachment.filename), styles['CaseSmall']))
            image = _image_flowable(attachment)
            if image:
                story.extend([Spacer(1, 4), image, Spacer(1, 10)])
    doc.build(story)
    return buffer.getvalue()


def build_summary_pdf(db: Session, *, ticket: SupportTicket, company: Company | None, store: Store | None, conversation: Conversation | None, code: str) -> bytes:
    buffer = BytesIO(); styles = _styles()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    operators = ', '.join(_operator_names(db, ticket.conversation_id)) or 'No requirió operador humano registrado'
    status_label, followup = _latest_followup(db, ticket.id)
    resolution = ticket.close_result or followup or 'Caso aún sin conclusión registrada.'
    story = [Paragraph('Resumen ejecutivo del caso', styles['Title']), Spacer(1, 8), _header_table(ticket, company, store, conversation, code, db), Spacer(1, 14), Paragraph('Problema', styles['CaseHeading']), Paragraph(escape(ticket.description or 'Sin descripción').replace('\n', '<br/>'), styles['CaseBody']), Spacer(1, 10), Paragraph('Solución / resultado', styles['CaseHeading']), Paragraph(escape(resolution).replace('\n', '<br/>'), styles['CaseBody']), Spacer(1, 10), Paragraph('Atención', styles['CaseHeading']), Paragraph(f'Operador(es): {escape(operators)}', styles['CaseBody'])]
    if status_label:
        story.extend([Spacer(1, 8), Paragraph(f'Último estado: {escape(status_label)}', styles['CaseBody'])])
    doc.build(story)
    return buffer.getvalue()
