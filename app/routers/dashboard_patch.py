from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .dashboard_ui import HTML, JS

router = APIRouter(tags=['dashboard-ui-v2'])
UI_VERSION = '2026.08.17-10'


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
        "<button class=\"open-chat\">Abrir chat</button>",
        "<button class=\"open-chat\">Abrir chat</button>${admin()?'<button class=\"forget-chat danger\">Olvidar conversación</button>':''}",
    )
    js = js.replace(
        "document.querySelectorAll('.open-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)))",
        "document.querySelectorAll('.open-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));document.querySelectorAll('.forget-chat').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-conv]'),id=Number(row.dataset.conv);if(!confirm('¿Olvidar esta conversación de prueba? Se eliminarán sus mensajes y solicitudes asociadas.'))return;try{await api('/api/conversaciones/'+id+'/olvidar',{method:'DELETE'});conv()}catch(x){err(x.message)}})",
    )

    js = js.replace(
        "[support,files,tree]=await Promise.all([api('/api/empresas/'+encodeURIComponent(key)+'/soporte'),api('/api/empresas/'+encodeURIComponent(key)+'/archivos'),api('/api/empresas/'+encodeURIComponent(key)+'/arbol')]);treeDraft=normalizeTree(tree);",
        "[support,files,tree,authorized,ident]=await Promise.all([api('/api/empresas/'+encodeURIComponent(key)+'/soporte'),api('/api/empresas/'+encodeURIComponent(key)+'/archivos'),api('/api/empresas/'+encodeURIComponent(key)+'/arbol'),api('/api/contacts'),api('/api/empresas/'+encodeURIComponent(key)+'/identificacion')]);treeDraft=normalizeTree(tree);const authorizedOptions=authorized.map(a=>'<option value=\"'+a.id+'\">'+esc(a.name||a.phone)+' · '+esc(a.phone)+'</option>').join('');const aliases=(ident.aliases||[]).join(', '),keywords=(ident.keywords||[]).join(', '),tags=(ident.tags||[]).join(', ');",
    )
    js = js.replace(
        "<input id=\"supportName\" placeholder=\"Nombre\"><input id=\"supportPhone\" placeholder=\"Teléfono\"><select id=\"supportRole\"><option value=\"primary\">Primario</option><option value=\"secondary\">Secundario</option></select><input id=\"supportMinutes\" type=\"number\" value=\"15\"><button id=\"addSupport\">Agregar apoyo</button>",
        "<label>Contacto autorizado</label><select id=\"supportContact\"><option value=\"\">Selecciona contacto</option>'+authorizedOptions+'</select><select id=\"supportRole\"><option value=\"primary\">Primario</option><option value=\"secondary\">Secundario</option></select><label>Minutos antes del siguiente escalón</label><input id=\"supportMinutes\" type=\"number\" min=\"1\" value=\"5\"><button id=\"addSupport\">Asignar apoyo</button>",
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

    js = js.replace(
        "</div></div><div id=\"treeVisual\"></div><div class=\"card\"><h3>Archivos</h3>",
        "</div></div>${admin()?`<div class=\"card\"><h3>Cómo identificar esta empresa</h3><p class=\"muted\">El bot usa estas pistas antes de aplicar el árbol.</p><label>Alias / marcas</label><input id=\"companyAliases\" value=\"${esc(aliases)}\" placeholder=\"Coppel, Coppel Canadá\"><label>Etiquetas</label><input id=\"companyTags\" value=\"${esc(tags)}\" placeholder=\"mueble isla, pantalla, video panel\"><label>Palabras clave</label><textarea id=\"companyKeywords\" placeholder=\"crédito, exhibidor, iqos, cck...\">${esc(keywords)}</textarea><button id=\"saveIdentification\">Guardar identificación</button></div><div class=\"card\"><h3>Herramientas de empresa</h3><p class=\"muted\">La plantilla agrega las opciones base que falten sin borrar tu árbol actual.</p><button id=\"applyBaseTemplate\">Agregar opciones predeterminadas</button><button id=\"deleteCompany\" class=\"danger\">Eliminar empresa</button></div>`:''}<div id=\"treeVisual\"></div><div class=\"card\"><h3>Archivos</h3>",
    )
    js = js.replace(
        "if(admin()){$('saveCompanyName').onclick=async()=>{",
        "if(admin()){$('saveIdentification').onclick=async()=>{const split=v=>v.split(',').map(x=>x.trim()).filter(Boolean);try{await api('/api/empresas/'+encodeURIComponent(key)+'/identificacion',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({aliases:split($('companyAliases').value),tags:split($('companyTags').value),keywords:split($('companyKeywords').value)})});err('Identificación guardada.')}catch(x){err(x.message)}};$('applyBaseTemplate').onclick=async()=>{try{const r=await api('/api/empresas/'+encodeURIComponent(key)+'/plantilla-base',{method:'POST'});err('Plantilla combinada: '+(r.added_nodes||0)+' paso(s) y '+(r.added_options||0)+' opción(es) agregadas.');companyPanel(key)}catch(x){err(x.message)}};$('deleteCompany').onclick=async()=>{if(!confirm('¿Eliminar esta empresa? También se eliminarán sus tiendas, conversaciones de prueba, solicitudes, archivos y apoyos asignados.'))return;if(!confirm('Confirmación final: esta acción no se puede deshacer.'))return;try{await api('/api/empresas/'+encodeURIComponent(key),{method:'DELETE'});companies()}catch(x){err(x.message)}};$('saveCompanyName').onclick=async()=>{",
    )
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_v2():
    return _html()


@router.get('/dashboard.js')
def dashboard_js_v2():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
