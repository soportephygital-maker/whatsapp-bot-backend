from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_neural_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-ai-neural-entry'])
UI_VERSION = '2026.09.04-69'


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
show=async function(){await _entryShow();setTimeout(forceAdminAiEntry,0);};
let _aiEntryAttempts=0;
const _aiEntryTimer=setInterval(()=>{
  forceAdminAiEntry();
  _aiEntryAttempts+=1;
  if(document.getElementById('navAINeural')||_aiEntryAttempts>20)clearInterval(_aiEntryTimer);
},250);
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
