from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_fullscreen_support_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-role-redesign'])
UI_VERSION = '2026.09.04-66'


def _html() -> str:
    html = base_html()
    for old in (
        '2026.09.04-65','2026.09.04-64','2026.09.04-63','2026.09.04-62','2026.09.04-61',
        '2026.09.04-60','2026.09.04-59','2026.09.04-58','2026.09.04-57','2026.09.04-56',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</style></head>', '''<style>
:root{--ps-bg:#06111f;--ps-panel:#0b1d31;--ps-panel2:#0f2843;--ps-line:#1c3b59;--ps-text:#eef6ff;--ps-muted:#8eacc8;--ps-blue:#2196ff;--ps-green:#18c788;--ps-red:#ff526d;--ps-purple:#8b5cf6;--ps-amber:#f2b940;--ps-shadow:0 18px 50px rgba(0,0,0,.28)}
html,body{min-height:100%;background:linear-gradient(135deg,#06111f,#07192b 50%,#05101b)!important;color:var(--ps-text)!important}
body:before,body:after{opacity:.28}
.w{max-width:none!important;margin:0!important;padding:0!important}
#login{max-width:460px;margin:8vh auto!important;background:linear-gradient(180deg,rgba(16,42,69,.96),rgba(8,25,42,.98))!important;border:1px solid var(--ps-line)!important;box-shadow:var(--ps-shadow)!important}
#app.phygital-role-shell{display:grid!important;grid-template-columns:238px minmax(0,1fr);min-height:100vh;align-items:stretch}
.ps-side{position:sticky;top:0;height:100vh;background:#071629;border-right:1px solid #0c2a45;padding:18px 14px;display:flex;flex-direction:column;z-index:20}
.ps-brand{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:750;margin:4px 8px 20px}.ps-logo{width:36px;height:36px;border-radius:11px;background:linear-gradient(145deg,#2ea7ff,#1458d8);display:grid;place-items:center;font-weight:900;box-shadow:0 8px 24px rgba(33,150,255,.25)}
.ps-side .nav{display:grid!important;gap:5px!important;background:transparent!important;border:0!important;padding:0!important;margin:0!important;box-shadow:none!important;backdrop-filter:none!important}
.ps-side .nav button{width:100%!important;text-align:left!important;margin:0!important;padding:11px 12px!important;border:1px solid transparent!important;background:transparent!important;color:#c7dcf1!important;border-radius:11px!important;box-shadow:none!important}
.ps-side .nav button:hover,.ps-side .nav button.ps-active{background:#0d3159!important;border-color:#17466e!important;color:#fff!important}
.ps-side-footer{margin-top:auto;border-top:1px solid #123553;padding:15px 8px 2px}.ps-role-chip{display:inline-flex;align-items:center;gap:7px;padding:6px 9px;border-radius:999px;background:#102d49;border:1px solid #235177;font-size:11px;color:#cfe6fa}.ps-role-chip.super{background:#31225d;border-color:#6c51b8;color:#efe8ff}.ps-scope{font-size:11px;color:var(--ps-muted);margin-top:8px;line-height:1.4}
.ps-main{min-width:0;padding:18px 22px 34px}.ps-topbar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:18px}.ps-search{max-width:540px;flex:1;background:#0a1c2f;border:1px solid #1a446b;border-radius:12px;padding:11px 14px;color:#dcecf8;outline:none}.ps-search:focus{border-color:#2f91e7;box-shadow:0 0 0 3px rgba(33,150,255,.12)}.ps-profile{display:flex;align-items:center;gap:10px;color:#c9ddf0;white-space:nowrap}.ps-avatar{width:38px;height:38px;border-radius:50%;background:linear-gradient(145deg,#469dff,#244bc8);display:grid;place-items:center;font-weight:800}.ps-role-title{font-size:12px;color:var(--ps-muted)}
.ps-hero{display:flex;justify-content:space-between;align-items:end;gap:14px;margin:8px 0 12px}.ps-hero h1{margin:0!important;font-size:28px!important}.ps-hero p{margin:5px 0 0;color:var(--ps-muted)}.ps-tagline{color:#9db7d1;font-size:13px;text-align:right}
#stats{display:grid!important;grid-template-columns:repeat(5,minmax(145px,1fr))!important;gap:12px!important;margin:0 0 12px!important}
#stats>.card{margin:0!important;padding:14px!important;min-height:92px;background:linear-gradient(180deg,rgba(16,42,69,.92),rgba(8,25,42,.97))!important;border:1px solid var(--ps-line)!important;border-radius:15px!important;box-shadow:var(--ps-shadow)!important;display:flex;flex-direction:column;justify-content:center}
#stats>.card b{font-size:26px!important}#stats>.card div{color:var(--ps-muted)!important;font-size:12px;margin-top:5px}
#content.card{background:linear-gradient(180deg,rgba(16,42,69,.88),rgba(8,25,42,.95))!important;border:1px solid var(--ps-line)!important;border-radius:15px!important;box-shadow:var(--ps-shadow)!important;padding:16px!important;margin:12px 0!important;min-height:320px}
#content .card{background:rgba(7,24,41,.72)!important;border:1px solid #173854!important;border-radius:13px!important;box-shadow:none!important}
#content .row{padding:12px 8px!important;border-bottom:1px solid #173854!important}#content .row:last-child{border-bottom:0!important}
#content table{width:100%;border-collapse:collapse}#content th{background:#0c2b47;color:#a9c5dc;text-align:left;padding:9px}#content td{padding:10px 9px;border-bottom:1px solid #173854}
#content input,#content select,#content textarea{background:#061827!important;border:1px solid #2b587f!important;color:#fff!important;border-radius:10px!important}
#content button,.ps-main button{border-radius:10px!important}.badge{background:#17314e!important;border:1px solid rgba(92,168,255,.18)}
.ticket-status-card{background:#0b2340!important;border-color:#214a6d!important}.chat{background:#071827!important}.bubble.in{background:#122d49!important}.bubble.out{background:#0d4939!important}
.ps-permission-banner{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 12px;padding:10px 12px;border:1px solid rgba(33,150,255,.22);border-radius:12px;background:rgba(10,39,66,.72);font-size:12px;color:#bdd5e8}.ps-permission-banner strong{color:#fff}.ps-permission-count{margin-left:auto;color:#7fd4ff}.ps-super-tools{color:#dfd3ff!important;border-color:#634aa2!important;background:#241b48!important}
.ps-hidden-by-search{display:none!important}
@media(max-width:1200px){#stats{grid-template-columns:repeat(3,minmax(145px,1fr))!important}}
@media(max-width:820px){#app.phygital-role-shell{grid-template-columns:1fr}.ps-side{position:relative;height:auto}.ps-side .nav{grid-template-columns:repeat(2,minmax(0,1fr))}.ps-side-footer{margin-top:12px}.ps-main{padding:14px}.ps-topbar{align-items:stretch;flex-direction:column}.ps-search{max-width:none}.ps-profile{justify-content:flex-end}#stats{grid-template-columns:repeat(2,minmax(130px,1fr))!important}.ps-hero{align-items:flex-start;flex-direction:column}.ps-tagline{text-align:left}}
@media(max-width:520px){.ps-side .nav{grid-template-columns:1fr}#stats{grid-template-columns:1fr!important}.ps-profile{justify-content:flex-start;white-space:normal}}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
const PS_NAV_META={
  navHelp:['⚑','Solicitudes'],navConv:['💬','Conversaciones'],navContacts:['👥','Contactos'],navCompanies:['🏬','Empresas'],
  navTickets:['🎫','Tickets'],navReports:['📊','Reportes'],navActivity:['◷','Actividad'],navAppearance:['🎨','Apariencia'],navUsers:['⚙','Usuarios y permisos']
};
function psAccessRoleLabel(){
  const u=USER_ACCESS||{},r=String(u.role||role()||'').toLowerCase();
  if(u.username==='admin'&&r==='admin')return 'Super Admin';
  if(r==='gerente')return 'Gerente';if(r==='operador')return 'Operador';if(r==='lector')return 'Lector';return r||'Usuario';
}
function psIsSuperAdmin(){const u=USER_ACCESS||{};return u.username==='admin'&&String(u.role||'').toLowerCase()==='admin'}
function psPermissionSummary(){
  const p=USER_ACCESS?.permissions||{};const enabled=Object.values(p).filter(Boolean).length,total=Object.keys(p).length;
  return {enabled,total};
}
function psDecorateNav(){
  Object.entries(PS_NAV_META).forEach(([id,meta])=>{const b=document.getElementById(id);if(!b)return;b.innerHTML=`<span>${meta[0]}</span> <span>${meta[1]}</span>`;});
  const logout=document.getElementById('logoutBtn');if(logout)logout.innerHTML='<span>⇥</span> <span>Salir</span>';
  document.querySelectorAll('.ps-side .nav button').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));b.classList.add('ps-active')}));
}
function psInstallShell(){
  const app=document.getElementById('app');if(!app||app.classList.contains('phygital-role-shell'))return;
  const nav=app.querySelector(':scope > .nav');if(!nav)return;
  app.classList.add('phygital-role-shell');
  const children=[...app.children].filter(x=>x!==nav);
  const side=document.createElement('aside');side.className='ps-side';side.innerHTML='<div class="ps-brand"><div class="ps-logo">P</div><div>Phygital Soporte<div class="ps-role-title">Centro de operación</div></div></div>';
  side.appendChild(nav);
  const footer=document.createElement('div');footer.className='ps-side-footer';footer.innerHTML='<div id="psRoleChip" class="ps-role-chip"></div><div id="psScope" class="ps-scope"></div>';side.appendChild(footer);
  const main=document.createElement('main');main.className='ps-main';
  const top=document.createElement('div');top.className='ps-topbar';top.innerHTML='<input id="psSearch" class="ps-search" placeholder="🔎 Buscar en la vista actual..."><div class="ps-profile"><span>🔔</span><span>❔</span><div class="ps-avatar">P</div><div><b id="psUsername">Usuario</b><div id="psRoleTitle" class="ps-role-title"></div></div></div>';
  const hero=document.createElement('div');hero.className='ps-hero';hero.innerHTML='<div><h1>Dashboard de soporte</h1><p>Monitorea solicitudes, conversaciones, tickets, tiendas y rendimiento operativo.</p></div><div class="ps-tagline">Tu red de soporte, más clara y rápida cada día</div>';
  const banner=document.createElement('div');banner.id='psPermissionBanner';banner.className='ps-permission-banner';
  main.appendChild(top);main.appendChild(hero);main.appendChild(banner);children.forEach(x=>main.appendChild(x));app.appendChild(side);app.appendChild(main);
  const originalTitle=main.querySelector(':scope > h1');if(originalTitle)originalTitle.classList.add('h');
  const versionNode=[...main.children].find(x=>x.classList?.contains('muted')&&String(x.textContent||'').includes('UI '));if(versionNode)versionNode.style.marginBottom='10px';
  psDecorateNav();psRefreshRoleChrome();psInstallSearch();
}
function psRefreshRoleChrome(){
  const label=psAccessRoleLabel(),superAdmin=psIsSuperAdmin(),summary=psPermissionSummary();
  const chip=document.getElementById('psRoleChip');if(chip){chip.className='ps-role-chip'+(superAdmin?' super':'');chip.textContent=(superAdmin?'★ ':'● ')+label;}
  const user=document.getElementById('psUsername');if(user)user.textContent=USER_ACCESS?.username||'Usuario';
  const title=document.getElementById('psRoleTitle');if(title)title.textContent=label;
  const scope=document.getElementById('psScope');if(scope){const ids=USER_ACCESS?.company_ids;scope.textContent=ids===null?'Acceso a todas las empresas':`${(ids||[]).length} empresa(s) asignada(s)`;}
  const banner=document.getElementById('psPermissionBanner');if(banner){banner.innerHTML=`<strong>${superAdmin?'Super Admin':'Permisos activos'}</strong><span>${superAdmin?'Acceso completo al sistema y herramientas administrativas.':'La interfaz se adapta a los permisos configurados para tu usuario.'}</span><span class="ps-permission-count">${summary.enabled}/${summary.total} permisos</span>`;}
  if(superAdmin)document.querySelectorAll('.ps-side .nav button').forEach(b=>{b.classList.remove('h');if(['navUsers','navAppearance','navActivity','navCompanies'].includes(b.id))b.classList.add('ps-super-tools')});
}
function psInstallSearch(){
  const input=document.getElementById('psSearch');if(!input||input.dataset.ready)return;input.dataset.ready='1';
  input.addEventListener('input',()=>{const q=input.value.trim().toLowerCase(),host=document.getElementById('content');if(!host)return;host.querySelectorAll('.row,tbody tr,.card[data-ticket-id],.ai-point').forEach(el=>{const hit=!q||String(el.textContent||'').toLowerCase().includes(q);el.classList.toggle('ps-hidden-by-search',!hit)});});
}
const _psApplyPermissionNavigation=applyPermissionNavigation;
applyPermissionNavigation=function(){_psApplyPermissionNavigation();if(psIsSuperAdmin())document.querySelectorAll('#app .nav button').forEach(b=>b.classList.remove('h'));psRefreshRoleChrome();};
const _psLoadMyAccess=loadMyAccess;
loadMyAccess=async function(){await _psLoadMyAccess();psRefreshRoleChrome();};
const _psShow=show;
show=async function(){await _psShow();psInstallShell();psRefreshRoleChrome();};
document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>{if(!document.getElementById('app')?.classList.contains('h'))psInstallShell()},0)});
'''
    marker='\n})();'
    if marker in js:
        head,tail=js.rsplit(marker,1)
        return head+'\n'+patch+marker+tail
    return js+'\n'+patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_role_redesign():
    return _html()


@router.get('/dashboard.js')
def dashboard_role_redesign_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
