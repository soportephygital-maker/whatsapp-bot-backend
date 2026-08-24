from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .dashboard_ui import HTML, JS

router = APIRouter(tags=['dashboard-ui-v2'])
UI_VERSION = '2026.08.21-16'


def _html() -> str:
    html = HTML.replace('__UI_VERSION__', UI_VERSION)
    html = html.replace('<button id="navContacts">Contactos</button>', '<button id="navContacts" class="h">Personal de soporte</button>')
    html = html.replace('<button id="navActivity" class="h">Actividad</button><button id="logoutBtn">Salir</button>', '<button id="navActivity" class="h">Actividad</button><button id="navAppearance" class="h">Apariencia</button><button id="logoutBtn">Salir</button>')
    html = html.replace('</style></head>', '''
.theme-preview{height:90px;border-radius:14px;border:1px solid rgba(92,168,255,.22);background-position:center;background-size:cover;display:flex;align-items:center;justify-content:center;font-weight:700;margin:8px 0}.appearance-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.appearance-grid label{display:block;font-size:13px;color:#8fa8c3}.appearance-grid input[type=color]{height:46px;padding:4px}.delivery-state{font-size:11px;margin-top:4px;opacity:.8}
</style></head>''')
    html = html.replace('/dashboard.js?v=__UI_VERSION__', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = JS
    js = js.replace(
        "$('navUsers').classList.toggle('h',!admin());$('navActivity').classList.toggle('h',!admin());",
        "$('navUsers').classList.toggle('h',!admin());$('navActivity').classList.toggle('h',!admin());$('navContacts').classList.toggle('h',!admin());$('navAppearance').classList.toggle('h',!admin());applyTheme();",
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
        "<div class=\"muted\">${esc(m.created_at)}</div></div>",
        "<div class=\"muted\">${esc(m.created_at)}</div>${m.direction==='outbound'&&m.delivery?.delivery_status?`<div class=\"delivery-state\">${m.delivery.delivery_status==='requested'?'Pendiente de envío por teléfono':(m.delivery.delivery_status==='sent'?'Enviado por teléfono':(m.delivery.delivery_status==='failed'?'Error de envío':'Estado: '+esc(m.delivery.delivery_status)))}</div>`:''}</div>",
    )
    js = js.replace(
        "await api('/api/conversaciones/'+id+'/responder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});openChat(id)",
        "const sent=await api('/api/conversaciones/'+id+'/responder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});err(sent.queued?'Respuesta enviada al teléfono administrador. El bot quedó pausado para este chat.':'Respuesta enviada. El bot quedó pausado para este chat.');openChat(id)",
    )
    js = js.replace(
        "[support,files,tree]=await Promise.all([api('/api/empresas/'+encodeURIComponent(key)+'/soporte'),api('/api/empresas/'+encodeURIComponent(key)+'/archivos'),api('/api/empresas/'+encodeURIComponent(key)+'/arbol')]);treeDraft=normalizeTree(tree);",
        "[support,files,tree,authorized,ident,stores]=await Promise.all([api('/api/empresas/'+encodeURIComponent(key)+'/soporte'),api('/api/empresas/'+encodeURIComponent(key)+'/archivos'),api('/api/empresas/'+encodeURIComponent(key)+'/arbol'),api('/api/contacts'),api('/api/empresas/'+encodeURIComponent(key)+'/identificacion'),api('/api/empresas/'+encodeURIComponent(key)+'/tiendas')]);treeDraft=normalizeTree(tree);const authorizedOptions=authorized.map(a=>'<option value=\"'+a.id+'\">'+esc(a.name||a.phone)+' · '+esc(a.phone)+'</option>').join('');const aliases=(ident.aliases||[]).join(', '),keywords=(ident.keywords||[]).join(', '),tags=(ident.tags||[]).join(', ');",
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
        "</div></div>${admin()?`<div class=\"card\"><h3>Tiendas / teléfonos</h3><p class=\"muted\">Puedes tener varias tiendas y seleccionar una o más desde la app Android.</p><div id=\"storesList\">${stores.map(s=>`<div class=\"row\" data-store=\"${s.id}\"><input class=\"storeName\" value=\"${esc(s.nombre)}\"><div class=\"toolbar\"><button class=\"saveStore\">Guardar</button>${stores.length>1?'<button class=\"deleteStore danger\">Eliminar</button>':''}</div></div>`).join('')}</div><input id=\"newStoreName\" placeholder=\"Nombre de nueva tienda\"><button id=\"addStore\">Agregar tienda</button></div><div class=\"card\"><h3>Cómo identificar esta empresa</h3><p class=\"muted\">El bot usa estas pistas antes de aplicar el árbol.</p><label>Alias / marcas</label><input id=\"companyAliases\" value=\"${esc(aliases)}\" placeholder=\"Coppel, Coppel Canadá\"><label>Etiquetas</label><input id=\"companyTags\" value=\"${esc(tags)}\" placeholder=\"mueble isla, pantalla, video panel\"><label>Palabras clave</label><textarea id=\"companyKeywords\" placeholder=\"crédito, exhibidor, iqos, cck...\">${esc(keywords)}</textarea><button id=\"saveIdentification\">Guardar identificación</button></div><div class=\"card\"><h3>Herramientas de empresa</h3><p class=\"muted\">La plantilla agrega las opciones base que falten sin borrar tu árbol actual.</p><button id=\"applyBaseTemplate\">Agregar opciones predeterminadas</button><button id=\"deleteCompany\" class=\"danger\">Eliminar empresa</button></div>`:''}<div id=\"treeVisual\"></div><div class=\"card\"><h3>Archivos</h3>",
    )
    js = js.replace(
        "if(admin()){$('saveCompanyName').onclick=async()=>{",
        "if(admin()){$('addStore').onclick=async()=>{const name=$('newStoreName').value.trim();if(!name)return err('Escribe un nombre para la tienda');try{await api('/api/empresas/'+encodeURIComponent(key)+'/tiendas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});companyPanel(key)}catch(x){err(x.message)}};document.querySelectorAll('.saveStore').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-store]'),name=row.querySelector('.storeName').value.trim();if(!name)return err('El nombre de tienda no puede estar vacío');try{await api('/api/empresas/'+encodeURIComponent(key)+'/tiendas/'+row.dataset.store,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});companyPanel(key)}catch(x){err(x.message)}});document.querySelectorAll('.deleteStore').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-store]');if(!confirm('¿Eliminar esta tienda?'))return;try{await api('/api/empresas/'+encodeURIComponent(key)+'/tiendas/'+row.dataset.store,{method:'DELETE'});companyPanel(key)}catch(x){err(x.message)}});$('saveIdentification').onclick=async()=>{const split=v=>v.split(',').map(x=>x.trim()).filter(Boolean);try{await api('/api/empresas/'+encodeURIComponent(key)+'/identificacion',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({aliases:split($('companyAliases').value),tags:split($('companyTags').value),keywords:split($('companyKeywords').value)})});err('Identificación guardada.')}catch(x){err(x.message)}};$('applyBaseTemplate').onclick=async()=>{try{const r=await api('/api/empresas/'+encodeURIComponent(key)+'/plantilla-base',{method:'POST'});err('Plantilla combinada: '+(r.added_nodes||0)+' paso(s) y '+(r.added_options||0)+' opción(es) agregadas.');companyPanel(key)}catch(x){err(x.message)}};$('deleteCompany').onclick=async()=>{if(!confirm('¿Eliminar esta empresa? También se eliminarán sus tiendas, conversaciones de prueba, solicitudes, archivos y apoyos asignados.'))return;if(!confirm('Confirmación final: esta acción no se puede deshacer.'))return;try{await api('/api/empresas/'+encodeURIComponent(key),{method:'DELETE'});companies()}catch(x){err(x.message)}};$('saveCompanyName').onclick=async()=>{",
    )
    js = js.replace(
        "return {nodo_raiz:clean[root]?root:Object.keys(clean)[0],nodos:clean}",
        "return {nodo_raiz:clean[root]?root:Object.keys(clean)[0],nodos:clean,respuesta_sin_sentido_1:String(raw?.respuesta_sin_sentido_1||'No pude identificar una opción válida. Por favor describe nuevamente lo que necesitas o usa alguna de las opciones disponibles.'),respuesta_sin_sentido_2:String(raw?.respuesta_sin_sentido_2||'Sigo sin poder identificar tu solicitud. Revisa las opciones disponibles o escribe humano si necesitas atención de una persona.')}",
    )
    js = js.replace(
        "return {nodo_raiz:'inicio',nodos:{inicio:{mensaje:'Escribe aquí el mensaje inicial.',opciones:[]}}}",
        "return {nodo_raiz:'inicio',nodos:{inicio:{mensaje:'Escribe aquí el mensaje inicial.',opciones:[]}},respuesta_sin_sentido_1:'No pude identificar una opción válida. Por favor describe nuevamente lo que necesitas o usa alguna de las opciones disponibles.',respuesta_sin_sentido_2:'Sigo sin poder identificar tu solicitud. Revisa las opciones disponibles o escribe humano si necesitas atención de una persona.'}",
    )
    js = js.replace(
        "if($('rootNode'))treeDraft.nodo_raiz=$('rootNode').value}",
        "if($('rootNode'))treeDraft.nodo_raiz=$('rootNode').value;if($('noMatchFirst'))treeDraft.respuesta_sin_sentido_1=$('noMatchFirst').value;if($('noMatchRepeat'))treeDraft.respuesta_sin_sentido_2=$('noMatchRepeat').value}",
    )
    js = js.replace(
        "<div id=\"nodesHost\"></div>${admin()?'<button id=\"saveTree\">Guardar árbol</button>':''}",
        "<div id=\"nodesHost\"></div><div class=\"card\"><h4>Cuando no entiende el mensaje</h4><p class=\"muted\">Estos textos se usan solo cuando ninguna palabra/criterio del paso actual coincide.</p><label>Primera vez que no entiende</label><textarea id=\"noMatchFirst\" ${admin()?'':'readonly'}>${esc(treeDraft.respuesta_sin_sentido_1||'')}</textarea><label>Si vuelve a insistir con algo que no coincide</label><textarea id=\"noMatchRepeat\" ${admin()?'':'readonly'}>${esc(treeDraft.respuesta_sin_sentido_2||'')}</textarea></div>${admin()?'<button id=\"saveTree\">Guardar árbol</button>':''}",
    )

    appearance_code = r'''
const THEME_KEY='phygital_dashboard_theme_v1';
function themeDefaults(){return {background:'#040814',cards:'#0a1322',text:'#edf6ff',accent:'#4cb6ff',input:'#08111f',backgroundImage:'',backgroundSize:'cover'}}
function loadTheme(){try{return {...themeDefaults(),...JSON.parse(localStorage.getItem(THEME_KEY)||'{}')}}catch(_){return themeDefaults()}}
function applyTheme(){const t=loadTheme();let st=$('phygitalThemeStyle');if(!st){st=document.createElement('style');st.id='phygitalThemeStyle';document.head.appendChild(st)}const bgimg=t.backgroundImage?`url("${String(t.backgroundImage).replace(/["\\]/g,'')}")`:'none';st.textContent=`body{background-color:${t.background};background-image:${bgimg};background-size:${t.backgroundSize||'cover'};background-position:center;background-attachment:fixed;color:${t.text}}.card{background:${t.cards}e6;border-color:${t.accent}38}input,button,select,textarea{background:${t.input};color:${t.text};border-color:${t.accent}66}button:hover{border-color:${t.accent};box-shadow:0 0 18px ${t.accent}33}.muted{color:${t.text}99}.badge{background:${t.accent}33}.option{border-left-color:${t.accent}}`;}
function appearance(){if(!admin())return;err('');const t=loadTheme();$('content').innerHTML=`<div class="section-title"><h2>Apariencia</h2><span class="badge">Solo administrador</span></div><p class="muted">Los cambios se guardan en este navegador y se aplican inmediatamente al dashboard.</p><div class="appearance-grid"><label>Fondo<input id="themeBackground" type="color" value="${esc(t.background)}"></label><label>Tarjetas<input id="themeCards" type="color" value="${esc(t.cards)}"></label><label>Texto<input id="themeText" type="color" value="${esc(t.text)}"></label><label>Color principal<input id="themeAccent" type="color" value="${esc(t.accent)}"></label><label>Campos y botones<input id="themeInput" type="color" value="${esc(t.input)}"></label><label>Imagen de fondo (URL)<input id="themeImage" value="${esc(t.backgroundImage||'')}" placeholder="https://..."></label><label>Ajuste de imagen<select id="themeSize"><option value="cover" ${t.backgroundSize==='cover'?'selected':''}>Cubrir</option><option value="contain" ${t.backgroundSize==='contain'?'selected':''}>Contener</option><option value="auto" ${t.backgroundSize==='auto'?'selected':''}>Tamaño original</option></select></label></div><div id="themePreview" class="theme-preview">Vista previa</div><div class="toolbar"><button id="saveTheme">Guardar diseño</button><button id="resetTheme">Restablecer diseño</button></div>`;const read=()=>({background:$('themeBackground').value,cards:$('themeCards').value,text:$('themeText').value,accent:$('themeAccent').value,input:$('themeInput').value,backgroundImage:$('themeImage').value.trim(),backgroundSize:$('themeSize').value});const preview=()=>{const x=read();$('themePreview').style.background=x.backgroundImage?`${x.background} url("${x.backgroundImage.replace(/["\\]/g,'')}") center/${x.backgroundSize} no-repeat`:x.background;$('themePreview').style.color=x.text;$('themePreview').style.borderColor=x.accent};['themeBackground','themeCards','themeText','themeAccent','themeInput','themeImage','themeSize'].forEach(id=>$(id).oninput=preview);preview();$('saveTheme').onclick=()=>{localStorage.setItem(THEME_KEY,JSON.stringify(read()));applyTheme();err('Apariencia guardada.')};$('resetTheme').onclick=()=>{localStorage.removeItem(THEME_KEY);applyTheme();appearance()}}
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", appearance_code + "\ndocument.addEventListener('DOMContentLoaded'")
    js = js.replace("$('navActivity').onclick=activity;", "$('navActivity').onclick=activity;$('navAppearance').onclick=appearance;")
    js = js.replace(
        "if(localStorage.getItem(TK))show()});",
        "applyTheme();if(localStorage.getItem(TK)){show();if(location.hash==='#arbol')setTimeout(async()=>{try{const a=await api('/api/empresas/listar');$('content').innerHTML='<h2>Selecciona empresa para editar su árbol</h2>'+a.map(c=>`<button data-tree-company=\"${esc(c.empresa_id)}\"><b>${esc(c.nombre)}</b><div class=\"muted\">${esc(c.empresa_id)}</div></button>`).join('');document.querySelectorAll('[data-tree-company]').forEach(b=>b.onclick=()=>companyPanel(b.dataset.treeCompany))}catch(x){err(x.message)}},200)}});",
    )
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_v2():
    return _html()


@router.get('/dashboard.js')
def dashboard_js_v2():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
