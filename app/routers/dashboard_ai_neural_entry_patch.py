from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_neural_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-ai-neural-entry'])
UI_VERSION = '2026.09.04-69'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-68', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-68', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    return base_js()


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_ai_neural_entry():
    return _html()


@router.get('/dashboard.js')
def dashboard_ai_neural_entry_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
