import time
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/api/mobile', tags=['mobile-update'])

REPO = 'soportephygital-maker/whatsapp-bot-backend'
RELEASE_TAG = 'android-latest'
ASSET_NAME = 'phygital-bot-latest.apk'
CACHE_SECONDS = 300
_cache: dict = {'expires_at': 0.0, 'payload': None}


def _parse_release_body(body: str) -> tuple[int, str, str]:
    version_code = 0
    version_name = ''
    message = 'Hay una actualización disponible para Phygital Bot.'
    for raw_line in (body or '').splitlines():
        line = raw_line.strip()
        if line.startswith('version_code='):
            try:
                version_code = int(line.split('=', 1)[1].strip())
            except ValueError:
                version_code = 0
        elif line.startswith('version_name='):
            version_name = line.split('=', 1)[1].strip()
        elif line.startswith('message='):
            value = line.split('=', 1)[1].strip()
            if value:
                message = value
    return version_code, version_name, message


def _fetch_release() -> dict:
    now = time.time()
    if _cache['payload'] is not None and now < _cache['expires_at']:
        return _cache['payload']

    url = f'https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}'
    response = requests.get(
        url,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Phygital-Bot-Update-Service'},
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
        _cache.update({'payload': payload, 'expires_at': now + 60})
        return payload
    response.raise_for_status()
    release = response.json()
    version_code, version_name, message = _parse_release_body(release.get('body') or '')
    asset_url = None
    for asset in release.get('assets') or []:
        if asset.get('name') == ASSET_NAME:
            asset_url = asset.get('browser_download_url')
            break

    payload = {
        'published': bool(asset_url and version_code > 0),
        'version_code': version_code,
        'version_name': version_name,
        'apk_url': asset_url,
        'message': message,
        'published_at': release.get('published_at'),
        'release_name': release.get('name'),
    }
    _cache.update({'payload': payload, 'expires_at': now + CACHE_SECONDS})
    return payload


@router.get('/update')
def mobile_update():
    try:
        return _fetch_release()
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f'No se pudo consultar la actualización móvil: {exc}') from exc
