from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..services import case_report_runtime_patch  # noqa: F401
from . import dashboard_image_gallery_patch, image_evidence_listo_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
router.include_router(image_evidence_listo_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-106'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in (
        '2026.09.04-83','2026.09.04-84','2026.09.04-85','2026.09.04-86','2026.09.04-87',
        '2026.09.04-88','2026.09.04-89','2026.09.04-90','2026.09.04-91','2026.09.04-92',
        '2026.09.04-93','2026.09.04-94','2026.09.04-95','2026.09.04-96','2026.09.04-97','2026.09.04-98','2026.09.04-99','2026.09.04-100','2026.09.04-101','2026.09.04-102','2026.09.04-103','2026.09.04-104','2026.09.04-105',
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
  const box=document.createElement('div');box.id='mobileSupportAccount97';box.className='card';box.style.marginBottom='14px';
  box.innerHTML=`<h3>Cuenta Soporte app móvil</h3><div class="muted">La cuenta Soporte se crea automáticamente como operador. Aquí puedes establecer o cambiar su contraseña.</div><div style="display:grid;grid-template-columns:minmax(160px,1fr) minmax(180px,1fr) auto;gap:8px;align-items:end;margin-top:10px"><label>Usuario<input value="Soporte" disabled></label><label>Contraseña<input id="mobileSupportPass97" type="password" placeholder="Nueva contraseña de Soporte"></label><button type="button" id="mobileSupportActivate97">Guardar contraseña</button></div><div id="mobileSupportStatus97" class="muted" style="margin-top:8px"></div>`;
  root.prepend(box);const button=box.querySelector('#mobileSupportActivate97');button.onclick=async()=>{const pass=box.querySelector('#mobileSupportPass97').value,status=box.querySelector('#mobileSupportStatus97');if(!pass){status.textContent='Escribe la contraseña que usará la app.';return}button.disabled=true;status.textContent='Guardando cuenta Soporte...';try{const response=await fetch('/api/auth/soporte/activar',{method:'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify({username:'Soporte',password:pass})});const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(data.detail||`HTTP ${response.status}`);box.querySelector('#mobileSupportPass97').value='';status.textContent='✅ Cuenta Soporte activa. Ya puedes iniciar sesión en la app.';if(typeof users==='function')setTimeout(()=>users(),300)}catch(e){status.textContent='❌ '+e.message}finally{button.disabled=false}};
}
const _users97=typeof users==='function'?users:null;if(_users97){users=async function(){const out=await _users97();setTimeout(injectMobileSupportAccount97,30);return out}}
const mobileSupportObserver97=new MutationObserver(()=>{clearTimeout(window.__support97Timer);window.__support97Timer=setTimeout(injectMobileSupportAccount97,40)});
document.addEventListener('DOMContentLoaded',()=>{const content=document.getElementById('content');if(content)mobileSupportObserver97.observe(content,{childList:true,subtree:true});setTimeout(injectMobileSupportAccount97,150)});

async function showChatPhotos99(conversationId){
  const content=document.getElementById('content');if(!content)return;
  const old=document.getElementById('chatPhotos99');if(old)old.remove();
  const ticket=await ticketForConversationId(conversationId);if(!ticket)return;
  let rows=[];try{rows=await api(`/api/tickets/${ticket.id}/adjuntos`)}catch(_){return}
  const photos=(rows||[]).filter(x=>String(x.content_type||'').toLowerCase().startsWith('image/'));if(!photos.length)return;
  const box=document.createElement('div');box.id='chatPhotos99';box.className='case-photo-gallery';box.innerHTML=`<h3>📷 Fotos recibidas en este chat</h3><div class="muted">${photos.length} imagen(es) asociadas al ticket.</div><div class="case-photo-grid"></div>`;
  const grid=box.querySelector('.case-photo-grid');
  for(const p of photos){const item=document.createElement('div');item.className='case-photo-item';item.innerHTML=`<div class="case-photo-loading">Cargando...</div><div class="case-photo-meta">${esc(p.filename||'imagen')}</div>`;grid.appendChild(item);try{const url=await casePhotoBlobUrl(ticket.id,p.id);item.querySelector('.case-photo-loading')?.remove();const img=document.createElement('img');img.src=url;img.alt=p.filename||'Evidencia';img.onclick=()=>openCasePhoto(url);item.insertBefore(img,item.firstChild)}catch(_){item.querySelector('.case-photo-loading').textContent='No disponible'}}
  const firstCard=content.querySelector('.card');if(firstCard)firstCard.insertAdjacentElement('afterend',box);else content.prepend(box);
}
const _openChat99=typeof openChat==='function'?openChat:null;if(_openChat99){openChat=async function(id){const out=await _openChat99(id);setTimeout(()=>showChatPhotos99(id),80);return out}}
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return HTMLResponse(_html(), headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})
