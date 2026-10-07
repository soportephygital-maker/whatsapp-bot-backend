from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_training_interpretation_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-image-gallery'])
UI_VERSION = '2026.09.04-87'


def _html() -> str:
    html = base_html()
    for old in ('2026.09.04-81', '2026.09.04-83', '2026.09.04-84', '2026.09.04-85', '2026.09.04-86'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="dashboardImageGallery87">
.case-photo-gallery{margin-top:14px;padding:13px;border:1px solid #275272;border-radius:13px;background:#081d31}.case-photo-gallery h3{margin:0 0 5px}.case-photo-gallery .muted{margin-bottom:10px}.case-photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}.case-photo-item{min-width:0;border:1px solid #244a68;border-radius:11px;overflow:hidden;background:#061522}.case-photo-item img{display:block;width:100%;height:132px;object-fit:cover;background:#030b12;cursor:pointer}.case-photo-meta{padding:7px 8px;font-size:11px;color:#a8bfd3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.case-photo-empty{padding:9px 0;color:#8eacc8}.case-photo-view-btn{width:auto!important;margin-left:6px!important}.case-photo-modal{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;padding:18px}.case-photo-modal img{max-width:96vw;max-height:92vh;object-fit:contain}.case-photo-modal button{position:absolute;top:14px;right:14px;width:auto!important;min-width:46px}.case-photo-loading{padding:12px;color:#8eacc8}
.support-email-editor-toolbar{display:flex;justify-content:flex-end;gap:8px;margin:8px 0 10px}.support-email-editor-row{display:grid;grid-template-columns:minmax(160px,1fr) minmax(230px,1.4fr) auto;gap:8px;align-items:center;padding:8px 0;border-top:1px solid #21415b}.support-email-editor-form{display:grid;grid-template-columns:minmax(150px,1fr) minmax(220px,1.4fr) auto;gap:8px;margin:10px 0;padding:10px;border:1px solid #275272;border-radius:10px;background:#071a2d}.support-email-editor-form.h{display:none!important}.support-email-editor-status{font-size:11px}.support-email-editor-status.paused{color:#ffd166}.support-email-editor-status.active{color:#69ddb0}.ps-super-email-actions{display:flex;gap:7px;flex-wrap:wrap}
@media(max-width:800px){.support-email-editor-row,.support-email-editor-form{grid-template-columns:1fr}.ps-super-email-actions{width:100%}.ps-super-email-actions button{flex:1}}@media(max-width:620px){.case-photo-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.case-photo-item img{height:115px}}
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
async function renderCasePhotoGallery(ticketId,host){
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
async function attachGalleryToOpenChat(conversationId){const ticket=await ticketForConversationId(conversationId),host=document.getElementById('content');if(ticket&&host)await renderCasePhotoGallery(ticket.id,host)}
function wireTicketPhotoButtons(){document.querySelectorAll('[data-ticket-id]').forEach(row=>{if(row.dataset.photoButtonReady==='1')return;row.dataset.photoButtonReady='1';const toolbar=row.querySelector('.toolbar')||row;const btn=document.createElement('button');btn.type='button';btn.className='case-photo-view-btn';btn.textContent='📷 Ver fotos';btn.onclick=async()=>{const gallery=row.querySelector('.case-photo-gallery');if(gallery){gallery.remove();return}await renderCasePhotoGallery(Number(row.dataset.ticketId),row)};toolbar.appendChild(btn)})}

function isTrueSuperAdmin87(){return typeof psIsSuperAdmin==='function'&&psIsSuperAdmin()}
async function enhanceCompanySupportEmailSection87(){
  if(!isTrueSuperAdmin87())return;
  const content=document.getElementById('content');if(!content)return;
  const heading=[...content.querySelectorAll('h2,h3,h4')].find(el=>/correos del personal de soporte/i.test(String(el.textContent||'')));
  if(!heading)return;
  const section=heading.closest('.card')||heading.parentElement;if(!section||section.dataset.superEmailEditor87==='1')return;section.dataset.superEmailEditor87='1';
  let companyKey=null;try{companyKey=COMPANY_CONTEXT?.empresa_id||COMPANY_CONTEXT?.company_key||COMPANY_CONTEXT?.key||null}catch(_){}
  if(!companyKey){const companies=await cachedApi('/api/empresas/listar');const sectionText=String(content.textContent||'').toLowerCase();const found=(companies||[]).find(c=>sectionText.includes(String(c.nombre||'').toLowerCase()));companyKey=found?.empresa_id||null}
  if(!companyKey)return;
  const toolbar=document.createElement('div');toolbar.className='support-email-editor-toolbar';toolbar.innerHTML='<button type="button" class="supportEmailEditMode">✏️ Editar</button><button type="button" class="supportEmailAdd h">＋ Añadir</button>';heading.parentElement?.insertBefore(toolbar,heading.nextSibling);
  const editBtn=toolbar.querySelector('.supportEmailEditMode'),addBtn=toolbar.querySelector('.supportEmailAdd');let editMode=false;
  const render=async()=>{
    section.querySelectorAll('.support-email-inline-editor').forEach(x=>x.remove());
    if(!editMode)return;
    const rows=(await api('/api/super-admin/email-recipients')).filter(r=>r.company_key===companyKey);
    const holder=document.createElement('div');holder.className='support-email-inline-editor';
    const form=document.createElement('div');form.className='support-email-editor-form h supportEmailNewForm';form.innerHTML='<input class="newName" placeholder="Nombre"><input class="newEmail" type="email" placeholder="correo@empresa.com"><button class="newSave">Guardar</button>';holder.appendChild(form);
    rows.forEach(r=>{const line=document.createElement('div');line.className='support-email-editor-row';line.innerHTML=`<div><input class="rowName" value="${esc(r.name||'')}"><div class="support-email-editor-status ${r.paused?'paused':'active'}">${r.paused?'⏸ En pausa':'● Activo'}</div></div><input class="rowEmail" type="email" value="${esc(r.email||'')}"><div class="ps-super-email-actions"><button class="rowSave">Guardar</button><button class="rowPause">${r.paused?'Reanudar':'Pausar'}</button></div>`;line.querySelector('.rowSave').onclick=async()=>{try{await api(`/api/super-admin/email-recipients/${r.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:line.querySelector('.rowName').value.trim(),email:line.querySelector('.rowEmail').value.trim()})});await render()}catch(e){err(e.message)}};line.querySelector('.rowPause').onclick=async()=>{try{await api(`/api/super-admin/email-recipients/${r.id}/pause`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({paused:!r.paused})});await render()}catch(e){err(e.message)}};holder.appendChild(line)});
    section.appendChild(holder);
    addBtn.onclick=()=>form.classList.toggle('h');form.querySelector('.newSave').onclick=async()=>{const name=form.querySelector('.newName').value.trim(),email=form.querySelector('.newEmail').value.trim();if(!name||!email)return err('Nombre y correo son obligatorios.');try{await api('/api/super-admin/email-recipients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_key:companyKey,name,email})});await render()}catch(e){err(e.message)}};
  };
  editBtn.onclick=async()=>{editMode=!editMode;editBtn.textContent=editMode?'✕ Terminar edición':'✏️ Editar';addBtn.classList.toggle('h',!editMode);await render()};
}

const _galleryOpenChat=typeof openChat==='function'?openChat:null;if(_galleryOpenChat){openChat=async function(id){const out=await _galleryOpenChat(id);await attachGalleryToOpenChat(id);return out}}
const _galleryTickets=typeof ticketsView==='function'?ticketsView:null;if(_galleryTickets){ticketsView=async function(){const out=await _galleryTickets();wireTicketPhotoButtons();return out}}
const _galleryCompanyPanel=typeof companyPanel==='function'?companyPanel:null;if(_galleryCompanyPanel){companyPanel=async function(key){const out=await _galleryCompanyPanel(key);setTimeout(enhanceCompanySupportEmailSection87,40);return out}}
const _galleryShow=show;show=async function(){const out=await _galleryShow();setTimeout(()=>{wireTicketPhotoButtons();enhanceCompanySupportEmailSection87()},40);return out}
const galleryObserver=new MutationObserver(()=>{clearTimeout(window.__gallery87Timer);window.__gallery87Timer=setTimeout(()=>{wireTicketPhotoButtons();enhanceCompanySupportEmailSection87()},50)});
document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{wireTicketPhotoButtons();enhanceCompanySupportEmailSection87();const content=document.getElementById('content');if(content)galleryObserver.observe(content,{childList:true,subtree:true})},120));
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
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})
