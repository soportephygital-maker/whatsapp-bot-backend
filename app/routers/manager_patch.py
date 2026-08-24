from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-gerente'])
UI_VERSION = '2026.08.21-17'


def _html() -> str:
    html = base_html().replace('UI 2026.08.21-16', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.08.21-16', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = base_js()
    js = js.replace(
        "const TK='phygital_token',RK='phygital_role',$=id=>document.getElementById(id),role=()=>localStorage.getItem(RK)||'',admin=()=>role()==='admin',operate=()=>['admin','operador'].includes(role());",
        "const TK='phygital_token',RK='phygital_role',$=id=>document.getElementById(id),role=()=>localStorage.getItem(RK)||'',rootAdmin=()=>role()==='admin',admin=()=>['admin','gerente'].includes(role()),operate=()=>['admin','gerente','operador'].includes(role());",
    )
    js = js.replace(
        "$('navUsers').classList.toggle('h',!admin());$('navActivity').classList.toggle('h',!admin());$('navContacts').classList.toggle('h',!admin());$('navAppearance').classList.toggle('h',!admin());applyTheme();",
        "$('navUsers').classList.toggle('h',!rootAdmin());$('navActivity').classList.toggle('h',!admin());$('navContacts').classList.toggle('h',!admin());$('navAppearance').classList.toggle('h',!admin());applyTheme();",
    )
    js = js.replace(
        '<option value="operador">Operador</option><option value="lector">Lector</option>',
        '<option value="gerente">Gerente</option><option value="operador">Operador</option><option value="lector">Lector</option>',
    )
    js = js.replace(
        '<option value="operador" ${u.role===\'operador\'?\'selected\':\'\'}>Operador</option><option value="lector" ${u.role===\'lector\'?\'selected\':\'\'}>Lector</option>',
        '<option value="gerente" ${u.role===\'gerente\'?\'selected\':\'\'}>Gerente</option><option value="operador" ${u.role===\'operador\'?\'selected\':\'\'}>Operador</option><option value="lector" ${u.role===\'lector\'?\'selected\':\'\'}>Lector</option>',
    )
    js = js.replace(
        "function appearance(){if(!admin())return;",
        "function appearance(){if(!admin())return;",
    )
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_gerente():
    return _html()


@router.get('/dashboard.js')
def dashboard_js_gerente():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
