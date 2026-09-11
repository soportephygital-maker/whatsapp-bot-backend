from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_training_interpretation_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-image-gallery'])
UI_VERSION = '2026.09.04-83'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-81', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-81', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="dashboardImageGallery83">
.case-photo-gallery{margin-top:14px;padding:13px;border:1px solid #275272;border-radius:13px;background:#081d31}.case-photo-gallery h3{margin:0 0 5px}.case-photo-gallery .muted{margin-bottom:10px}.case-photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}.case-photo-item{min-width:0;border:1px solid #244a68;border-radius:11px;overflow:hidden;background:#061522}.case-photo-item img{display:block;width:100%;height:132px;object-fit:cover;background:#030b12;cursor:pointer}.case-photo-meta{padding:7px 8px;font-size:11px;color:#a8bfd3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.case-photo-empty{padding:9px 0;color:#8eacc8}.case-photo-view-btn{width:auto!important;margin-left:6px!important}.case-photo-modal{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;padding:18px}.case-photo-modal img{max-width:96vw;max-height:92vh;object-fit:contain}.case-photo-modal button{position:absolute;top:14px;right:14px;width:auto!important;min-width:46px}.case-photo-loading{padding:12px;color:#8eacc8}@media(max-width:620px){.case-photo-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.case-photo-item img{height:115px}}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
const CASE_PHOTO_URLS=new Set();
async function casePhotoBlobUrl(ticketId,attachmentId){
  const r=await fetch(`/api/tickets/${ticketId}/adjuntos/${attachmentId}`,{headers:headers()});
  if(!r.ok)throw Error('No se pudo cargar la imagen');
  const url=URL.createObjectURL(await r.blob());CASE_PHOTO_URLS.add(url);return url;
}
function openCasePhoto(url){
  const modal=document.createElement('div');modal.className='case-photo-modal';modal.innerHTML=`<button type="button">✕ Cerrar</button><img alt="Evidencia fotográfica del ticket">`;
  modal.querySelector('img').src=url;const close=()=>modal.remove();modal.querySelector('button').onclick=close;modal.onclick=e=>{if(e.target===modal)close()};document.body.appendChild(modal);
}
async function renderCasePhotoGallery(ticketId,host,autoOpen=false){
  if(!host||!ticketId)return;
  let box=host.querySelector(`.case-photo-gallery[data-ticket-gallery="${ticketId}"]`);
  if(!box){box=document.createElement('div');box.className='case-photo-gallery';box.dataset.ticketGallery=String(ticketId);host.appendChild(box)}
  box.innerHTML='<div class="case-photo-loading">Cargando evidencias fotográficas...</div>';
  try{
    const rows=await api(`/api/tickets/${ticketId}/adjuntos`),photos=(rows||[]).filter(x=>String(x.content_type||'').toLowerCase().startsWith('image/'));
    box.innerHTML=`<h3>📷 Evidencias fotográficas</h3><div class="muted">${photos.length} foto(s) asociadas a este reporte. Las fotos se conservan en el expediente interno.</div><div class="case-photo-grid"></div>`;
    const grid=box.querySelector('.case-photo-grid');
    if(!photos.length){grid.innerHTML='<div class="case-photo-empty">Todavía no hay fotografías guardadas.</div>';return}
    for(const p of photos){
      const item=document.createElement('div');item.className='case-photo-item';item.innerHTML=`<div class="case-photo-loading">Cargando...</div><div class="case-photo-meta" title="${esc(p.filename||'imagen')}">${esc(p.filename||'imagen')}</div>`;grid.appendChild(item);
      try{const url=await casePhotoBlobUrl(ticketId,p.id);const loading=item.querySelector('.case-photo-loading');if(loading)loading.remove();const img=document.createElement('img');img.src=url;img.alt=p.filename||'Evidencia';img.onclick=()=>openCasePhoto(url);item.insertBefore(img,item.firstChild)}catch(_){const loading=item.querySelector('.case-photo-loading');if(loading)loading.textContent='No disponible'}
    }
  }catch(e){box.innerHTML=`<div class="danger">${esc(e.message)}</div>`}
}
async function ticketForConversationId(conversationId){
  try{const rows=await cachedApi('/api/tickets');return (rows||[]).find(x=>Number(x.conversation_id)===Number(conversationId))||null}catch(_){return null}
}
async function attachGalleryToOpenChat(conversationId){
  const ticket=await ticketForConversationId(conversationId),host=document.getElementById('content');if(ticket&&host)await renderCasePhotoGallery(ticket.id,host,true)
}
function wireTicketPhotoButtons(){
  document.querySelectorAll('[data-ticket-id]').forEach(row=>{
    if(row.dataset.photoButtonReady==='1')return;row.dataset.photoButtonReady='1';const toolbar=row.querySelector('.toolbar')||row;
    const btn=document.createElement('button');btn.type='button';btn.className='case-photo-view-btn';btn.textContent='📷 Ver fotos';btn.onclick=async()=>{let gallery=row.querySelector('.case-photo-gallery');if(gallery){gallery.remove();return}await renderCasePhotoGallery(Number(row.dataset.ticketId),row)};toolbar.appendChild(btn);
  });
}
const _galleryOpenChat=typeof openChat==='function'?openChat:null;if(_galleryOpenChat){openChat=async function(id){const out=await _galleryOpenChat(id);await attachGalleryToOpenChat(id);return out}}
const _galleryTickets=typeof ticketsView==='function'?ticketsView:null;if(_galleryTickets){ticketsView=async function(){const out=await _galleryTickets();wireTicketPhotoButtons();return out}}
const _galleryLiveRefresh=typeof liveRefresh==='function'?liveRefresh:null;if(_galleryLiveRefresh){liveRefresh=async function(){const out=await _galleryLiveRefresh();if(typeof LIVE_VIEW!=='undefined'&&LIVE_VIEW==='tickets')wireTicketPhotoButtons();return out}}
document.addEventListener('DOMContentLoaded',()=>setTimeout(wireTicketPhotoButtons,120));
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_image_gallery():
    return _html()


@router.get('/dashboard.js')
def dashboard_image_gallery_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
