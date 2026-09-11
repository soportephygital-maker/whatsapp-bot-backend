from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from . import dashboard_image_gallery_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
router.include_router(dashboard_image_gallery_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-85'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    html = html.replace('UI 2026.09.04-83', f'UI {UI_VERSION}')
    html = html.replace('UI 2026.09.04-84', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-83', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-84', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="superAdminEmailPause85">
#navEmailRecipientsAdmin{display:none}.ps-super-email-panel{display:grid;gap:12px}.ps-super-email-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}.ps-super-email-row{display:grid;grid-template-columns:minmax(150px,1fr) minmax(210px,1.35fr) minmax(120px,.8fr) auto;gap:10px;align-items:center;padding:11px 12px;border:1px solid #275272;border-radius:12px;background:#081d31}.ps-super-email-state{font-size:12px}.ps-super-email-state.active{color:#69ddb0}.ps-super-email-state.paused{color:#ffd166}.ps-super-email-row button{min-width:112px}.ps-super-email-summary{font-size:12px;color:#9eb8ce}@media(max-width:800px){.ps-super-email-row{grid-template-columns:1fr}.ps-super-email-row button{width:100%}}
</style></head>''')
    return html


def _js() -> str:
    js = dashboard_image_gallery_patch._js()
    patch = r'''
function installSuperAdminEmailRecipientsNav(){
  const nav=document.querySelector('.ps-side .nav');if(!nav)return;
  let btn=document.getElementById('navEmailRecipientsAdmin');
  if(typeof psIsSuperAdmin!=='function'||!psIsSuperAdmin()){if(btn)btn.remove();return}
  if(!btn){
    btn=document.createElement('button');btn.id='navEmailRecipientsAdmin';btn.type='button';btn.className='ps-super-tools';btn.innerHTML='<span>✉</span> <span>Correos · Super Admin</span>';
    const users=document.getElementById('navUsers');if(users&&users.nextSibling)nav.insertBefore(btn,users.nextSibling);else nav.appendChild(btn);
    btn.onclick=()=>renderSuperAdminEmailRecipients();
  }
  btn.style.display='';btn.classList.remove('h','ps-permission-hidden');
}
async function renderSuperAdminEmailRecipients(){
  if(typeof psIsSuperAdmin!=='function'||!psIsSuperAdmin())return;
  if(typeof LIVE_VIEW!=='undefined')LIVE_VIEW='super_admin_email';if(typeof LIVE_CHAT_ID!=='undefined')LIVE_CHAT_ID=null;
  document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));const nav=document.getElementById('navEmailRecipientsAdmin');if(nav)nav.classList.add('ps-active');
  const content=document.getElementById('content');if(!content)return;content.innerHTML='<div class="muted">Cargando destinatarios de correo...</div>';
  try{
    const rows=await api('/api/super-admin/email-recipients');
    const active=(rows||[]).filter(x=>!x.paused).length,paused=(rows||[]).filter(x=>x.paused).length;
    content.innerHTML=`<div class="ps-super-email-panel"><div class="ps-super-email-head"><div><h2 style="margin:0">Destinatarios de correo</h2><div class="muted">Pausa temporalmente a una persona sin eliminar su configuración.</div></div><div class="ps-super-email-summary">Activos: <b>${active}</b> · En pausa: <b>${paused}</b></div></div><div id="superAdminEmailRows"></div></div>`;
    const host=document.getElementById('superAdminEmailRows');
    if(!rows?.length){host.innerHTML='<div class="muted">No hay destinatarios configurados.</div>';return}
    rows.forEach(r=>{
      const row=document.createElement('div');row.className='ps-super-email-row';
      row.innerHTML=`<div><b>${esc(r.name||'Sin nombre')}</b><div class="muted">${esc(r.company_name||'')}</div></div><div>${esc(r.email||'')}</div><div class="ps-super-email-state ${r.paused?'paused':'active'}">${r.paused?'⏸ En pausa':'● Recibiendo correos'}</div><button type="button">${r.paused?'Reanudar':'Pausar'}</button>`;
      const button=row.querySelector('button');button.onclick=async()=>{button.disabled=true;try{await api(`/api/super-admin/email-recipients/${r.id}/pause`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({paused:!r.paused})});await renderSuperAdminEmailRecipients()}catch(e){err(e.message);button.disabled=false}};host.appendChild(row);
    });
  }catch(e){content.innerHTML=`<div class="danger">${esc(e.message)}</div>`}
}
const _emailPauseShow=show;show=async function(){const out=await _emailPauseShow();installSuperAdminEmailRecipientsNav();return out};
const _emailPauseRefresh=typeof psRefreshRoleChrome==='function'?psRefreshRoleChrome:null;if(_emailPauseRefresh){psRefreshRoleChrome=function(){_emailPauseRefresh();installSuperAdminEmailRecipientsNav()}}
document.addEventListener('DOMContentLoaded',()=>setTimeout(installSuperAdminEmailRecipientsNav,100));
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return _html()


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
