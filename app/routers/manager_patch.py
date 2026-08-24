from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-gerente'])
UI_VERSION = '2026.08.21-22'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.21-16', '2026.08.21-17', '2026.08.21-18', '2026.08.21-19', '2026.08.21-20', '2026.08.21-21'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = base_js()
    js = js.replace(
        "if(r.status===401){localStorage.clear();location.reload();throw Error('Sesión expirada')}",
        "if(r.status===401){localStorage.removeItem(TK);localStorage.removeItem(RK);if($('app'))$('app').classList.add('h');if($('login'))$('login').classList.remove('h');const e=$('loginError');if(e)e.textContent='Sesión inválida o vencida. Inicia sesión nuevamente.';throw Error('Sesión inválida o vencida')}",
    )
    js = js.replace(
        "if(localStorage.getItem(TK))show()",
        "if(new URLSearchParams(location.search).get('embedded')==='1'&&localStorage.getItem(TK))show()",
    )
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
        '<h2>Usuarios</h2><div class="two">',
        '<h2>Usuarios</h2><div class="card"><h3>Permisos por rol</h3><p class="muted">Los permisos se aplican a todas las cuentas del rol. El nivel propietario del sistema permanece oculto.</p><div class="toolbar"><button data-edit-role="gerente">Gerente</button><button data-edit-role="operador">Operador</button><button data-edit-role="lector">Lector</button></div></div><div class="two">',
    )
    js = js.replace(
        '<div class="toolbar"><button class="saveRole">Guardar rol</button>',
        '<div class="toolbar"><button class="saveRole">Guardar rol</button><button type="button" data-edit-role="${u.role}">Editar permisos del rol</button>',
    )
    js = js.replace(
        "$('content').innerHTML='<h2>Conversaciones</h2>'+a.map(",
        "$('content').innerHTML='<h2>Conversaciones</h2><p class=\"muted\">Los chats que solicitaron atención humana se muestran en Solicitudes de ayuda mientras estén pendientes o en atención.</p>'+a.filter(r=>!['help_pending','human_active'].includes(r.status)).map(",
    )

    settings_code = r'''
let ACTIVE_PERMISSIONS={};
const GLOBAL_THEME_DEFAULTS={background:'#040814',cards:'#0a1322',text:'#edf6ff',accent:'#4cb6ff',input:'#08111f',backgroundImage:'',backgroundSize:'cover',imageRepeatCount:1,cardOpacity:90,contentWidth:'1240',density:'comfortable',cardRadius:'18'};
function alphaHex(percent){const n=Math.round(Math.max(0,Math.min(100,Number(percent||90)))*2.55);return n.toString(16).padStart(2,'0')}
function globalThemeStyle(t){const count=Math.max(1,Number(t.imageRepeatCount||1));const bgimg=t.backgroundImage?`url("${String(t.backgroundImage).replace(/["\\]/g,'')}")`:'none';const bgRepeat=count>1?'repeat':'no-repeat';const bgSize=count>1?`${100/count}% auto`:(t.backgroundSize||'cover');const pad=t.density==='compact'?'10px':(t.density==='spacious'?'24px':'18px');const margin=t.density==='compact'?'8px':(t.density==='spacious'?'20px':'14px');const opacity=alphaHex(t.cardOpacity);return `body{background-color:${t.background};background-image:${bgimg};background-size:${bgSize};background-repeat:${bgRepeat};background-position:center;background-attachment:fixed;color:${t.text}}.w{max-width:${t.contentWidth||'1240'}px}.card{background:${t.cards}${opacity};border-color:${t.accent}38;border-radius:${t.cardRadius||'18'}px;padding:${pad};margin:${margin} 0}input,button,select,textarea{background:${t.input};color:${t.text};border-color:${t.accent}66}button:hover{border-color:${t.accent};box-shadow:0 0 18px ${t.accent}33}.muted{color:${t.text}99}.badge{background:${t.accent}33}.option{border-left-color:${t.accent}}`;}
applyTheme=async function(){try{const [theme,perm]=await Promise.all([api('/api/settings/appearance'),api('/api/settings/me-permissions')]);ACTIVE_PERMISSIONS=perm.permissions||{};let st=$('phygitalThemeStyle');if(!st){st=document.createElement('style');st.id='phygitalThemeStyle';document.head.appendChild(st)}st.textContent=globalThemeStyle({...GLOBAL_THEME_DEFAULTS,...theme});if($('navAppearance'))$('navAppearance').classList.toggle('h',!ACTIVE_PERMISSIONS.appearance_edit);if($('navActivity'))$('navActivity').classList.toggle('h',!ACTIVE_PERMISSIONS.activity_view);if($('navUsers'))$('navUsers').classList.toggle('h',!rootAdmin())}catch(_){}};
appearance=async function(){if(!ACTIVE_PERMISSIONS.appearance_edit&&!rootAdmin())return err('Tu rol no tiene permiso para editar la apariencia global.');err('');let t={...GLOBAL_THEME_DEFAULTS};try{t={...t,...await api('/api/settings/appearance')}}catch(x){return err(x.message)}$('content').innerHTML=`<div class="section-title"><h2>Apariencia global</h2><span class="badge">Se aplica a todas las cuentas</span></div><p class="muted">Todos los usuarios y dispositivos verán este mismo diseño.</p><div class="appearance-grid"><label>Fondo<input id="themeBackground" type="color" value="${esc(t.background)}"></label><label>Tarjetas / ventanas<input id="themeCards" type="color" value="${esc(t.cards)}"></label><label>Transparencia de ventanas <span id="opacityValue">${esc(t.cardOpacity)}%</span><input id="themeOpacity" type="range" min="10" max="100" step="5" value="${esc(t.cardOpacity)}"></label><label>Texto<input id="themeText" type="color" value="${esc(t.text)}"></label><label>Color principal<input id="themeAccent" type="color" value="${esc(t.accent)}"></label><label>Campos y botones<input id="themeInput" type="color" value="${esc(t.input)}"></label><label>Imagen de fondo (URL)<input id="themeImage" value="${esc(t.backgroundImage||'')}" placeholder="https://..."></label><label>Ajuste de imagen<select id="themeSize"><option value="cover" ${t.backgroundSize==='cover'?'selected':''}>Cubrir</option><option value="contain" ${t.backgroundSize==='contain'?'selected':''}>Contener</option><option value="auto" ${t.backgroundSize==='auto'?'selected':''}>Tamaño original</option></select></label><label>Veces que se repite la imagen<input id="themeRepeat" type="number" min="1" max="12" value="${esc(t.imageRepeatCount||1)}"><span class="muted">1 = una sola imagen; 2-12 = mosaico repetido.</span></label><label>Ancho del dashboard<select id="themeWidth"><option value="960" ${t.contentWidth==='960'?'selected':''}>Compacto 960</option><option value="1100" ${t.contentWidth==='1100'?'selected':''}>1100</option><option value="1240" ${t.contentWidth==='1240'?'selected':''}>Normal 1240</option><option value="1440" ${t.contentWidth==='1440'?'selected':''}>Amplio 1440</option><option value="1600" ${t.contentWidth==='1600'?'selected':''}>Muy amplio 1600</option></select></label><label>Densidad<select id="themeDensity"><option value="compact" ${t.density==='compact'?'selected':''}>Compacta</option><option value="comfortable" ${t.density==='comfortable'?'selected':''}>Cómoda</option><option value="spacious" ${t.density==='spacious'?'selected':''}>Espaciosa</option></select></label><label>Redondeo de tarjetas<select id="themeRadius"><option value="0" ${t.cardRadius==='0'?'selected':''}>Recto</option><option value="8" ${t.cardRadius==='8'?'selected':''}>8 px</option><option value="12" ${t.cardRadius==='12'?'selected':''}>12 px</option><option value="18" ${t.cardRadius==='18'?'selected':''}>18 px</option><option value="24" ${t.cardRadius==='24'?'selected':''}>24 px</option><option value="32" ${t.cardRadius==='32'?'selected':''}>32 px</option></select></label></div><div id="themePreview" class="theme-preview">Vista previa global</div><div class="toolbar"><button id="saveTheme">Guardar para todas las cuentas</button><button id="resetTheme">Restablecer valores base</button></div>`;const read=()=>({background:$('themeBackground').value,cards:$('themeCards').value,text:$('themeText').value,accent:$('themeAccent').value,input:$('themeInput').value,backgroundImage:$('themeImage').value.trim(),backgroundSize:$('themeSize').value,imageRepeatCount:Number($('themeRepeat').value||1),cardOpacity:Number($('themeOpacity').value||90),contentWidth:$('themeWidth').value,density:$('themeDensity').value,cardRadius:$('themeRadius').value});const preview=()=>{const x=read();$('opacityValue').textContent=x.cardOpacity+'%';const count=Math.max(1,x.imageRepeatCount);$('themePreview').style.backgroundImage=x.backgroundImage?`url("${x.backgroundImage.replace(/["\\]/g,'')}")`:'none';$('themePreview').style.backgroundColor=x.background;$('themePreview').style.backgroundRepeat=count>1?'repeat':'no-repeat';$('themePreview').style.backgroundSize=count>1?`${100/count}% auto`:x.backgroundSize;$('themePreview').style.color=x.text;$('themePreview').style.borderColor=x.accent;$('themePreview').style.borderRadius=x.cardRadius+'px';$('themePreview').style.opacity=Math.max(.1,x.cardOpacity/100)};['themeBackground','themeCards','themeText','themeAccent','themeInput','themeImage','themeSize','themeRepeat','themeOpacity','themeWidth','themeDensity','themeRadius'].forEach(id=>$(id).oninput=preview);preview();$('saveTheme').onclick=async()=>{try{await api('/api/settings/appearance',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(read())});await applyTheme();err('Apariencia global guardada. Ya aplica para todas las cuentas.')}catch(x){err(x.message)}};$('resetTheme').onclick=async()=>{try{await api('/api/settings/appearance',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(GLOBAL_THEME_DEFAULTS)});await applyTheme();appearance()}catch(x){err(x.message)}}};
async function editRolePermissions(roleName){if(!rootAdmin())return err('Solo el propietario puede editar permisos de roles.');try{const data=await api('/api/settings/role-policies'),item=(data.roles||[]).find(x=>x.role===roleName);if(!item)return err('Rol no encontrado');const labels=data.labels||{};$('content').innerHTML=`<button id="backUsers">← Usuarios</button><h2>Editar permisos del rol: ${esc(roleName)}</h2><p class="muted">Los cambios afectarán a todas las cuentas con este rol.</p><div class="card">${Object.entries(labels).map(([key,label])=>`<label style="display:flex;gap:10px;align-items:center;margin:10px 0"><input style="width:auto" type="checkbox" data-permission="${esc(key)}" ${item.permissions?.[key]?'checked':''}><span>${esc(label)}</span></label>`).join('')}</div><button id="saveRolePermissions">Guardar permisos del rol</button>`;$('backUsers').onclick=users;$('saveRolePermissions').onclick=async()=>{const permissions={};document.querySelectorAll('[data-permission]').forEach(x=>permissions[x.dataset.permission]=x.checked);try{await api('/api/settings/role-policies/'+encodeURIComponent(roleName),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({permissions})});err('Permisos del rol actualizados.');users()}catch(x){err(x.message)}}}catch(x){err(x.message)}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-edit-role]');if(b){e.preventDefault();editRolePermissions(b.dataset.editRole)}});
activity=async function(selected=''){if(!ACTIVE_PERMISSIONS.activity_view&&!rootAdmin())return err('Tu rol no tiene permiso para ver actividad.');err('');try{const usersList=await api('/api/audit/activity/users');const query=selected?'?limit=500&username='+encodeURIComponent(selected):'?limit=500';const rows=await api('/api/audit/activity'+query);$('content').innerHTML=`<div class="section-title"><h2>Actividad</h2>${rootAdmin()?'<button id="clearActivity" class="danger">Eliminar actividad visible</button>':''}</div><p class="muted">El historial del propietario del sistema no se registra ni se muestra.</p><label>Ver actividad por usuario</label><select id="activityUser"><option value="">Todos los usuarios</option>${usersList.map(u=>`<option value="${esc(u)}" ${u===selected?'selected':''}>${esc(u)}</option>`).join('')}</select><div id="activityRows">${rows.map(r=>`<div class="row activity" data-audit="${r.id}"><span class="ok">${esc(r.username||'sistema')}</span> · ${esc(r.action)} · ${esc(r.entity||'')} · ${esc(r.created_at)}${rootAdmin()?`<button class="deleteAudit danger" style="width:auto;margin-left:8px">Eliminar</button>`:''}<div class="muted">${esc(JSON.stringify(r.details||{}))}</div></div>`).join('')||'<div class="muted">Sin actividad.</div>'}</div>`;$('activityUser').onchange=()=>activity($('activityUser').value);document.querySelectorAll('.deleteAudit').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-audit]');if(!confirm('¿Eliminar este registro de actividad?'))return;try{await api('/api/audit/activity/'+row.dataset.audit,{method:'DELETE'});activity($('activityUser').value)}catch(x){err(x.message)}});if($('clearActivity'))$('clearActivity').onclick=async()=>{const user=$('activityUser').value;const msg=user?'¿Eliminar toda la actividad visible de '+user+'?':'¿Eliminar toda la actividad visible?';if(!confirm(msg))return;try{await api('/api/audit/activity'+(user?'?username='+encodeURIComponent(user):''),{method:'DELETE'});activity(user)}catch(x){err(x.message)}}}catch(x){err(x.message)}};
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", settings_code + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_gerente():
    return _html()


@router.get('/dashboard.js')
def dashboard_js_gerente():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
