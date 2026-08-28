from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .operations_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-login-recovery'])
UI_VERSION = '2026.08.28-41'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-40', '2026.08.28-39', '2026.08.28-38', '2026.08.28-37', '2026.08.28-36'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    # Serve the last stable operations UI directly. This intentionally excludes
    # the experimental tree-zoom layer so a syntax error there cannot block
    # dashboard login or initialization.
    return base_js()


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_login_recovery():
    return _html()


@router.get('/dashboard.js')
def dashboard_login_recovery_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})
