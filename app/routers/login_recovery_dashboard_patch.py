from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .tree_zoom_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-login-recovery'])
UI_VERSION = '2026.08.28-40'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-39', '2026.08.28-38', '2026.08.28-37', '2026.08.28-36'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = base_js()
    # Fix the compact ternary added by the zoom layer. Without the spaces,
    # some browsers parse `0?.08` as optional chaining and reject the whole
    # dashboard script before the login button handlers are installed.
    js = js.replace(
        "TREE_ZOOM+(e.deltaY<0?.08:-.08)",
        "TREE_ZOOM+(e.deltaY<0 ? 0.08 : -0.08)",
    )
    # Defensive fallback for any equivalent minified occurrence.
    js = js.replace("e.deltaY<0?.08:-.08", "e.deltaY<0 ? 0.08 : -0.08")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_login_recovery():
    return _html()


@router.get('/dashboard.js')
def dashboard_login_recovery_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
