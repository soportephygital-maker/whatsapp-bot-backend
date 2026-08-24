from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .manager_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-tree-multiline'])
UI_VERSION = '2026.08.21-24'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.21-16', '2026.08.21-17', '2026.08.21-18', '2026.08.21-19', '2026.08.21-20', '2026.08.21-21', '2026.08.21-22', '2026.08.21-23'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '<style>.optResponse{min-height:110px;resize:vertical;white-space:pre-wrap;line-height:1.45}.nodeMessage{min-height:110px;resize:vertical;white-space:pre-wrap;line-height:1.45}</style></head>',
    )
    return html


def _js() -> str:
    js = base_js()
    js = js.replace(
        '<input class="optResponse" value="${esc(o.respuesta)}" placeholder="Respuesta">',
        '<textarea class="optResponse" rows="5" placeholder="Respuesta. Puedes usar Enter para separar párrafos.">${esc(o.respuesta)}</textarea>',
    )
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_tree_multiline():
    return _html()


@router.get('/dashboard.js')
def dashboard_tree_multiline_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
