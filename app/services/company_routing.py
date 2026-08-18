import re
import unicodedata
from sqlalchemy.orm import Session
from ..models import Company


def normalize(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _items(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def identification_profile(company: Company) -> dict:
    tree = company.decision_tree or {}
    profile = tree.get('identificacion') or {}
    return {
        'aliases': _items(profile.get('aliases')),
        'keywords': _items(profile.get('keywords')),
        'tags': _items(profile.get('tags')),
    }


def routing_terms(company: Company) -> list[tuple[str, int, str]]:
    profile = identification_profile(company)
    terms: list[tuple[str, int, str]] = []
    # Explicit aliases are strongest, followed by tags and supporting keywords.
    for value in profile['aliases']:
        terms.append((value, 5, 'alias'))
    for value in profile['tags']:
        terms.append((value, 3, 'tag'))
    for value in profile['keywords']:
        terms.append((value, 2, 'keyword'))
    # Company name/key are useful safe fallbacks when no explicit alias was added.
    terms.append((company.name, 4, 'company_name'))
    terms.append((company.company_key, 4, 'company_key'))
    return terms


def score_company(company: Company, text: str) -> tuple[int, list[str]]:
    normalized_text = f' {normalize(text)} '
    if not normalized_text.strip():
        return 0, []
    score = 0
    matches: list[str] = []
    used: set[str] = set()
    for raw_term, weight, kind in routing_terms(company):
        term = normalize(raw_term)
        if not term or term in used:
            continue
        used.add(term)
        if f' {term} ' in normalized_text:
            score += weight
            matches.append(f'{kind}:{raw_term}')
    return score, matches


def detect_company(db: Session, text: str, fallback: Company | None = None) -> tuple[Company | None, dict]:
    companies = db.query(Company).filter(Company.is_active.is_(True)).all()
    scored = []
    for company in companies:
        score, matches = score_company(company, text)
        if score > 0:
            scored.append((score, company, matches))
    scored.sort(key=lambda row: (-row[0], row[1].id))

    if not scored:
        return fallback, {'matched': False, 'reason': 'no_keywords', 'fallback_company_id': fallback.id if fallback else None}

    best_score, best_company, best_matches = scored[0]
    ties = [row for row in scored if row[0] == best_score]
    if len(ties) > 1:
        if fallback and any(row[1].id == fallback.id for row in ties):
            fallback_row = next(row for row in ties if row[1].id == fallback.id)
            return fallback, {
                'matched': True,
                'ambiguous': True,
                'score': best_score,
                'matches': fallback_row[2],
                'reason': 'tie_kept_fallback',
            }
        return fallback, {
            'matched': False,
            'ambiguous': True,
            'score': best_score,
            'reason': 'tie_no_override',
            'candidates': [row[1].company_key for row in ties],
        }

    return best_company, {
        'matched': True,
        'ambiguous': False,
        'score': best_score,
        'matches': best_matches,
        'company_key': best_company.company_key,
        'fallback_company_id': fallback.id if fallback else None,
    }


def base_decision_tree() -> dict:
    return {
        'identificacion': {'aliases': [], 'keywords': [], 'tags': []},
        'nodo_raiz': 'inicio',
        'nodos': {
            'inicio': {
                'mensaje': 'Hola. ¿En qué podemos ayudarte? Elige una opción.',
                'opciones': [
                    {'comando': '1', 'respuesta': 'Cuéntame qué problema presentas.', 'siguiente': 'soporte'},
                    {'comando': '2', 'respuesta': 'Escribe qué información necesitas.', 'siguiente': 'informacion'},
                    {'comando': '3', 'respuesta': 'Entendido. Voy a solicitar apoyo de una persona.', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'soporte': {
                'mensaje': 'Describe brevemente el problema. Si necesitas una persona escribe: humano.',
                'opciones': [
                    {'comando': 'humano', 'respuesta': 'Entendido. Voy a solicitar apoyo de una persona.', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'informacion': {
                'mensaje': 'Escribe tu consulta. Si necesitas una persona escribe: humano.',
                'opciones': [
                    {'comando': 'humano', 'respuesta': 'Entendido. Voy a solicitar apoyo de una persona.', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'humano': {
                'mensaje': 'Tu solicitud de atención humana fue registrada.',
                'opciones': [],
            },
        },
    }
