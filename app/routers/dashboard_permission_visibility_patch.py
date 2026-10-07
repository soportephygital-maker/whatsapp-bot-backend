from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_role_redesign_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-permission-visibility'])
UI_VERSION = '2026.09.04-67'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-66', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-66', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</style></head>', '''<style>
/* Contrast pass: clearer separation between navigation, cards and active controls. */
:root{--ps-bg:#05101d;--ps-panel:#0b1f35;--ps-panel2:#102a47;--ps-line:#275272;--ps-text:#f3f8ff;--ps-muted:#a8bfd3;--ps-blue:#46a8ff;--ps-green:#42d6a0;--ps-red:#ff7087;--ps-purple:#a78bfa;--ps-amber:#ffd166}
html,body{background:linear-gradient(135deg,#04101c 0%,#071b2d 52%,#06121f 100%)!important;color:var(--ps-text)!important}
.ps-side{background:#06182a!important;border-right-color:#163b5a!important}.ps-brand{color:#fff}.ps-role-title,.ps-scope,.muted{color:var(--ps-muted)!important}
.ps-side .nav button{color:#d7e7f5!important}.ps-side .nav button:hover{background:#0e3458!important;border-color:#2a628e!important}.ps-side .nav button.ps-active{background:linear-gradient(180deg,#124b79,#0d3558)!important;border-color:#367cad!important;color:#fff!important;box-shadow:0 8px 24px rgba(25,116,181,.18)!important}
.ps-main{background:radial-gradient(circle at 75% -10%,rgba(43,118,184,.10),transparent 32%)}
.ps-search{background:#071a2d!important;border-color:#2a5c83!important;color:#f5f9ff!important}.ps-search::placeholder{color:#7897b1}.ps-search:focus{border-color:#4eaef6!important;box-shadow:0 0 0 3px rgba(70,168,255,.14)!important}
#stats>.card,#content.card{background:linear-gradient(180deg,rgba(15,42,69,.96),rgba(8,26,44,.98))!important;border-color:#28516f!important}#content .card{background:#0a2239!important;border-color:#234863!important}
#content .row{border-bottom-color:#21415b!important}#content th{background:#0f3657!important;color:#c5dbed!important}#content td{color:#eaf3fb!important;border-bottom-color:#21415b!important}
#content input,#content select,#content textarea{background:#061a2c!important;border-color:#326486!important;color:#fff!important}#content input:focus,#content select:focus,#content textarea:focus{outline:none;border-color:#53aff1!important;box-shadow:0 0 0 3px rgba(83,175,241,.12)!important}
#content button,.ps-main button{background:linear-gradient(180deg,#153e61,#0d2943)!important;border-color:#32658b!important;color:#eef8ff!important}#content button:hover,.ps-main button:hover{border-color:#56b5f5!important;box-shadow:0 5px 18px rgba(31,141,214,.15)!important}.danger{background:#462031!important;border-color:#91405a!important;color:#ffdce4!important}
.badge{background:#153957!important;border-color:#2d5a7d!important;color:#d9edff!important}.ps-permission-banner{background:#0b2a46!important;border-color:#2a5a7d!important;color:#cfe1ef!important}.ps-permission-banner strong{color:#fff!important}.ps-permission-count{color:#79c9ff!important}.ps-super-tools{background:#28204a!important;border-color:#7059ae!important;color:#eee8ff!important}
.ps-access-note{margin:6px 0 14px;padding:9px 12px;border-radius:10px;background:#0d304f;border:1px solid #285a7e;color:#d5e9f8;font-size:13px}.ps-access-note strong{color:#fff}
/* A control without permission must not remain visible or clickable. */
.ps-permission-hidden{display:none!important}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
const PS_NAV_PERMISSIONS={
  navHelp:'view_requests',navConv:'view_conversations',navContacts:'view_contacts',navCompanies:'view_companies',
  navReports:'view_reports',navActivity:'view_activity',navAppearance:'manage_appearance'
};
function psHas(permission){
  if(psIsSuperAdmin())return true;
  return Boolean(USER_ACCESS?.permissions?.[permission]);
}
function psHasAny(...permissions){return psIsSuperAdmin()||permissions.some(psHas)}
function psCanManageUsers(){return psHasAny('manage_users','manage_user_permissions','manage_user_companies')}
function psApplyStrictVisibility(){
  Object.entries(PS_NAV_PERMISSIONS).forEach(([id,permission])=>{const el=document.getElementById(id);if(el)el.classList.toggle('ps-permission-hidden',!psHas(permission))});
  const users=document.getElementById('navUsers');if(users)users.classList.toggle('ps-permission-hidden',!psCanManageUsers());
  const tickets=document.getElementById('navTickets');if(tickets)tickets.classList.toggle('ps-permission-hidden',!psHasAny('view_conversations','close_cases','view_reports'));

  document.querySelectorAll('button,a').forEach(el=>{
    const text=String(el.textContent||'').trim().toLowerCase();let permission=null,any=null;
    if(/enviar respuesta|responder/.test(text))permission='reply_conversations';
    else if(/cerrar caso|cerrar ticket/.test(text))permission='close_cases';
    else if(/eliminar conversación/.test(text))permission='delete_conversations';
    else if(/guardar contacto|administrar contacto|eliminar contacto/.test(text))permission='manage_contacts';
    else if(/editar árbol|guardar árbol|aplicar.*flujo|restaurar.*flujo/.test(text))permission='manage_company_tree';
    else if(/agregar tienda|crear tienda|eliminar tienda|guardar tienda/.test(text))permission='manage_stores';
    else if(/personal de soporte|correo de soporte|correo de prueba/.test(text))any=['manage_support_contacts','manage_support_emails'];
    else if(/subir archivo|eliminar archivo|archivo de empresa/.test(text))permission='manage_company_files';
    else if(/simular|simulador/.test(text))permission='simulate_bot';
    else if(/descargar reporte|exportar reporte|exportar csv|exportar pdf/.test(text))permission='download_reports';
    else if(/crear usuario|guardar rol|cambiar contraseña|desactivar|activar usuario/.test(text))permission='manage_users';
    else if(/guardar permisos|configurar permisos/.test(text))permission='manage_user_permissions';
    if(permission)el.classList.toggle('ps-permission-hidden',!psHas(permission));
    else if(any)el.classList.toggle('ps-permission-hidden',!psHasAny(...any));
  });
}
function psReplaceAccessLegend(){
  const root=document.getElementById('content');if(!root)return;
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  nodes.forEach(node=>{
    const text=String(node.nodeValue||'');
    if(/solo el super admin puede administrar usuarios y permisos/i.test(text)){
      node.nodeValue=text.replace(/solo el super admin puede administrar usuarios y permisos/ig,'Solo el Gerente o Administrador tiene acceso a Usuarios y permisos.');
      const parent=node.parentElement;if(parent){parent.style.color='#d5e9f8';parent.style.background='#0d304f';parent.style.border='1px solid #285a7e';parent.style.borderRadius='10px';parent.style.padding='9px 12px';}
    }
  });
}
function psPermissionSweep(){psApplyStrictVisibility();psReplaceAccessLegend()}
const _psvApplyPermissionNavigation=applyPermissionNavigation;
applyPermissionNavigation=function(){_psvApplyPermissionNavigation();psPermissionSweep();};
const _psvRefreshRoleChrome=psRefreshRoleChrome;
psRefreshRoleChrome=function(){_psvRefreshRoleChrome();psPermissionSweep();};
const _psvCompanyPanel=companyPanel;
companyPanel=async function(key){await _psvCompanyPanel(key);psPermissionSweep();};
if(typeof users==='function'){const _psvUsers=users;users=async function(){await _psvUsers();psReplaceAccessLegend();psPermissionSweep();};}
if(typeof ticketsView==='function'){const _psvTickets=ticketsView;ticketsView=async function(){await _psvTickets();psPermissionSweep();};}
if(typeof openChat==='function'){const _psvOpenChat=openChat;openChat=async function(id){await _psvOpenChat(id);psPermissionSweep();};}
const psPermissionObserver=new MutationObserver(()=>{clearTimeout(window.__psPermTimer);window.__psPermTimer=setTimeout(psPermissionSweep,20)});
document.addEventListener('DOMContentLoaded',()=>{const app=document.getElementById('app');if(app)psPermissionObserver.observe(app,{childList:true,subtree:true});setTimeout(psPermissionSweep,50)});
'''
    marker='\n})();'
    if marker in js:
        head,tail=js.rsplit(marker,1)
        return head+'\n'+patch+marker+tail
    return js+'\n'+patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_permission_visibility():
    return _html()


@router.get('/dashboard.js')
def dashboard_permission_visibility_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
