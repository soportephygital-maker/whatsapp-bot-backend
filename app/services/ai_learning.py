import io
import json
import math
import re
from collections import Counter
from typing import Any

import requests
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AIAdminMessage, AILearningPoint, Company, CompanyFile, Conversation, Message, SupportTicket


_STOPWORDS = {
    'a','al','algo','como','con','de','del','el','ella','en','es','esta','este','esto','hay','la','las','lo','los',
    'me','mi','no','nos','para','pero','por','que','se','si','sin','su','sus','te','tu','un','una','y','ya','yo',
    'hola','gracias','favor','puedes','puede','necesito','ayuda','ayudar','quiero','tengo',
}


def _tokens(value: str) -> list[str]:
    text = str(value or '').lower()
    text = re.sub(r'[^a-záéíóúüñ0-9]+', ' ', text)
    return [x for x in text.split() if len(x) >= 3 and x not in _STOPWORDS]


def _topic_label(text: str, limit: int = 5) -> str:
    counts = Counter(_tokens(text))
    words = [word for word, _ in counts.most_common(limit)]
    return ', '.join(words) if words else 'tema general'


def _provider() -> str:
    requested = (settings.ai_provider or 'auto').lower()
    if requested == 'openai':
        return 'openai' if settings.openai_api_key else 'retrieval'
    if requested == 'ollama':
        return 'ollama' if settings.ai_local_base_url else 'retrieval'
    if requested == 'retrieval':
        return 'retrieval'
    if settings.openai_api_key:
        return 'openai'
    if settings.ai_local_base_url:
        return 'ollama'
    return 'retrieval'


def learning_status(db: Session) -> dict[str, Any]:
    rows = db.query(AILearningPoint).all()
    approved = sum(1 for row in rows if row.status == 'approved')
    pending = sum(1 for row in rows if row.status == 'pending')
    rejected = sum(1 for row in rows if row.status == 'rejected')
    companies = len({row.company_id for row in rows if row.company_id})
    score = min(100, approved * 4 + min(20, companies * 5))
    level = 'Inicial' if score < 20 else 'Aprendiendo' if score < 50 else 'Operativo' if score < 80 else 'Avanzado'
    provider = _provider()
    return {
        'enabled': settings.ai_learning_enabled,
        'configured': provider in {'openai', 'ollama'},
        'provider': provider,
        'model': settings.openai_model if provider == 'openai' else settings.ai_local_model if provider == 'ollama' else 'memoria local',
        'score': score,
        'level': level,
        'approved_points': approved,
        'pending_points': pending,
        'rejected_points': rejected,
        'companies_with_learning': companies,
    }


def approved_context(db: Session, company_id: int | None = None, limit: int = 30) -> str:
    query = db.query(AILearningPoint).filter(AILearningPoint.status == 'approved')
    if company_id is not None:
        query = query.filter((AILearningPoint.company_id == company_id) | (AILearningPoint.company_id.is_(None)))
    rows = query.order_by(AILearningPoint.updated_at.desc()).limit(limit).all()
    chunks = []
    for row in rows:
        chunks.append(f'Problema: {row.problem}\nSolución aprobada: {row.solution}\nConfianza: {row.confidence}%')
    return '\n\n'.join(chunks)


def _extract_company_file_text(row: CompanyFile, max_chars: int = 16000) -> str:
    data = bytes(row.data or b'')
    if not data:
        return ''
    name = (row.filename or '').lower()
    ctype = (row.content_type or '').lower()
    try:
        if ctype.startswith('text/') or name.endswith(('.txt', '.md', '.csv', '.json', '.log')):
            return data.decode('utf-8', errors='ignore')[:max_chars]
        if name.endswith('.pdf') or ctype == 'application/pdf':
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
            return text[:max_chars]
        if name.endswith('.docx') or 'wordprocessingml' in ctype:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())[:max_chars]
    except Exception:
        return ''
    return ''


def manual_context(db: Session, company_id: int | None, query: str, limit: int = 5) -> str:
    if company_id is None:
        return ''
    q_tokens = set(_tokens(query))
    rows = db.query(CompanyFile).filter(CompanyFile.company_id == company_id).order_by(CompanyFile.id.desc()).limit(30).all()
    scored: list[tuple[float, str, str]] = []
    for row in rows:
        text = _extract_company_file_text(row)
        if not text:
            continue
        words = set(_tokens(text))
        overlap = len(q_tokens & words)
        score = overlap / max(1, math.sqrt(len(q_tokens) * max(1, len(words)))) if q_tokens else 0.0
        if overlap or not q_tokens:
            scored.append((score, row.filename, text))
    scored.sort(key=lambda x: x[0], reverse=True)
    return '\n\n'.join(f'Manual: {name}\n{txt}' for _, name, txt in scored[:limit])


def _learning_matches(db: Session, company_id: int | None, query: str, approved_only: bool = True, limit: int | None = None) -> list[AILearningPoint]:
    q_tokens = set(_tokens(query))
    q = db.query(AILearningPoint)
    if approved_only:
        q = q.filter(AILearningPoint.status == 'approved')
    if company_id is not None:
        q = q.filter((AILearningPoint.company_id == company_id) | (AILearningPoint.company_id.is_(None)))
    rows = q.order_by(AILearningPoint.updated_at.desc()).limit(200).all()
    scored = []
    for row in rows:
        combined = f'{row.problem} {row.solution}'
        tokens = set(_tokens(combined))
        overlap = len(q_tokens & tokens)
        if not overlap:
            continue
        precision = overlap / max(1, len(q_tokens))
        confidence = max(0, min(100, int(row.confidence or 0))) / 100
        score = precision * .75 + confidence * .25
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:(limit or settings.ai_retrieval_limit)]]


def learn_from_conversation(db: Session, ticket: SupportTicket) -> AILearningPoint | None:
    """Create or enrich a pending learning neuron from the complete solved conversation.

    This is local auto-learning: it extracts the recurring topic, customer problem,
    operator/bot guidance and final result. It never becomes customer-facing until
    the primary admin approves it.
    """
    if not ticket or ticket.status != 'closed':
        return None
    rows = db.query(Message).filter(Message.conversation_id == ticket.conversation_id).order_by(Message.id.asc()).all()
    inbound = [str(r.body or '').strip() for r in rows if r.direction == 'inbound' and str(r.body or '').strip()]
    useful_outbound = []
    for r in rows:
        if r.direction != 'outbound' or not str(r.body or '').strip():
            continue
        payload = r.raw_payload or {}
        if r.sender != 'bot' or payload.get('manual') or payload.get('manual_dashboard') or payload.get('operator'):
            useful_outbound.append(str(r.body or '').strip())
    if not useful_outbound:
        useful_outbound = [str(r.body or '').strip() for r in rows if r.direction == 'outbound' and str(r.body or '').strip()][-6:]

    problem_text = ' | '.join(inbound[-8:]) or ticket.description or ''
    solution_parts = useful_outbound[-8:]
    if ticket.close_result:
        solution_parts.append(f'Resultado final: {ticket.close_result}')
    solution_text = ' | '.join(x for x in solution_parts if x).strip()
    topic = _topic_label(f'{ticket.description or ""} {problem_text}')
    problem = f'Tema: {topic}. Problema observado: {ticket.description or problem_text}'.strip()
    solution = solution_text or 'Caso cerrado sin una solución textual suficiente; requiere revisión del administrador.'

    existing = db.query(AILearningPoint).filter(AILearningPoint.ticket_id == ticket.id).first()
    confidence = 68 if useful_outbound and ticket.close_result else 55 if useful_outbound else 35
    if existing:
        if existing.status == 'pending':
            existing.problem = problem[:4000]
            existing.solution = solution[:4000]
            existing.confidence = max(int(existing.confidence or 0), confidence)
        return existing
    row = AILearningPoint(
        company_id=ticket.company_id,
        ticket_id=ticket.id,
        problem=problem[:4000],
        solution=solution[:4000],
        confidence=confidence,
        status='pending',
    )
    db.add(row)
    return row


def _responses_text(payload: dict) -> str:
    if isinstance(payload.get('output_text'), str):
        return payload['output_text'].strip()
    texts: list[str] = []
    for item in payload.get('output') or []:
        for content in item.get('content') or []:
            text = content.get('text')
            if text:
                texts.append(str(text))
    return '\n'.join(texts).strip()


def _generate(provider: str, *, instructions: str, prompt: str) -> str:
    if provider == 'openai':
        response = requests.post(
            'https://api.openai.com/v1/responses',
            headers={'Authorization': f'Bearer {settings.openai_api_key}', 'Content-Type': 'application/json'},
            json={'model': settings.openai_model, 'instructions': instructions, 'input': prompt},
            timeout=45,
        )
        response.raise_for_status()
        return _responses_text(response.json())
    if provider == 'ollama':
        response = requests.post(
            f'{settings.ai_local_base_url}/api/generate',
            json={
                'model': settings.ai_local_model,
                'system': instructions,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.15},
            },
            timeout=settings.ai_local_timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json().get('response') or '').strip()
    return ''


def _retrieval_answer(db: Session, company_id: int | None, message: str) -> str:
    matches = _learning_matches(db, company_id, message, approved_only=True, limit=5)
    manuals = manual_context(db, company_id, message, limit=2)
    if not matches and not manuals:
        return (
            'Todavía no tengo conocimiento aprobado suficiente sobre ese tema. '
            'Puedes explicarme cuál debería ser el procedimiento correcto y lo guardaré como un nuevo punto pendiente para revisión.'
        )
    parts = []
    if matches:
        parts.append('Conocimiento aprobado relacionado:\n' + '\n\n'.join(
            f'- {r.problem}\n  Respuesta aprobada: {r.solution}' for r in matches
        ))
    if manuals:
        parts.append('También encontré contenido relacionado en manuales de la empresa. Puedo usarlo como referencia para proponer un nuevo aprendizaje, pero no lo daré por aprobado automáticamente.')
    return '\n\n'.join(parts)


def admin_chat(db: Session, *, username: str, message: str, company_id: int | None = None) -> dict[str, Any]:
    db.add(AIAdminMessage(username=username, role='admin', body=message))
    provider = _provider()
    context = approved_context(db, company_id=company_id)
    manuals = manual_context(db, company_id, message, limit=3)
    company = db.get(Company, company_id) if company_id else None
    if provider == 'retrieval':
        reply = _retrieval_answer(db, company_id, message)
        db.add(AIAdminMessage(username=username, role='assistant', body=reply))
        return {'reply': reply, 'configured': True, 'provider': 'retrieval'}

    instructions = (
        'Eres el asistente interno de aprendizaje de Phygital Bot. Solo ayudas al administrador. '
        'No inventes procedimientos. Usa conocimiento aprobado, manuales recuperados y la instrucción del administrador. '
        'Los manuales son referencia; si contradicen un punto aprobado, señala la contradicción y pide decisión. '
        'Si falta información, pregunta al administrador. Propón aprendizajes concretos, breves y verificables.'
    )
    prompt = (
        f'Empresa: {company.name if company else "general"}\n\n'
        f'Puntos aprobados:\n{context or "Ninguno todavía"}\n\n'
        f'Manuales recuperados:\n{manuals or "Ninguno relacionado"}\n\nAdministrador: {message}'
    )
    reply = _generate(provider, instructions=instructions, prompt=prompt) or _retrieval_answer(db, company_id, message)
    db.add(AIAdminMessage(username=username, role='assistant', body=reply))
    return {'reply': reply, 'configured': True, 'provider': provider}


def customer_suggestion(db: Session, *, company_id: int, question: str) -> str:
    """Customer fallback from approved knowledge only. Pending auto-learning is never exposed."""
    if not settings.ai_learning_enabled:
        return ''
    matches = _learning_matches(db, company_id, question, approved_only=True, limit=6)
    if not matches:
        return ''
    provider = _provider()
    if provider == 'retrieval':
        best = matches[0]
        q_tokens = set(_tokens(question))
        overlap = len(q_tokens & set(_tokens(best.problem))) / max(1, len(q_tokens))
        if overlap < .35 or int(best.confidence or 0) < 60:
            return ''
        return str(best.solution or '').strip()

    context = '\n\n'.join(f'Problema: {r.problem}\nSolución aprobada: {r.solution}' for r in matches)
    text = _generate(
        provider,
        instructions='Responde como soporte Phygital. Usa solo el conocimiento aprobado proporcionado. Si no hay coincidencia clara, responde exactamente NO_SEGURO. Sé breve y concreto.',
        prompt=f'Conocimiento aprobado:\n{context}\n\nConsulta del cliente:\n{question}',
    ).strip()
    return '' if not text or text == 'NO_SEGURO' else text
