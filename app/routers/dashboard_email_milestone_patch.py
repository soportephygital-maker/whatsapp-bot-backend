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
UI_VERSION = '2026.09.04-98'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in (
        '2026.09.04-83', '2026.09.04-84', '2026.09.04-85',
        '2026.09.04-86', '2026.09.04-87', '2026.09.04-88',
        '2026.09.04-89', '2026.09.04-90', '2026.09.04-91',
        '2026.09.04-92', '2026.09.04-93', '2026.09.04-94',
        '2026.09.04-95', '2026.09.04-96', '2026.09.04-97',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = dashboard_image_gallery_patch._js()
    patch = r'''
function injectMobileSupportAccount97(){
  const root=document.getElementById('content');
  if(!root||root.querySelector('#mobileSupportAccount97'))return;
  const box=document.createElement('div');
  box.id='mobileSupportAccount97';
  box.className='card';
  box.style.marginBottom='14px';
  box.innerHTML=`
    <h3>Cuenta Soporte app móvil</h3>
    <div class="muted">La cuenta Soporte se crea automáticamente como operador. Aquí puedes establecer o cambiar su contraseña.</div>
    <div style="display:grid;grid-template-columns:minmax(160px,1fr) minmax(180px,1fr) auto;gap:8px;align-items:end;margin-top:10px">
      <label>Usuario<input value="Soporte" disabled></label>
      <label>Contraseña<input id="mobileSupportPass97" type="password" placeholder="Nueva contraseña de Soporte"></label>
      <button type="button" id="mobileSupportActivate97">Guardar contraseña</button>
    </div>
    <div id="mobileSupportStatus97" class="muted" style="margin-top:8px"></div>`;
  root.prepend(box);
  const button=box.querySelector('#mobileSupportActivate97');
  button.onclick=async()=>{
    const pass=box.querySelector('#mobileSupportPass97').value;
    const status=box.querySelector('#mobileSupportStatus97');
    if(!pass){status.textContent='Escribe la contraseña que usará la app.';return;}
    button.disabled=true;status.textContent='Guardando cuenta Soporte...';
    try{
      const response=await fetch('/api/auth/soporte/activar',{
        method:'POST',
        headers:{...headers(),'Content-Type':'application/json'},
        body:JSON.stringify({username:'Soporte',password:pass})
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(data.detail||`HTTP ${response.status}`);
      box.querySelector('#mobileSupportPass97').value='';
      status.textContent='✅ Cuenta Soporte activa. Ya puedes iniciar sesión en la app.';
      if(typeof users==='function')setTimeout(()=>users(),300);
    }catch(e){status.textContent='❌ '+e.message}
    finally{button.disabled=false;}
  };
}
const _users97=typeof users==='function'?users:null;
if(_users97){users=async function(){const out=await _users97();setTimeout(injectMobileSupportAccount97,30);return out}}
const mobileSupportObserver97=new MutationObserver(()=>{clearTimeout(window.__support97Timer);window.__support97Timer=setTimeout(injectMobileSupportAccount97,40)});
document.addEventListener('DOMContentLoaded',()=>{const content=document.getElementById('content');if(content)mobileSupportObserver97.observe(content,{childList:true,subtree:true});setTimeout(injectMobileSupportAccount97,150)});
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
