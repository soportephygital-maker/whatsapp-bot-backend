from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from . import dashboard_image_gallery_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
router.include_router(dashboard_image_gallery_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-86'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in ('2026.09.04-83', '2026.09.04-84', '2026.09.04-85'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="superAdminEmailEditor86">
#navEmailRecipientsAdmin{display:none}.ps-super-email-panel{display:grid;gap:12px}.ps-super-email-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}.ps-super-email-row{display:grid;grid-template-columns:minmax(150px,1fr) minmax(210px,1.35fr) minmax(120px,.8fr) auto;gap:10px;align-items:center;padding:11px 12px;border:1px solid #275272;border-radius:12px;background:#081d31}.ps-super-email-state{font-size:12px}.ps-super-email-state.active{color:#69ddb0}.ps-super-email-state.paused{color:#ffd166}.ps-super-email-actions{display:flex;gap:7px;flex-wrap:wrap}.ps-super-email-row button{min-width:94px}.ps-super-email-summary{font-size:12px;color:#9eb8ce}.support-email-editor-toolbar{display:flex;justify-content:flex-end;gap:8px;margin:8px 0 10px}.support-email-editor-row{display:grid;grid-template-columns:minmax(160px,1fr) minmax(230px,1.4fr) auto;gap:8px;align-items:center;padding:8px 0;border-top:1px solid #21415b}.support-email-editor-form{display:grid;grid-template-columns:minmax(150px,1fr) minmax(220px,1.4fr) auto;gap:8px;margin:10px 0;padding:10px;border:1px solid #275272;border-radius:10px;background:#071a2d}.support-email-editor-form.h{display:none!important}.support-email-editor-status{font-size:11px}.support-email-editor-status.paused{color:#ffd166}.support-email-editor-status.active{color:#69ddb0}@media(max-width:800px){.ps-super-email-row,.support-email-editor-row,.support-email-editor-form{grid-template-columns:1fr}.ps-super-email-actions{width:100%}.ps-super-email-actions button{flex:1}}
</style></head>''')
    return html


def _js() -> str:
    js = dashboard_image_gallery_patch._js()
    patch = r'''
function isTrueSuperAdmin(){return typeof psIsSuperAdmin==='function'&&psIsSuperAdmin()}

function installSuperAdminEmailRecipientsNav(){
  const nav=document.querySelector('.ps-side .nav');if(!nav)return;
  let btn=document.getElementById('navEmailRecipientsAdmin');
  if(!isTrueSuperAdmin()){if(btn)btn.remove();return}
  if(!btn){
    btn=document.createElement('button');btn.id='navEmailRecipientsAdmin';btn.type='button';btn.className='ps-super-tools';btn.innerHTML='<span>✉</span> <span>Correos</span>';
    const users=document.getElementById('navUsers');if(users&&users.nextSibling)nav.insertBefore(btn,users.nextSibling);else nav.appendChild(btn);
    btn.onclick=()=>renderSuperAdminEmailRecipients();
  }
  btn.style.display='';btn.classList.remove('h','ps-permission-hidden');
}

async function renderSuperAdminEmailRecipients(){
  if(!isTrueSuperAdmin())return;
  if(typeof LIVE_VIEW!=='undefined')LIVE_VIEW='super_admin_email';if(typeof LIVE_CHAT_ID!=='undefined')LIVE_CHAT_ID=null;
  document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));const nav=document.getElementById('navEmailRecipientsAdmin');if(nav)nav.classList.add('ps-active');
  const content=document.getElementById('content');if(!content)return;content.innerHTML='<div class="muted">Cargando destinatarios de correo...</div>';
  try{
    const rows=await api('/api/super-admin/email-recipients');
    const companies=await cachedApi('/api/empresas/listar');
    const active=(rows||[]).filter(x=>!x.paused).length,paused=(rows||[]).filter(x=>x.paused).length;
    content.innerHTML=`<div class="ps-super-email-panel"><div class="ps-super-email-head"><div><h2 style="margin:0">Destinatarios de correo</h2><div class="muted">Agregar, editar, pausar o reanudar destinatarios de incidencias.</div></div><div><button id="superEmailAdd">＋ Añadir</button></div><div class="ps-super-email-summary">Activos: <b>${active}</b> · En pausa: <b>${paused}</b></div></div><div id="superEmailAddForm" class="support-email-editor-form h"><select id="superEmailCompany"><option value="">Selecciona empresa</option>${(companies||[]).map(c=>`<option value="${esc(c.empresa_id)}">${esc(c.nombre)}</option>`).join('')}</select><input id="superEmailName" placeholder="Nombre"><input id="superEmailAddress" type="email" placeholder="correo@empresa.com"><button id="superEmailSaveNew">Guardar</button></div><div id="superAdminEmailRows"></div></div>`;
    document.getElementById('superEmailAdd').onclick=()=>document.getElementById('superEmailAddForm').classList.toggle('h');
    document.getElementById('superEmailSaveNew').onclick=async()=>{const company_key=document.getElementById('superEmailCompany').value,name=document.getElementById('superEmailName').value.trim(),email=document.getElementById('superEmailAddress').value.trim();if(!company_key||!name||!email)return err('Selecciona empresa, escribe nombre y correo.');try{await api('/api/super-admin/email-recipients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_key,name,email})});await renderSuperAdminEmailRecipients()}catch(e){err(e.message)}};
    const host=document.getElementById('superAdminEmailRows');
    if(!rows?.length){host.innerHTML='<div class="muted">No hay destinatarios configurados.</div>';return}
    rows.forEach(r=>{
      const row=document.createElement('div');row.className='ps-super-email-row';
      row.innerHTML=`<div><b class="email-recipient-name">${esc(r.name||'Sin nombre')}</b><div class="muted">${esc(r.company_name||'')}</div></div><div class="email-recipient-address">${esc(r.email||'')}</div><div class="ps-super-email-state ${r.paused?'paused':'active'}">${r.paused?'⏸ En pausa':'● Recibiendo correos'}</div><div class="ps-super-email-actions"><button type="button" class="emailEdit">Editar</button><button type="button" class="emailPause">${r.paused?'Reanudar':'Pausar'}</button></div><div class="support-email-editor-form h" style="grid-column:1/-1"><input class="editName" value="${esc(r.name||'')}"><input class="editEmail" type="email" value="${esc(r.email||'')}"><button class="editSave">Guardar cambios</button></div>`;
      row.querySelector('.emailEdit').onclick=()=>row.querySelector('.support-email-editor-form').classList.toggle('h');
      row.querySelector('.editSave').onclick=async()=>{const name=row.querySelector('.editName').value.trim(),email=row.querySelector('.editEmail').value.trim();if(!name||!email)return err('Nombre y correo son obligatorios.');try{await api(`/api/super-admin/email-recipients/${r.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email})});await renderSuperAdminEmailRecipients()}catch(e){err(e.message)}};
      row.querySelector('.emailPause').onclick=async e=>{e.currentTarget.disabled=true;try{await api(`/api/super-admin/email-recipients/${r.id}/pause`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({paused:!r.paused})});await renderSuperAdminEmailRecipients()}catch(x){err(x.message);e.currentTarget.disabled=false}};
      host.appendChild(row);
    });
  }catch(e){content.innerHTML=`<div class="danger">${esc(e.message)}</div>`}
}

async function enhanceCompanySupportEmailSection(){
  if(!isTrueSuperAdmin())return;
  const content=document.getElementById('content');if(!content)return;
  const heading=[...content.querySelectorAll('h2,h3,h4')].find(el=>/correos del personal de soporte/i.test(String(el.textContent||'')));
  if(!heading)return;
  const section=heading.closest('.card')||heading.parentElement;if(!section||section.dataset.superEmailEditor==='1')return;section.dataset.superEmailEditor='1';
  let companyKey=null;try{companyKey=COMPANY_CONTEXT?.empresa_id||COMPANY_CONTEXT?.company_key||COMPANY_CONTEXT?.key||null}catch(_){}
  if(!companyKey){const title=String(document.querySelector('#content h2')?.textContent||'');const companies=await cachedApi('/api/empresas/listar');const found=(companies||[]).find(c=>title.toLowerCase().includes(String(c.nombre||'').toLowerCase()));companyKey=found?.empresa_id||null}
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

const _emailPauseShow=show;show=async function(){const out=await _emailPauseShow();installSuperAdminEmailRecipientsNav();setTimeout(enhanceCompanySupportEmailSection,30);return out};
const _emailPauseRefresh=typeof psRefreshRoleChrome==='function'?psRefreshRoleChrome:null;if(_emailPauseRefresh){psRefreshRoleChrome=function(){_emailPauseRefresh();installSuperAdminEmailRecipientsNav();setTimeout(enhanceCompanySupportEmailSection,30)}}
const _emailCompanyPanel=typeof companyPanel==='function'?companyPanel:null;if(_emailCompanyPanel){companyPanel=async function(key){const out=await _emailCompanyPanel(key);setTimeout(enhanceCompanySupportEmailSection,50);return out}}
const superEmailObserver=new MutationObserver(()=>{clearTimeout(window.__superEmailEditorTimer);window.__superEmailEditorTimer=setTimeout(enhanceCompanySupportEmailSection,60)});
document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{installSuperAdminEmailRecipientsNav();enhanceCompanySupportEmailSection();const content=document.getElementById('content');if(content)superEmailObserver.observe(content,{childList:true,subtree:true})},100));
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
