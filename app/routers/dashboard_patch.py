from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .dashboard_ui import HTML, JS

router = APIRouter(tags=['dashboard-ui-v2'])
UI_VERSION = '2026.08.17-7'


def _html() -> str:
    html = HTML.replace('__UI_VERSION__', UI_VERSION)
    html = html.replace('<button id="navContacts">Contactos</button>', '<button id="navContacts" class="h">Personal de soporte</button>')
    html = html.replace('/dashboard.js?v=__UI_VERSION__', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = JS
    js = js.replace(
        "$('navUsers').classList.toggle('h',!admin());$('navActivity').classList.toggle('h',!admin());",
        "$('navUsers').classList.toggle('h',!admin());$('navActivity').classList.toggle('h',!admin());$('navContacts').classList.toggle('h',!admin());",
    )
    js = js.replace(
        "<b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)}<div>${esc(r.body)}</div>",
        "<b>${esc(r.company_name)}</b> · <span class=\"badge\">${esc(r.store_name||'Tienda sin identificar')}</span> · ${esc(r.wa_user_id)}<div>${esc(r.body)}</div>",
    )
    js = js.replace(
        "<button class=\"help-review\">En revisión</button><button class=\"help-resolve\">Resolver</button>",
        "<button class=\"help-review\">En revisión</button><button class=\"help-resolve\">Cerrar atendido</button><button class=\"help-ignore danger\">Cerrar sin éxito</button>",
    )
    js = js.replace(
        "document.querySelectorAll('.help-review,.help-resolve').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-help]'),status=b.classList.contains('help-resolve')?'resolved':'reviewing';",
        "document.querySelectorAll('.help-review,.help-resolve,.help-ignore').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-help]'),status=b.classList.contains('help-resolve')?'resolved':(b.classList.contains('help-ignore')?'ignored':'reviewing');",
    )
    js = js.replace(
        "[support,files,tree]=await Promise.all([api('/api/empresas/'+encodeURIComponent(key)+'/soporte'),api('/api/empresas/'+encodeURIComponent(key)+'/archivos'),api('/api/empresas/'+encodeURIComponent(key)+'/arbol')]);",
        "[support,files,tree,authorized]=await Promise.all([api('/api/empresas/'+encodeURIComponent(key)+'/soporte'),api('/api/empresas/'+encodeURIComponent(key)+'/archivos'),api('/api/empresas/'+encodeURIComponent(key)+'/arbol'),api('/api/contacts')]);",
    )
    js = js.replace(
        "<input id=\"supportName\" placeholder=\"Nombre\"><input id=\"supportPhone\" placeholder=\"Teléfono\"><select id=\"supportRole\"><option value=\"primary\">Primario</option><option value=\"secondary\">Secundario</option></select><input id=\"supportMinutes\" type=\"number\" value=\"15\"><button id=\"addSupport\">Agregar apoyo</button>",
        "<label>Contacto autorizado</label><select id=\"supportContact\"><option value=\"\">Selecciona contacto</option>${authorized.map(a=>`<option value=\"${a.id}\">${esc(a.name||a.phone)} · ${esc(a.phone)}</option>`).join('')}</select><select id=\"supportRole\"><option value=\"primary\">Primario</option><option value=\"secondary\">Secundario</option></select><label>Minutos antes del siguiente escalón</label><input id=\"supportMinutes\" type=\"number\" min=\"1\" value=\"5\"><button id=\"addSupport\">Asignar apoyo</button>",
    )
    js = js.replace(
        "body:JSON.stringify({name:$('supportName').value,phone:$('supportPhone').value,role:$('supportRole').value,priority:1,escalation_after_minutes:Number($('supportMinutes').value||15)})",
        "body:JSON.stringify({contact_id:Number($('supportContact').value),role:$('supportRole').value,priority:1,escalation_after_minutes:Number($('supportMinutes').value||5)})",
    )
    js = js.replace(
        "$('addSupport').onclick=async()=>{try{await api('/api/empresas/'",
        "$('addSupport').onclick=async()=>{if(!$('supportContact').value)return err('Selecciona un contacto autorizado');try{await api('/api/empresas/'",
    )
    js = js.replace(
        "<h2>Contactos autorizados</h2><p class=\"muted\">Solo aparecen los contactos seleccionados desde la app Android.</p>",
        "<h2>Personal de soporte autorizado</h2><p class=\"muted\">Solo el administrador ve esta lista. Estos contactos pueden asignarse como soporte primario o secundario.</p>",
    )
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_v2():
    return _html()


@router.get('/dashboard.js')
def dashboard_js_v2():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
