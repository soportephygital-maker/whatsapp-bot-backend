from io import BytesIO
from html import escape
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from sqlalchemy.orm import Session

from ..models import AuditLog, CaseAttachment, Company, Conversation, Message, Store, SupportTicket

ACCENT = colors.HexColor('#23A7D8')
GRID = colors.HexColor('#D7DCE1')
HEADER_BG = colors.HexColor('#F2F4F6')
LABEL = colors.HexColor('#68717A')
TEXT = colors.HexColor('#2B3035')
BOT_DOT = colors.HexColor('#30363D')
CLIENT_DOT = ACCENT
OPERATOR_DOT = colors.HexColor('#7B858F')


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=TEXT))
    styles.add(ParagraphStyle(name='ReportSmall', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.2, leading=9.2, textColor=LABEL))
    styles.add(ParagraphStyle(name='ReportTiny', parent=styles['BodyText'], fontName='Helvetica', fontSize=6.6, leading=8.2, textColor=LABEL))
    styles.add(ParagraphStyle(name='ReportSection', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=ACCENT, spaceBefore=5, spaceAfter=5))
    styles.add(ParagraphStyle(name='ReportTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=17, leading=19, textColor=TEXT, alignment=TA_RIGHT, spaceAfter=0))
    styles.add(ParagraphStyle(name='ReportSubtitle', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=9.5, leading=11, textColor=ACCENT, alignment=TA_RIGHT, spaceAfter=0))
    styles.add(ParagraphStyle(name='ReportBrand', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, leading=22, textColor=colors.HexColor('#B8DDE8'), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='ReportBrandSmall', parent=styles['BodyText'], fontName='Helvetica', fontSize=6.5, leading=7, textColor=colors.HexColor('#B8BFC5'), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='CellLabel', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=6.8, leading=8.5, textColor=LABEL))
    styles.add(ParagraphStyle(name='CellValue', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.7, leading=9.4, textColor=TEXT))
    styles.add(ParagraphStyle(name='CellHeader', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=6.7, leading=8.2, textColor=LABEL))
    return styles


def _p(value, style):
    text = str(value or '').strip()
    return Paragraph(escape(text).replace('\n', '<br/>') if text else '&nbsp;', style)


def _messages(db: Session, conversation_id: int) -> list[Message]:
    return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc(), Message.id.asc()).all()


def _operator_names(db: Session, conversation_id: int) -> list[str]:
    names: list[str] = []
    for row in _messages(db, conversation_id):
        if row.direction != 'outbound':
            continue
        payload = row.raw_payload or {}
        name = str(payload.get('operator') or '').strip()
        if not name and row.sender and row.sender != 'bot':
            name = str(row.sender).strip()
        if name and name not in names:
            names.append(name)
    return names


def _human_messages(db: Session, conversation_id: int) -> list[Message]:
    result = []
    for row in _messages(db, conversation_id):
        if row.direction != 'outbound':
            continue
        payload = row.raw_payload or {}
        if payload.get('operator') or payload.get('manual') or payload.get('manual_dashboard') or (row.sender and row.sender != 'bot'):
            result.append(row)
    return result


def _latest_followup(db: Session, ticket_id: int) -> tuple[str, str]:
    row = db.query(AuditLog).filter(AuditLog.entity == 'support_ticket', AuditLog.entity_id == str(ticket_id), AuditLog.action == 'ticket_followup').order_by(AuditLog.id.desc()).first()
    details = row.details if row and isinstance(row.details, dict) else {}
    return str(details.get('status_label') or ''), str(details.get('message') or '')


def _latest_bot_action(db: Session, conversation_id: int) -> str:
    row = db.query(Message).filter(Message.conversation_id == conversation_id, Message.direction == 'outbound', Message.sender == 'bot').order_by(Message.id.desc()).first()
    return str(row.body or '').strip() if row else ''


def _attachments(db: Session, ticket_id: int) -> list[CaseAttachment]:
    return db.query(CaseAttachment).filter(CaseAttachment.ticket_id == ticket_id).order_by(CaseAttachment.created_at.asc(), CaseAttachment.id.asc()).all()


def _fmt_date(value, include_time: bool = False) -> str:
    if not value:
        return ''
    try:
        return value.strftime('%d/%m/%Y %H:%M' if include_time else '%d/%m/%Y')
    except Exception:
        return str(value)


def _status_text(ticket: SupportTicket) -> str:
    return 'CERRADO' if str(ticket.status or '').lower() == 'closed' else 'ABIERTO'


def _company_label(company: Company | None) -> str:
    return company.name if company else 'Sin empresa'


def _store_label(store: Store | None) -> str:
    return store.name if store else 'Tienda sin identificar'


def _contact_label(conversation: Conversation | None) -> str:
    return conversation.wa_user_id if conversation else ''


def _customer_name(db: Session, conversation: Conversation | None) -> str:
    if not conversation:
        return 'No identificado'
    rows = db.query(Message).filter(Message.conversation_id == conversation.id, Message.direction == 'inbound').order_by(Message.id.desc()).limit(80).all()
    for row in rows:
        payload = row.raw_payload or {}
        for key in ('customer_name', 'sender_display', 'contact_name', 'display_name'):
            value = str(payload.get(key) or '').strip()
            if value and value.lower() not in {'contacto', 'whatsapp'}:
                return value
    raw = str(conversation.wa_user_id or '').strip()
    if raw.startswith('local:') and ':' in raw:
        label = raw.rsplit(':', 1)[-1].strip()
        if label:
            return label
    return raw or 'No identificado'


def _customer_role(db: Session, conversation: Conversation | None) -> str:
    if not conversation:
        return 'No registrado'
    rows = _messages(db, conversation.id)
    for row in reversed(rows):
        payload = row.raw_payload or {}
        for key in ('customer_role', 'customer_position', 'job_title', 'position', 'puesto', 'cargo'):
            value = str(payload.get(key) or '').strip()
            if value:
                return value
    for index, row in enumerate(rows[:-1]):
        if row.direction != 'outbound':
            continue
        prompt = str(row.body or '').lower()
        if not any(token in prompt for token in ('puesto', 'cargo', 'posición', 'posicion', 'rol dentro', 'qué puesto', 'que puesto')):
            continue
        for candidate in rows[index + 1:index + 5]:
            if candidate.direction == 'inbound':
                value = ' '.join(str(candidate.body or '').split()).strip()
                if value and not value.isdigit() and len(value) <= 100:
                    return value
    return 'No registrado'


def _problem_summary(ticket: SupportTicket, company: Company | None, store: Store | None) -> str:
    subject = ' '.join(str(ticket.subject or '').split()).strip()
    raw = str(ticket.description or '').replace('\r', '\n')
    company_name = str(company.name if company else '').strip().lower()
    store_name = str(store.name if store else '').strip().lower()
    candidates = []
    for part in re.split(r'[\n]+', raw):
        value = ' '.join(part.split()).strip(' -•')
        low = value.lower()
        if not value or value.isdigit():
            continue
        if low in {company_name, store_name}:
            continue
        if company_name and company_name in low and len(value) <= len(company_name) + 15:
            continue
        if store_name and store_name in low and len(value) <= len(store_name) + 15:
            continue
        if re.fullmatch(r'\d+[\s\-\.]*', value):
            continue
        if any(low.startswith(prefix) for prefix in ('ticket:', 'estado:', 'motivo:', 'nuestro equipo', 'regresar al menú', 'hablar con soporte', 'finalizar conversación')):
            continue
        candidates.append(value)
    generic_subjects = {'incidencia', 'incidencia de soporte', 'soporte', 'reporte'}
    pieces = []
    if subject and subject.lower() not in generic_subjects:
        pieces.append(subject.rstrip('.'))
    for value in candidates:
        if value.lower() not in {p.lower() for p in pieces}:
            pieces.append(value.rstrip('.'))
        if len(' '.join(pieces)) > 260 or len(pieces) >= 3:
            break
    summary = '. '.join(pieces).strip()
    if not summary:
        summary = subject or 'Falla reportada sin detalle suficiente.'
    if len(summary) > 360:
        summary = summary[:357].rstrip() + '...'
    return summary + ('' if summary.endswith(('.', '!', '?')) else '.')


def _brand_header(title: str, subtitle: str, company: Company | None, styles) -> Table:
    brand = [_p('PHYGITAL', styles['ReportBrand']), _p('RETAIL MARKETING EXPERIENCE', styles['ReportBrandSmall'])]
    right = [_p(title, styles['ReportTitle']), _p(subtitle, styles['ReportSubtitle']), _p(f'{_company_label(company).upper()} · PHYGITAL', ParagraphStyle(name=f'HeaderCompany{title}', parent=styles['ReportTiny'], alignment=TA_RIGHT))]
    table = Table([[brand, right]], colWidths=[73 * mm, 104 * mm])
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    return table


def _section(title: str, styles) -> Paragraph:
    return _p(title, styles['ReportSection'])


def _identification_table(ticket: SupportTicket, company: Company | None, store: Store | None, conversation: Conversation | None, code: str, db: Session, styles) -> Table:
    operators = ', '.join(_operator_names(db, ticket.conversation_id)) or 'No registrado'
    status_label, _ = _latest_followup(db, ticket.id)
    rows = [
        [_p('TICKET', styles['CellLabel']), _p(code, styles['CellValue']), _p('FECHA', styles['CellLabel']), _p(_fmt_date(ticket.opened_at or getattr(ticket, 'created_at', None)), styles['CellValue'])],
        [_p('EMPRESA', styles['CellLabel']), _p(_company_label(company), styles['CellValue']), _p('TIENDA', styles['CellLabel']), _p(_store_label(store), styles['CellValue'])],
        [_p('CONTACTO', styles['CellLabel']), _p(_customer_name(db, conversation), styles['CellValue']), _p('ESTADO', styles['CellLabel']), _p(_status_text(ticket), styles['CellValue'])],
        [_p('OPERADOR(ES)', styles['CellLabel']), _p(operators, styles['CellValue']), _p('SEGUIMIENTO', styles['CellLabel']), _p(status_label or 'Sin cambio registrado', styles['CellValue'])],
    ]
    table = Table(rows, colWidths=[25 * mm, 64 * mm, 25 * mm, 63 * mm])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('BACKGROUND', (0, 0), (0, -1), HEADER_BG), ('BACKGROUND', (2, 0), (2, -1), HEADER_BG), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    return table


def _footer(canvas, doc):
    canvas.saveState(); canvas.setStrokeColor(GRID); canvas.setLineWidth(0.35); canvas.line(16 * mm, 13 * mm, 194 * mm, 13 * mm); canvas.setFillColor(LABEL); canvas.setFont('Helvetica', 6.5)
    canvas.drawString(16 * mm, 8.5 * mm, 'phygital.com.mx'); canvas.drawCentredString(105 * mm, 8.5 * mm, 'Democracias 116 · Azcapotzalco · CDMX'); canvas.drawRightString(194 * mm, 8.5 * mm, 'info@phygital.com.mx')
    if doc.page > 1: canvas.drawRightString(194 * mm, 14.5 * mm, f'Página {doc.page}')
    canvas.restoreState()


def _message_actor(row: Message) -> tuple[str, object]:
    payload = row.raw_payload or {}; operator = str(payload.get('operator') or '').strip()
    if row.direction == 'inbound': return 'CLIENTE', CLIENT_DOT
    if operator or (row.sender and row.sender != 'bot'): return f'OPERADOR{(": " + operator) if operator else ""}', OPERATOR_DOT
    return 'BOT', BOT_DOT


def _message_block(row: Message, styles) -> KeepTogether:
    actor, dot = _message_actor(row); when = _fmt_date(row.created_at, include_time=True)
    header = Table([[_p(f'● {actor}', styles['CellHeader']), _p(when, ParagraphStyle(name=f'MsgDate{row.id}', parent=styles['ReportTiny'], alignment=TA_RIGHT))]], colWidths=[110 * mm, 67 * mm])
    header.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HEADER_BG), ('TEXTCOLOR', (0, 0), (0, 0), dot), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    body = Table([[_p('Mensaje:', styles['CellLabel'])], [_p(row.body or '(sin texto)', styles['ReportBody'])]], colWidths=[177 * mm])
    body.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.35, GRID), ('LINEBELOW', (0, 0), (-1, 0), 0.25, GRID), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    return KeepTogether([header, body, Spacer(1, 4)])


def _image_flowable(attachment: CaseAttachment, max_w: float = 80 * mm, max_h: float = 58 * mm):
    if not str(attachment.content_type or '').lower().startswith('image/') or not attachment.data:
        return None
    try:
        image = RLImage(BytesIO(attachment.data))
        if not image.imageWidth or not image.imageHeight:
            return None
        scale = min(max_w / float(image.imageWidth), max_h / float(image.imageHeight), 1.0)
        image.drawWidth = float(image.imageWidth) * scale
        image.drawHeight = float(image.imageHeight) * scale
        return image
    except Exception:
        return None


def _photo_attachments(attachments: list[CaseAttachment]) -> list[CaseAttachment]:
    return [a for a in attachments if str(a.content_type or '').lower().startswith('image/') and a.data]


def _evidence_summary(attachments: list[CaseAttachment]) -> tuple[str, str]:
    photos = _photo_attachments(attachments)
    videos = [a for a in attachments if str(a.content_type or '').lower().startswith('video/')]
    others = [a for a in attachments if a not in photos and a not in videos]
    checks = f'Fotos: {len(photos)} · Videos: {len(videos)} · Otros archivos: {len(others)}'
    refs = ', '.join(a.filename for a in attachments[:8]) or 'Sin evidencia registrada'
    if len(attachments) > 8: refs += f' (+{len(attachments) - 8} más)'
    return checks, refs


def _photo_grid(attachments: list[CaseAttachment], styles, columns: int = 2):
    photos = _photo_attachments(attachments)
    if not photos:
        return _p('No hay fotografías almacenadas para este ticket.', styles['ReportSmall'])
    cells = []
    for photo in photos:
        image = _image_flowable(photo)
        content = []
        if image: content.append(image)
        content.append(_p(photo.filename, styles['ReportTiny']))
        cells.append(content)
    rows = [cells[i:i + columns] for i in range(0, len(cells), columns)]
    while rows and len(rows[-1]) < columns: rows[-1].append('')
    table = Table(rows, colWidths=[86 * mm] * columns)
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('BOX', (0, 0), (-1, -1), 0.25, GRID), ('INNERGRID', (0, 0), (-1, -1), 0.25, GRID), ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    return table


def _evidence_table(attachments: list[CaseAttachment], styles, include_images: bool = True) -> list:
    photos = _photo_attachments(attachments)
    if not attachments:
        table = Table([[[_p('SIGUIENTE INTERACCIÓN', styles['CellHeader']), _p('Sin evidencia adicional registrada.', styles['ReportSmall'])], [_p('ARCHIVO / EVIDENCIA ASOCIADA', styles['CellHeader']), _p('Sin archivos asociados.', styles['ReportSmall'])]]], colWidths=[88.5 * mm, 88.5 * mm])
        table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
        return [table]
    rows = []
    for attachment in attachments:
        kind = 'Foto' if str(attachment.content_type or '').lower().startswith('image/') else ('Video' if str(attachment.content_type or '').lower().startswith('video/') else 'Documento')
        rows.append([[_p('SIGUIENTE INTERACCIÓN', styles['CellHeader']), _p('Actor: Cliente', styles['ReportSmall']), _p(f'Fecha/hora: {_fmt_date(attachment.created_at, include_time=True)}', styles['ReportSmall']), _p('Mensaje: Evidencia asociada al reporte', styles['ReportSmall'])], [_p('ARCHIVO / EVIDENCIA ASOCIADA', styles['CellHeader']), _p(f'Tipo: {kind}', styles['ReportSmall']), _p(f'Referencia: {attachment.filename}', styles['ReportSmall']), _p(f'Descripción: {attachment.source or "Adjunto del caso"}', styles['ReportSmall'])]])
    table = Table(rows, colWidths=[88.5 * mm, 88.5 * mm])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    result = [table]
    if include_images and photos:
        result.extend([Spacer(1, 6), _p(f'Fotografías recibidas: {len(photos)}', styles['CellHeader']), Spacer(1, 4), _photo_grid(photos, styles)])
    return result


def build_chat_pdf(db: Session, *, ticket: SupportTicket, company: Company | None, store: Store | None, conversation: Conversation | None, code: str, include_images: bool = True) -> bytes:
    buffer = BytesIO(); styles = _styles(); doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=13 * mm, bottomMargin=17 * mm)
    messages = _messages(db, ticket.conversation_id); attachments = _attachments(db, ticket.id)
    story = [_brand_header('EXPEDIENTE COMPLETO', 'CONVERSACIÓN DEL CHATBOT', company, styles), Spacer(1, 4), _section('1. DATOS DEL EXPEDIENTE', styles), _identification_table(ticket, company, store, conversation, code, db, styles), _section('2. HISTORIAL CRONOLÓGICO DE CONVERSACIÓN', styles), _p('● CLIENTE        ● BOT        ● OPERADOR', styles['CellHeader']), Spacer(1, 4)]
    if not messages: story.append(_p('No hay mensajes registrados.', styles['ReportBody']))
    else:
        for row in messages: story.append(_message_block(row, styles))
    story.append(_section('3. CONTINUIDAD DEL EXPEDIENTE', styles)); story.extend(_evidence_table(attachments, styles, include_images=include_images)); story.extend([Spacer(1, 5), _p('Este expediente continúa en páginas adicionales cuando el historial del ticket lo requiera.', styles['ReportTiny'])])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def build_summary_pdf(db: Session, *, ticket: SupportTicket, company: Company | None, store: Store | None, conversation: Conversation | None, code: str) -> bytes:
    buffer = BytesIO(); styles = _styles(); doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=13 * mm, bottomMargin=17 * mm)
    operators = _operator_names(db, ticket.conversation_id); human_rows = _human_messages(db, ticket.conversation_id); status_label, followup = _latest_followup(db, ticket.id); attachments = _attachments(db, ticket.id); checks, refs = _evidence_summary(attachments)
    resolution = ticket.close_result or followup or 'Caso aún sin conclusión registrada.'; bot_action = _latest_bot_action(db, ticket.conversation_id) or 'Sin acción del chatbot registrada.'; request = ticket.subject or 'Incidencia de soporte'; problem = _problem_summary(ticket, company, store); reporter = _customer_name(db, conversation); reporter_role = _customer_role(db, conversation); responsible = ', '.join(operators) or 'No requerido'; attention_date = _fmt_date(human_rows[0].created_at) if human_rows else ''; close_date = _fmt_date(ticket.closed_at) if getattr(ticket, 'closed_at', None) else ''
    detail_text = f'Tienda: {_store_label(store)}\nReporta: {reporter}\nPuesto: {reporter_role}'

    route = Table([[_p('SOLICITUD', styles['CellHeader']), _p('CATEGORÍA', styles['CellHeader']), _p('DETALLE', styles['CellHeader']), _p('CAUSA / ORIGEN', styles['CellHeader'])], [_p(request, styles['CellValue']), _p(company.name if company else 'Sin empresa', styles['CellValue']), _p(detail_text, styles['CellValue']), _p('Información registrada en la conversación', styles['CellValue'])]], colWidths=[44.25 * mm] * 4)
    route.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG), ('ALIGN', (0, 0), (-1, 0), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))

    incidence = Table([[_p('PROBLEMA REPORTADO', styles['CellHeader']), _p('EVIDENCIA RECIBIDA', styles['CellHeader'])], [_p(problem, styles['ReportBody']), [_p(checks, styles['ReportSmall']), Spacer(1, 3), _p(f'Referencia: {refs}', styles['ReportSmall'])]]], colWidths=[88.5 * mm, 88.5 * mm])
    incidence.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))

    result = Table([[_p('DIAGNÓSTICO / ACCIÓN DEL CHATBOT', styles['CellHeader']), _p('SOLUCIÓN / RESULTADO', styles['CellHeader'])], [_p(bot_action, styles['ReportBody']), _p(resolution, styles['ReportBody'])]], colWidths=[88.5 * mm, 88.5 * mm])
    result.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))

    human_check = 'Escalado a soporte' if human_rows else 'No requerida'; close_state = _status_text(ticket)
    close = Table([[_p('ATENCIÓN HUMANA', styles['CellHeader']), _p('CIERRE DEL CASO', styles['CellHeader'])], [[_p(human_check, styles['ReportSmall']), _p(f'Responsable: {responsible}', styles['ReportSmall']), _p(f'Fecha de atención: {attention_date or "No registrada"}', styles['ReportSmall'])], [_p(f'Estado final: {close_state}', styles['ReportSmall']), _p(f'Fecha de cierre: {close_date or "Pendiente"}', styles['ReportSmall']), _p(f'Observaciones: {followup or resolution}', styles['ReportSmall'])]]], colWidths=[88.5 * mm, 88.5 * mm])
    close.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.35, GRID), ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))

    story = [_brand_header('REPORTE DE ATENCIÓN', 'RESUMEN EJECUTIVO DEL CASO', company, styles), Spacer(1, 4), _section('1. IDENTIFICACIÓN DEL CASO', styles), _identification_table(ticket, company, store, conversation, code, db, styles), _section('2. RUTA DE ATENCIÓN', styles), route, _section('3. INCIDENCIA Y EVIDENCIA', styles), incidence]
    photos = _photo_attachments(attachments)
    if photos:
        story.extend([Spacer(1, 5), _p(f'EVIDENCIA FOTOGRÁFICA · {len(photos)} foto(s)', styles['CellHeader']), Spacer(1, 4), _photo_grid(photos, styles)])
    story.extend([_section('4. DIAGNÓSTICO Y RESULTADO', styles), result, _section('5. ATENCIÓN Y CIERRE', styles), close, Spacer(1, 5), _p('ANEXO DISPONIBLE: Expediente completo de conversación asociado al mismo ticket.', styles['ReportSmall'])])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
