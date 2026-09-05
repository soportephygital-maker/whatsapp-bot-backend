from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_neural_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-ai-neural-entry'])
UI_VERSION = '2026.09.04-71'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-68', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-68', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
// The admin account may use a bootstrap username different from the literal
// "admin". Role=admin is the reliable UI signal; API endpoints still enforce
// primary-admin authorization server-side.
psIsSuperAdmin=function(){
  const u=USER_ACCESS||{};
  return String(u.role||'').toLowerCase()==='admin';
};
function forceAdminAiEntry(){
  if(!psIsSuperAdmin())return;
  installSuperAdminAiNav();
  const b=document.getElementById('navAINeural');
  if(b){b.classList.remove('h','ps-permission-hidden');b.style.display='';}
}
const _entryRefresh=psRefreshRoleChrome;
psRefreshRoleChrome=function(){_entryRefresh();forceAdminAiEntry();};
const _entryApplyPermissions=applyPermissionNavigation;
applyPermissionNavigation=function(){_entryApplyPermissions();forceAdminAiEntry();};

const _entryShow=show;
let _dashboardInitialShowDone=false;
show=async function(){
  if(!_dashboardInitialShowDone){
    _dashboardInitialShowDone=true;
    await _entryShow();
    setTimeout(forceAdminAiEntry,0);
    return;
  }
  try{
    if(typeof loadMyAccess==='function')await loadMyAccess();
    const s=await api('/api/stats');
    const stats=document.getElementById('stats');
    if(stats)stats.innerHTML=Object.entries(s).map(([k,v])=>`<div class="card"><b style="font-size:24px">${esc(v)}</b><div>${esc(k)}</div></div>`).join('');
    if(typeof loadCompanyContext==='function')await loadCompanyContext();
    if(typeof psRefreshRoleChrome==='function')psRefreshRoleChrome();
    setTimeout(forceAdminAiEntry,0);
  }catch(x){err(x.message)}
};

function rememberDashboardView(name){try{sessionStorage.setItem('phygital_dashboard_view_v1',name||'help')}catch(_){}}
const _entryHelp=help;help=async function(){rememberDashboardView('help');return _entryHelp()};
const _entryConv=conv;conv=async function(...args){rememberDashboardView('conv');return _entryConv(...args)};
const _entryCompanies=companies;companies=async function(...args){rememberDashboardView('companies');return _entryCompanies(...args)};
if(typeof ticketsView==='function'){const _entryTickets=ticketsView;ticketsView=async function(...args){rememberDashboardView('tickets');return _entryTickets(...args)}}
if(typeof reportsView==='function'){const _entryReports=reportsView;reportsView=async function(...args){rememberDashboardView('reports');return _entryReports(...args)}}
if(typeof users==='function'){const _entryUsers=users;users=async function(...args){rememberDashboardView('users');return _entryUsers(...args)}}
if(typeof activity==='function'){const _entryActivity=activity;activity=async function(...args){rememberDashboardView('activity');return _entryActivity(...args)}}
const _entryRenderAi=renderSuperAdminAiNeural;
renderSuperAdminAiNeural=async function(...args){
  rememberDashboardView('ai');
  const out=await _entryRenderAi(...args);
  try{
    const s=await api('/api/admin-ai/status');
    const badge=document.querySelector('.ai-ai-badge');
    if(badge){
      const labels={openai:'OpenAI',ollama:'Modelo local',retrieval:'Memoria local'};
      const provider=labels[s.provider]||s.provider||'IA local';
      badge.textContent=`● ${provider} · ${s.model||'sin modelo'}`;
    }
  }catch(_){}
  return out;
};

let _aiEntryAttempts=0;
const _aiEntryTimer=setInterval(()=>{forceAdminAiEntry();_aiEntryAttempts+=1;if(document.getElementById('navAINeural')||_aiEntryAttempts>20)clearInterval(_aiEntryTimer)},250);
document.addEventListener('DOMContentLoaded',()=>setTimeout(forceAdminAiEntry,50));
'''
    marker='\n})();'
    if marker in js:
        head,tail=js.rsplit(marker,1)
        return head+'\n'+patch+marker+tail
    return js+'\n'+patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_ai_neural_entry():
    return _html()


@router.get('/dashboard.js')
def dashboard_ai_neural_entry_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
