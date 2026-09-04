import json
import os
from typing import Any

import requests
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AIAdminMessage, AILearningPoint, Company


def learning_status(db: Session) -> dict[str, Any]:
    rows = db.query(AILearningPoint).all()
    approved = sum(1 for row in rows if row.status == 'approved')
    pending = sum(1 for row in rows if row.status == 'pending')
    rejected = sum(1 for row in rows if row.status == 'rejected')
    companies = len({row.company_id for row in rows if row.company_id})
    # This is a transparent operational score, not a claim that model weights changed.
    score = min(100, approved * 4 + min(20, companies * 5))
    level = 'Inicial' if score < 20 else 'Aprendiendo' if score < 50 else 'Operativo' if score < 80 else 'Avanzado'
    return {
        'enabled': settings.ai_learning_enabled,
        'configured': bool(settings.openai_api_key),
        'model': settings.openai_model,
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


def admin_chat(db: Session, *, username: str, message: str, company_id: int | None = None) -> dict[str, Any]:
    db.add(AIAdminMessage(username=username, role='admin', body=message))
    if not settings.openai_api_key:
        reply = 'La IA generativa aún no está conectada. Configura OPENAI_API_KEY en Render; mientras tanto puedo seguir almacenando y aprobando puntos de aprendizaje.'
        db.add(AIAdminMessage(username=username, role='assistant', body=reply))
        return {'reply': reply, 'configured': False}

    context = approved_context(db, company_id=company_id)
    company = db.get(Company, company_id) if company_id else None
    instructions = (
        'Eres el asistente interno de aprendizaje de Phygital Bot. Solo ayudas al administrador. '
        'No inventes procedimientos. Usa únicamente los puntos aprobados y la instrucción del administrador. '
        'Si falta información, pregunta al administrador qué respuesta o procedimiento debe aprobarse. '
        'Explica de forma concreta qué nuevo punto debería guardarse cuando corresponda.'
    )
    prompt = f'Empresa: {company.name if company else "general"}\n\nPuntos aprobados:\n{context or "Ninguno todavía"}\n\nAdministrador: {message}'
    response = requests.post(
        'https://api.openai.com/v1/responses',
        headers={'Authorization': f'Bearer {settings.openai_api_key}', 'Content-Type': 'application/json'},
        json={'model': settings.openai_model, 'instructions': instructions, 'input': prompt},
        timeout=45,
    )
    response.raise_for_status()
    reply = _responses_text(response.json()) or 'No recibí una respuesta utilizable del modelo.'
    db.add(AIAdminMessage(username=username, role='assistant', body=reply))
    return {'reply': reply, 'configured': True}


def customer_suggestion(db: Session, *, company_id: int, question: str) -> str:
    """Optional approved-knowledge fallback. Never uses pending learning points."""
    if not (settings.ai_learning_enabled and settings.openai_api_key):
        return ''
    context = approved_context(db, company_id=company_id, limit=20)
    if not context:
        return ''
    response = requests.post(
        'https://api.openai.com/v1/responses',
        headers={'Authorization': f'Bearer {settings.openai_api_key}', 'Content-Type': 'application/json'},
        json={
            'model': settings.openai_model,
            'instructions': 'Responde como soporte Phygital. Usa solo el conocimiento aprobado. Si no hay coincidencia clara, responde exactamente NO_SEGURO.',
            'input': f'Conocimiento aprobado:\n{context}\n\nConsulta del cliente:\n{question}',
        },
        timeout=30,
    )
    if not response.ok:
        return ''
    text = _responses_text(response.json()).strip()
    return '' if not text or text == 'NO_SEGURO' else text
