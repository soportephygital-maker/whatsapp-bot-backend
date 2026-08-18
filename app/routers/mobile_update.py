import time
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/api/mobile', tags=['mobile-update'])

METADATA_URL = 'https://raw.githubusercontent.com/soportephygital-maker/whatsapp-bot-backend/mobile-release/latest.json'
CACHE_SECONDS = 60
_cache: dict = {'expires_at': 0.0, 'payload': None}


def _fetch_metadata() -> dict:
    now = time.time()
    if _cache['payload'] is not None and now < _cache['expires_at']:
        return _cache['payload']

    response = requests.get(
        METADATA_URL,
        headers={'User-Agent': 'Phygital-Bot-Update-Service'},
        timeout=10,
    )
    if response.status_code == 404:
        payload = {
            'published': False,
            'version_code': 0,
            'version_name': '',
            'apk_url': None,
            'message': 'Todavía no hay una actualización móvil publicada.',
        }
        _cache.update({'payload': payload, 'expires_at': now + 20})
        return payload

    response.raise_for_status()
    data = response.json()
    version_code = int(data.get('version_code') or 0)
    apk_url = str(data.get('apk_url') or '').strip() or None
    payload = {
        'published': bool(version_code > 0 and apk_url),
        'version_code': version_code,
        'version_name': str(data.get('version_name') or ''),
        'apk_url': apk_url,
        'message': str(data.get('message') or 'Hay una actualización disponible para Phygital Bot.'),
        'source_sha': data.get('source_sha'),
    }
    _cache.update({'payload': payload, 'expires_at': now + CACHE_SECONDS})
    return payload


@router.get('/update')
def mobile_update():
    try:
        return _fetch_metadata()
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail=f'No se pudo consultar la actualización móvil: {exc}') from exc
