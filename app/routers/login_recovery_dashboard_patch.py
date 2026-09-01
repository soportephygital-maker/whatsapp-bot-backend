from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .report_download_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-login-recovery'])
UI_VERSION = '2026.08.31-43'


def _html() -> str:
    html = base_html()
    for old in (
        '2026.08.31-42',
        '2026.08.28-41',
        '2026.08.28-40',
        '2026.08.28-39',
        '2026.08.28-38',
        '2026.08.28-37',
        '2026.08.28-36',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
let USER_ACCESS={dashboard:true,permissions:{},company_ids:null};
function permissionAllowed(key){return USER_ACCESS?.permissions?.[key]===true}
function setNavVisible(id,visible){const el=document.getElementById(id);if(el)el.classList.toggle('h',!visible)}
function applyPermissionNavigation(){
    setNavVisible('navHelp',permissionAllowed('view_requests'));
    setNavVisible('navConv',permissionAllowed('view_conversations'));
    setNavVisible('navContacts',permissionAllowed('view_contacts'));
    setNavVisible('navCompanies',permissionAllowed('view_companies'));
    setNavVisible('navReports',permissionAllowed('view_reports'));
    setNavVisible('navActivity',permissionAllowed('view_activity'));
    setNavVisible('navAppearance',permissionAllowed('manage_appearance'));
    setNavVisible('navUsers',permissionAllowed('manage_users')||permissionAllowed('manage_user_permissions')||permissionAllowed('manage_user_companies'));
}
async function loadMyAccess(){
    try{USER_ACCESS=await api('/api/access-control/me');applyPermissionNavigation()}catch(_){applyPermissionNavigation()}
}
const _showPermissionAware=show;
show=async function(){await _showPermissionAware();await loadMyAccess()};
'''
    marker = '\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_login_recovery():
    return _html()


@router.get('/dashboard.js')
def dashboard_login_recovery_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})
