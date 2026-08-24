from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-gerente'])
UI_VERSION = '2026.08.21-18'


def _html() -> str:
    html = base_html().replace('UI 2026.08.21-16', f'UI {UI_VERSION}').replace('UI 2026.08.21-17', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.08.21-16', f'/dashboard.js?v={UI_VERSION}').replace('/dashboard.js?v=2026.08.21-17', f'/dashboard.js?v={UI_VERSION}')
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
        '<h2>Usuarios</h2><div class="two">',
        '<h2>Usuarios</h2><div class="card"><h3>Permisos por rol</h3><p class="muted">Los permisos se aplican a todas las cuentas que tengan ese rol.</p><div class="toolbar"><button data-edit-role="admin">Administrador</button><button data-edit-role="gerente">Gerente</button><button data-edit-role="operador">Operador</button><button data-edit-role="lector">Lector</button></div></div><div class="two">',
    )
    js = js.replace(
        '<div class="toolbar"><button class="saveRole">Guardar rol</button>',
        '<div class="toolbar"><button class="saveRole">Guardar rol</button><button type="button" data-edit-role="${u.role}">Editar permisos del rol</button>',
    )

    settings_code = r'''
let ACTIVE_PERMISSIONS={};
const GLOBAL_THEME_DEFAULTS={background:'#040814',cards:'#0a1322',text:'#edf6ff',accent:'#4cb6ff',input:'#08111f',backgroundImage:'',backgroundSize:'cover',contentWidth:'1240',density:'comfortable',cardRadius:'18'};
function globalThemeStyle(t){const bgimg=t.backgroundImage?`url("${String(t.backgroundImage).replace(/["\\]/g,'')}")`:'none';const pad=t.density==='compact'?'10px':(t.density==='spacious'?'24px':'18px');const margin=t.density==='compact'?'8px':(t.density==='spacious'?'20px':'14px');return `body{background-color:${t.background};background-image:${bgimg};background-size:${t.backgroundSize||'cover'};background-position:center;background-attachment:fixed;color:${t.text}}.w{max-width:${t.contentWidth||'1240'}px}.card{background:${t.cards}e6;border-color:${t.accent}38;border-radius:${t.cardRadius||'18'}px;padding:${pad};margin:${margin} 0}input,button,select,textarea{background:${t.input};color:${t.text};border-color:${t.accent}66}button:hover{border-color:${t.accent};box-shadow:0 0 18px ${t.accent}33}.muted{color:${t.text}99}.badge{background:${t.accent}33}.option{border-left-color:${t.accent}}`;}
applyTheme=async function(){try{const [theme,perm]=await Promise.all([api('/api/settings/appearance'),api('/api/settings/me-permissions')]);ACTIVE_PERMISSIONS=perm.permissions||{};let st=$('phygitalThemeStyle');if(!st){st=document.createElement('style');st.id='phygitalThemeStyle';document.head.appendChild(st)}st.textContent=globalThemeStyle({...GLOBAL_THEME_DEFAULTS,...theme});if($('navAppearance'))$('navAppearance').classList.toggle('h',!ACTIVE_PERMISSIONS.appearance_edit);if($('navActivity'))$('navActivity').classList.toggle('h',!ACTIVE_PERMISSIONS.activity_view);if($('navUsers'))$('navUsers').classList.toggle('h',!rootAdmin())}catch(_){}};
appearance=async function(){if(!ACTIVE_PERMISSIONS.appearance_edit&& !rootAdmin())return err('Tu rol no tiene permiso para editar la apariencia global.');err('');let t={...GLOBAL_THEME_DEFAULTS};try{t={...t,...await api('/api/settings/appearance')}}catch(x){return err(x.message)}$('content').innerHTML=`<div class="section-title"><h2>Apariencia global</h2><span class="badge">Se aplica a todas las cuentas</span></div><p class="muted">Los cambios se guardan en el servidor. Todos los usuarios y dispositivos verán este mismo diseño.</p><div class="appearance-grid"><label>Fondo<input id="themeBackground" type="color" value="${esc(t.background)}"></label><label>Tarjetas<input id="themeCards" type="color" value="${esc(t.cards)}"></label><label>Texto<input id="themeText" type="color" value="${esc(t.text)}"></label><label>Color principal<input id="themeAccent" type="color" value="${esc(t.accent)}"></label><label>Campos y botones<input id="themeInput" type="color" value="${esc(t.input)}"></label><label>Imagen de fondo (URL)<input id="themeImage" value="${esc(t.backgroundImage||'')}" placeholder="https://..."></label><label>Ajuste de imagen<select id="themeSize"><option value="cover" ${t.backgroundSize==='cover'?'selected':''}>Cubrir</option><option value="contain" ${t.backgroundSize==='contain'?'selected':''}>Contener</option><option value="auto" ${t.backgroundSize==='auto'?'selected':''}>Tamaño original</option></select></label><label>Ancho del dashboard<select id="themeWidth"><option value="960" ${t.contentWidth==='960'?'selected':''}>Compacto 960</option><option value="1100" ${t.contentWidth==='1100'?'selected':''}>1100</option><option value="1240" ${t.contentWidth==='1240'?'selected':''}>Normal 1240</option><option value="1440" ${t.contentWidth==='1440'?'selected':''}>Amplio 1440</option><option value="1600" ${t.contentWidth==='1600'?'selected':''}>Muy amplio 1600</option></select></label><label>Densidad<select id="themeDensity"><option value="compact" ${t.density==='compact'?'selected':''}>Compacta</option><option value="comfortable" ${t.density==='comfortable'?'selected':''}>Cómoda</option><option value="spacious" ${t.density==='spacious'?'selected':''}>Espaciosa</option></select></label><label>Redondeo de tarjetas<select id="themeRadius"><option value="0" ${t.cardRadius==='0'?'selected':''}>Recto</option><option value="8" ${t.cardRadius==='8'?'selected':''}>8 px</option><option value="12" ${t.cardRadius==='12'?'selected':''}>12 px</option><option value="18" ${t.cardRadius==='18'?'selected':''}>18 px</option><option value="24" ${t.cardRadius==='24'?'selected':''}>24 px</option><option value="32" ${t.cardRadius==='32'?'selected':''}>32 px</option></select></label></div><div id="themePreview" class="theme-preview">Vista previa global</div><div class="toolbar"><button id="saveTheme">Guardar para todas las cuentas</button><button id="resetTheme">Restablecer valores base</button></div>`;const read=()=>({background:$('themeBackground').value,cards:$('themeCards').value,text:$('themeText').value,accent:$('themeAccent').value,input:$('themeInput').value,backgroundImage:$('themeImage').value.trim(),backgroundSize:$('themeSize').value,contentWidth:$('themeWidth').value,density:$('themeDensity').value,cardRadius:$('themeRadius').value});const preview=()=>{const x=read();$('themePreview').style.background=x.backgroundImage?`${x.background} url("${x.backgroundImage.replace(/["\\]/g,'')}") center/${x.backgroundSize} no-repeat`:x.background;$('themePreview').style.color=x.text;$('themePreview').style.borderColor=x.accent;$('themePreview').style.borderRadius=x.cardRadius+'px'};['themeBackground','themeCards','themeText','themeAccent','themeInput','themeImage','themeSize','themeWidth','themeDensity','themeRadius'].forEach(id=>$(id).oninput=preview);preview();$('saveTheme').onclick=async()=>{try{await api('/api/settings/appearance',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(read())});await applyTheme();err('Apariencia global guardada. Ya aplica para todas las cuentas.')}catch(x){err(x.message)}};$('resetTheme').onclick=async()=>{try{await api('/api/settings/appearance',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(GLOBAL_THEME_DEFAULTS)});await applyTheme();appearance()}catch(x){err(x.message)}}};
async function editRolePermissions(roleName){if(!rootAdmin())return err('Solo el Administrador puede editar permisos de roles.');try{const data=await api('/api/settings/role-policies'),item=(data.roles||[]).find(x=>x.role===roleName);if(!item)return err('Rol no encontrado');const labels=data.labels||{},locked=!!item.protected;$('content').innerHTML=`<button id="backUsers">← Usuarios</button><h2>Editar permisos del rol: ${esc(roleName)}</h2>${locked?'<p class="muted">El Administrador principal está protegido y siempre conserva todos sus permisos.</p>':'<p class="muted">Los cambios afectarán a todas las cuentas con este rol.</p>'}<div class="card">${Object.entries(labels).map(([key,label])=>`<label style="display:flex;gap:10px;align-items:center;margin:10px 0"><input style="width:auto" type="checkbox" data-permission="${esc(key)}" ${item.permissions?.[key]?'checked':''} ${locked?'disabled':''}><span>${esc(label)}</span></label>`).join('')}</div>${locked?'':'<button id="saveRolePermissions">Guardar permisos del rol</button>'}`;$('backUsers').onclick=users;if($('saveRolePermissions'))$('saveRolePermissions').onclick=async()=>{const permissions={};document.querySelectorAll('[data-permission]').forEach(x=>permissions[x.dataset.permission]=x.checked);try{await api('/api/settings/role-policies/'+encodeURIComponent(roleName),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({permissions})});err('Permisos del rol actualizados.');users()}catch(x){err(x.message)}}}catch(x){err(x.message)}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-edit-role]');if(b){e.preventDefault();editRolePermissions(b.dataset.editRole)}});
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", settings_code + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_gerente():
    return _html()


@router.get('/dashboard.js')
def dashboard_js_gerente():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
