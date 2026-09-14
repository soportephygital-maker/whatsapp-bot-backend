from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..services import case_report_runtime_patch  # noqa: F401 - applies report contact sanitization at startup
from . import dashboard_image_gallery_patch, image_evidence_listo_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
# IMPORTANT: do not include dashboard_image_gallery_patch.router here.
# That router defines its own /dashboard and /dashboard.js (UI 87). If it is
# included before the routes below, FastAPI resolves the legacy UI first.
# We still reuse dashboard_image_gallery_patch._html()/_js() as the content base.
router.include_router(image_evidence_listo_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-96'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in (
        '2026.09.04-83', '2026.09.04-84', '2026.09.04-85',
        '2026.09.04-86', '2026.09.04-87', '2026.09.04-88',
        '2026.09.04-89', '2026.09.04-90', '2026.09.04-91',
        '2026.09.04-92', '2026.09.04-93', '2026.09.04-94',
        '2026.09.04-95',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = dashboard_image_gallery_patch._js()
    patch = r'''
function injectMobileSupportAccount96(){
  const root=document.getElementById('content');
  if(!root||root.querySelector('#mobileSupportAccount96'))return;
  const text=String(root.textContent||'').toLowerCase();
  if(!text.includes('usuario')&&!text.includes('usuarios'))return;
  const box=document.createElement('div');
  box.id='mobileSupportAccount96';
  box.className='card';
  box.style.marginBottom='14px';
  box.innerHTML=`
    <h3>Cuenta Soporte app móvil</h3>
    <div class="muted">Crea o reactiva la cuenta dedicada del teléfono como operador con permiso para responder conversaciones.</div>
    <div style="display:grid;grid-template-columns:minmax(160px,1fr) minmax(180px,1fr) auto;gap:8px;align-items:end;margin-top:10px">
      <label>Usuario<input id="mobileSupportUser96" value="Soporte" disabled></label>
      <label>Contraseña<input id="mobileSupportPass96" type="password" placeholder="Nueva contraseña de Soporte"></label>
      <button type="button" id="mobileSupportActivate96">Crear / activar Soporte</button>
    </div>
    <div id="mobileSupportStatus96" class="muted" style="margin-top:8px"></div>`;
  root.prepend(box);
  const button=box.querySelector('#mobileSupportActivate96');
  button.onclick=async()=>{
    const pass=box.querySelector('#mobileSupportPass96').value;
    const status=box.querySelector('#mobileSupportStatus96');
    if(!pass){status.textContent='Escribe la contraseña que usará la app.';return;}
    button.disabled=true;status.textContent='Activando cuenta Soporte...';
    try{
      const response=await fetch('/api/auth/soporte/activar',{
        method:'POST',
        headers:{...headers(),'Content-Type':'application/json'},
        body:JSON.stringify({username:'Soporte',password:pass})
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(data.detail||`HTTP ${response.status}`);
      box.querySelector('#mobileSupportPass96').value='';
      status.textContent='✅ Soporte quedó activa como operador con permiso para responder conversaciones.';
    }catch(e){status.textContent='❌ '+e.message}
    finally{button.disabled=false;}
  };
}
const _users96=typeof users==='function'?users:null;
if(_users96){users=async function(){const out=await _users96();setTimeout(injectMobileSupportAccount96,30);return out}}
const mobileSupportObserver96=new MutationObserver(()=>{clearTimeout(window.__support96Timer);window.__support96Timer=setTimeout(injectMobileSupportAccount96,40)});
document.addEventListener('DOMContentLoaded',()=>{const content=document.getElementById('content');if(content)mobileSupportObserver96.observe(content,{childList:true,subtree:true});setTimeout(injectMobileSupportAccount96,150)});
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return HTMLResponse(
        _html(),
        headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'},
    )


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(
        _js(),
        media_type='application/javascript',
        headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'},
    )
