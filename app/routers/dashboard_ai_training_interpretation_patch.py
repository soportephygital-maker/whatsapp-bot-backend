from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import manager_ai_chat_patch
from .dashboard_ai_neural_entry_patch import _html as base_html, _js as base_js
from ..auth import get_current_user
from ..database import get_db
from ..models import Company, GlobalSetting, User
from ..services.user_access import can_access_company, require_user_permission

router = APIRouter(tags=['dashboard-ui-ai-training-interpretation'])
router.include_router(manager_ai_chat_patch.router)
UI_VERSION = '2026.09.04-81'

TICKET_DISPLAY_DEFAULTS = {
    'title_template': '{codigo}',
    'subtitle_template': '{empresa} · {tienda}',
    'show_status': True,
    'show_tracking': True,
    'compact': False,
}


class TicketDisplayConfig(BaseModel):
    title_template: str = Field(default='{codigo}', min_length=1, max_length=160)
    subtitle_template: str = Field(default='{empresa} · {tienda}', max_length=200)
    show_status: bool = True
    show_tracking: bool = True
    compact: bool = False


def _ticket_display_setting_key(company_id: int) -> str:
    return f'ticket_display:{company_id}'


def _ticket_display_company(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


def _ticket_display_value(company: Company, db: Session) -> dict:
    row = db.get(GlobalSetting, _ticket_display_setting_key(company.id))
    value = row.value if row and isinstance(row.value, dict) else {}
    return {**TICKET_DISPLAY_DEFAULTS, **{k: value[k] for k in TICKET_DISPLAY_DEFAULTS if k in value}}


@router.get('/api/empresas/{company_key}/ticket-display')
def get_ticket_display(company_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _ticket_display_company(company_key, db)
    if not can_access_company(db, user, company.id):
        raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
    return _ticket_display_value(company, db)


@router.put('/api/empresas/{company_key}/ticket-display')
def update_ticket_display(company_key: str, data: TicketDisplayConfig, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = _ticket_display_company(company_key, db)
    if not can_access_company(db, user, company.id):
        raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
    require_user_permission(db, user, 'manage_company_tree')
    key = _ticket_display_setting_key(company.id)
    row = db.get(GlobalSetting, key)
    value = data.model_dump()
    if row:
        row.value = value
        row.updated_by = user.username
    else:
        db.add(GlobalSetting(key=key, value=value, updated_by=user.username))
    db.commit()
    return {'status': 'ok', 'config': value}


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-73', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-73', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="dashboardAi81">
#navGeneral{font-weight:700!important}.dash-action{cursor:pointer;transition:transform .16s ease,filter .16s ease,box-shadow .16s ease}.dash-action:hover{transform:translateY(-2px);filter:brightness(1.08);box-shadow:0 10px 26px rgba(0,0,0,.18)}.dash-general-welcome{padding:16px 18px;margin-bottom:14px}.dash-general-welcome h2{margin:0 0 5px;font-size:24px}.dash-general-welcome p{margin:0;color:#8eacc8}.ai-node-editor{display:grid;gap:9px;margin-top:12px;padding:12px;border:1px solid #62431f;border-radius:12px;background:#0b0907}.ai-node-editor label{font-size:11px;color:#c9ad8d}.ai-node-editor textarea{min-height:88px}.ai-node-editor input[type=number]{max-width:130px}.ai-node-danger{background:#4a1920!important;border-color:#9d3e4c!important;color:#ffdce2!important}.ai-manager-approve{background:#0c5b42!important;border-color:#188966!important;color:#e0fff4!important}.ai-manager-chat{margin-top:14px}.ai-manager-chat-log{max-height:310px;overflow:auto;background:#06111c;border:1px solid #29445a;border-radius:12px;padding:10px}.ai-manager-chat textarea{min-height:92px;width:100%;margin-top:10px}.ai-manager-chat .toolbar{margin-top:8px}.ai-manager-chat .bubble{margin:7px 0;padding:9px 11px;border-radius:12px}.ai-manager-chat .bubble.user{background:#102842;border:1px solid #234864}.ai-manager-chat .bubble.ai{background:#0d2c27;border:1px solid #1b594d}.ai-manager-chat-label{font-size:12px;color:#9eb8ce;margin-bottom:8px}.ai-manager-scope{font-size:11px;color:#9eb8ce}.ai-manager-note{display:none!important}.ps-access-note,.ps-permission-banner{display:none!important}.ticket-display-editor{margin-top:16px;padding-top:14px;border-top:1px solid #214b6d}.ticket-display-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ticket-display-preview{margin-top:10px;padding:12px;border:1px dashed #3d6f94;border-radius:10px;background:#071a2d}.ticket-status-card.ticket-compact{padding:7px 9px!important;margin:5px 0!important}.ticket-status-card.ticket-compact .ticket-display-subtitle{font-size:11px!important}.ticket-display-help{font-size:11px;color:#8eacc8;margin-top:5px}@media(max-width:760px){.ticket-display-grid{grid-template-columns:1fr}}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
function currentDashboardRole(){return String(USER_ACCESS?.role||role()||'').toLowerCase()}
function canViewAiLearning(){return ['admin','gerente'].includes(currentDashboardRole())}
function isManagerAiViewer(){return currentDashboardRole()==='gerente'}
function isAdminAiViewer(){return currentDashboardRole()==='admin'}

const TICKET_DISPLAY_DEFAULTS={title_template:'{codigo}',subtitle_template:'{empresa} · {tienda}',show_status:true,show_tracking:true,compact:false};
const TICKET_DISPLAY_BY_COMPANY={};
function ticketDisplayConfigFor(t){return {...TICKET_DISPLAY_DEFAULTS,...(TICKET_DISPLAY_BY_COMPANY[String(t?.company_id)]||{})}}
function ticketTemplateText(template,t){
  const values={codigo:t?.code||'',empresa:t?.company_name||'',tienda:t?.store_name||'Tienda sin identificar',estado:t?.status==='closed'?'CERRADO':'ABIERTO',id:t?.id??''};
  return String(template||'').replace(/\{(codigo|empresa|tienda|estado|id)\}/g,(_,k)=>String(values[k]??''));
}
async function loadTicketDisplayConfigs(){
  try{const companies=await cachedApi('/api/empresas/listar');await Promise.all((companies||[]).map(async c=>{try{TICKET_DISPLAY_BY_COMPANY[String(c.id)]=await api('/api/empresas/'+encodeURIComponent(c.empresa_id)+'/ticket-display')}catch(_){TICKET_DISPLAY_BY_COMPANY[String(c.id)]={...TICKET_DISPLAY_DEFAULTS}}}))}catch(_){}
}
function ticketStateHtml(t){
  if(!t)return '<div class="muted">Ticket en preparación.</div>';
  const tr=t.tracking||{},closed=t.status==='closed',cfg=ticketDisplayConfigFor(t),title=ticketTemplateText(cfg.title_template,t)||t.code,subtitle=ticketTemplateText(cfg.subtitle_template,t);
  return `<div class="ticket-status-card ${cfg.compact?'ticket-compact':''}"><div class="section-title"><div><b class="ticket-code">${esc(title)}</b>${subtitle?`<div class="ticket-display-subtitle muted">${esc(subtitle)}</div>`:''}</div>${cfg.show_status?`<span class="badge ${closed?'ticket-status-closed':'ticket-status-open'}">${closed?'CERRADO':'ABIERTO'}</span>`:''}</div>${cfg.show_tracking?`<div><b>${esc(tr.status_label||(closed?'Cerrado':'En atención'))}</b></div><div>${esc(tr.message||'Tu caso está siendo atendido por nuestro equipo.')}</div>${tr.updated_at?`<div class="muted">Última actualización: ${esc(tr.updated_at)}</div>`:''}`:''}</div>`;
}

async function installTicketDisplayEditor(companyKey){
  const content=document.getElementById('content');if(!content||!companyKey||document.getElementById('ticketDisplayEditor'))return;
  let company=null;try{const list=await cachedApi('/api/empresas/listar');company=(list||[]).find(c=>c.empresa_id===companyKey)}catch(_){}
  if(!company)return;
  let cfg={...TICKET_DISPLAY_DEFAULTS};try{cfg={...cfg,...await api('/api/empresas/'+encodeURIComponent(companyKey)+'/ticket-display')}}catch(_){}
  TICKET_DISPLAY_BY_COMPANY[String(company.id)]=cfg;
  const heading=[...content.querySelectorAll('h2,h3,h4')].find(x=>String(x.textContent||'').trim().toLowerCase()==='configuración');
  const host=heading?.closest('.card')||content.querySelector('.card')||content;
  const box=document.createElement('div');box.id='ticketDisplayEditor';box.className='ticket-display-editor';
  const editable=typeof psHas==='function'?psHas('manage_company_tree'):['admin','gerente'].includes(currentDashboardRole());
  box.innerHTML=`<h3>Cómo aparecen los tickets</h3><div class="muted">Personaliza la presentación de tickets para ${esc(company.nombre||companyKey)}.</div><div class="ticket-display-grid"><label>Título del ticket<input id="ticketTitleTemplate" value="${esc(cfg.title_template)}" ${editable?'':'disabled'}></label><label>Línea secundaria<input id="ticketSubtitleTemplate" value="${esc(cfg.subtitle_template)}" ${editable?'':'disabled'}></label></div><div class="ticket-display-help">Variables disponibles: {codigo}, {empresa}, {tienda}, {estado}, {id}</div><div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px"><label><input id="ticketShowStatus" type="checkbox" style="width:auto" ${cfg.show_status?'checked':''} ${editable?'':'disabled'}> Mostrar estado</label><label><input id="ticketShowTracking" type="checkbox" style="width:auto" ${cfg.show_tracking?'checked':''} ${editable?'':'disabled'}> Mostrar seguimiento</label><label><input id="ticketCompact" type="checkbox" style="width:auto" ${cfg.compact?'checked':''} ${editable?'':'disabled'}> Vista compacta</label></div><div id="ticketDisplayPreview" class="ticket-display-preview"></div>${editable?'<button id="saveTicketDisplay" style="margin-top:10px">Guardar formato de tickets</button>':''}`;
  host.appendChild(box);
  const read=()=>({title_template:document.getElementById('ticketTitleTemplate').value.trim()||'{codigo}',subtitle_template:document.getElementById('ticketSubtitleTemplate').value.trim(),show_status:document.getElementById('ticketShowStatus').checked,show_tracking:document.getElementById('ticketShowTracking').checked,compact:document.getElementById('ticketCompact').checked});
  const preview=()=>{const x=read(),sample={id:123,code:'EDM-CPP-20260910-042-000123',company_name:company.nombre||companyKey,store_name:'Tienda 042',status:'open',tracking:{status_label:'En atención',message:'Tu caso está siendo atendido por nuestro equipo.'}},p=document.getElementById('ticketDisplayPreview');if(p){TICKET_DISPLAY_BY_COMPANY[String(company.id)]=x;p.innerHTML='<div class="muted" style="margin-bottom:6px">Vista previa</div>'+ticketStateHtml(sample)}};
  ['ticketTitleTemplate','ticketSubtitleTemplate','ticketShowStatus','ticketShowTracking','ticketCompact'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('input',preview)});preview();
  const save=document.getElementById('saveTicketDisplay');if(save)save.onclick=async()=>{try{const x=read();const r=await api('/api/empresas/'+encodeURIComponent(companyKey)+'/ticket-display',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(x)});TICKET_DISPLAY_BY_COMPANY[String(company.id)]={...TICKET_DISPLAY_DEFAULTS,...(r.config||x)};err('Formato de tickets guardado.')}catch(e){err(e.message)}};
}

function installGeneralNav(){
  const nav=document.querySelector('.ps-side .nav');if(!nav||document.getElementById('navGeneral'))return;
  const b=document.createElement('button');b.id='navGeneral';b.type='button';b.innerHTML='<span>🏠</span> <span>General</span>';b.onclick=()=>renderGeneralDashboard();nav.insertBefore(b,nav.firstChild);
}
function markDashboardNavActive(id){document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));const b=document.getElementById(id);if(b)b.classList.add('ps-active')}
async function renderGeneralDashboard(){
  if(typeof LIVE_VIEW!=='undefined')LIVE_VIEW='general';if(typeof LIVE_CHAT_ID!=='undefined')LIVE_CHAT_ID=null;try{sessionStorage.setItem('phygital_dashboard_view_v1','general')}catch(_){}err('');
  try{const s=await api('/api/stats');window.__dashStats=s||{};const stats=$('stats');if(stats&&typeof renderDashStats==='function')stats.innerHTML=renderDashStats(s)}catch(_){}
  const content=$('content');if(content){content.innerHTML='<div class="card dash-general-welcome"><h2>General</h2><p>Resumen de la operación, accesos directos y métricas del soporte.</p></div>';if(typeof decorateDashboardView==='function')decorateDashboardView()}
  markDashboardNavActive('navGeneral');window.scrollTo({top:0,behavior:'smooth'});
}

function hideSuperAdminTabOnly(){
  document.querySelectorAll('.ps-side .nav button,#app .nav button').forEach(btn=>{
    const txt=String(btn.textContent||'').trim().toLowerCase();
    if(txt==='super admin'||txt.includes('super admin'))btn.classList.add('ps-permission-hidden');
  });
}
function removeSuperAdminNotices(){
  const root=document.getElementById('app')||document.body;
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes=[];
  while(walker.nextNode())nodes.push(walker.currentNode);
  nodes.forEach(n=>{
    if(/super admin/i.test(String(n.nodeValue||''))){
      const p=n.parentElement;
      if(p&&(/solo el super admin|super admin puede|función exclusiva del super admin|acceso completo al sistema/i.test(String(p.textContent||''))))p.style.display='none';
    }
  });
}
function applyManagerFriendlyChrome(){
  hideSuperAdminTabOnly();removeSuperAdminNotices();
  const appearance=document.getElementById('navAppearance');if(appearance&&typeof psHas==='function')appearance.classList.toggle('ps-permission-hidden',!psHas('manage_appearance'));
}

installSuperAdminAiNav=function(){
  const nav=document.querySelector('.ps-side .nav');if(!nav)return;let btn=document.getElementById('navAINeural');
  if(!canViewAiLearning()){if(btn)btn.remove();return}
  if(btn){btn.classList.remove('h','ps-permission-hidden');btn.style.display='';return}
  btn=document.createElement('button');btn.id='navAINeural';btn.className='ps-ai-nav';btn.type='button';btn.innerHTML='<span>✦</span> <span>IA · Aprendizaje</span>';
  const users=document.getElementById('navUsers');if(users)nav.insertBefore(btn,users);else nav.appendChild(btn);
  btn.onclick=async()=>{document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));btn.classList.add('ps-active');await renderRoleAiNeural()};
}

function renderManagerNeuronDetail(point){
  const box=document.getElementById('aiNeuronDetail');if(!box)return;
  if(!point){box.innerHTML='<div class="muted">Selecciona una neurona para revisar el aprendizaje.</div>';return}
  const growth=typeof aiNeuralGrowth==='function'?aiNeuralGrowth(point):Number(point.confidence||0),phase=typeof aiNeuralPhase==='function'?aiNeuralPhase(point):point.status;
  box.innerHTML=`<h4>Neurona N${point.id} · ${esc(phase)}</h4><span class="badge status">${esc(point.status)}</span><div><b>Problema aprendido</b><div>${esc(point.problem||'Sin problema registrado')}</div></div><div style="margin-top:8px"><b>Respuesta / solución</b><div>${esc(point.solution||'Sin solución registrada')}</div></div><div style="margin-top:10px;display:flex;justify-content:space-between"><span>Desarrollo</span><b>${growth}%</b></div><div class="ai-growth"><i style="width:${growth}%"></i></div><div class="ai-neural-note">Confianza registrada: ${Number(point.confidence||0)}% · Ticket: ${point.ticket_id||'sin ticket'} · Empresa ID: ${point.company_id||'general'}</div>${point.status==='pending'?`<div class="toolbar" style="margin-top:10px"><button class="aiManagerApprove ai-manager-approve">Aprobar aprendizaje</button></div>`:''}`;
  const approve=box.querySelector('.aiManagerApprove');if(approve)approve.onclick=async()=>{try{await api('/api/admin-ai/learning/'+point.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'approved'})});await renderManagerAiNeural()}catch(x){err(x.message)}};
}

async function loadManagerAiChat(){
  try{const history=await api('/api/manager-ai/chat');const log=document.getElementById('managerAiChatLog');if(!log)return;log.innerHTML=(history||[]).map(m=>`<div class="bubble ${m.role==='admin'?'user':'ai'}"><b>${m.role==='admin'?'Tú':'IA'}</b><div>${esc(m.body||'')}</div></div>`).join('')||'<div class="muted">Todavía no hay mensajes de entrenamiento.</div>';log.scrollTop=log.scrollHeight}catch(x){err(x.message)}
}
function installManagerAiChat(){
  if(!isManagerAiViewer())return;const content=document.getElementById('content');if(!content||document.getElementById('managerAiChatPanel'))return;
  const panel=document.createElement('div');panel.id='managerAiChatPanel';panel.className='card ai-manager-chat';panel.innerHTML=`<div class="section-title"><div><h3 style="margin:0">Chat de entrenamiento</h3><div class="ai-manager-chat-label">Puedes enseñarle procedimientos, corregir criterios o pedirle que te haga preguntas cuando falte información.</div></div></div><div id="managerAiChatLog" class="ai-manager-chat-log"></div><textarea id="managerAiChatInput" placeholder="Ejemplo: cuando una etiqueta esté apagada, primero verifica si la tinta está manchada. Si falta información, pregúntame antes de guardar el aprendizaje."></textarea><div class="toolbar"><button id="managerAiChatSend">Enviar guía a la IA</button></div><div class="ai-manager-scope">El entrenamiento se aplica al contexto de empresa seleccionado.</div>`;content.appendChild(panel);
  const send=document.getElementById('managerAiChatSend');if(send)send.onclick=async()=>{const input=document.getElementById('managerAiChatInput'),message=(input?.value||'').trim();if(!message)return;let companyId=null;try{companyId=COMPANY_CONTEXT?.id||null}catch(_){}try{send.disabled=true;await api('/api/manager-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,company_id:companyId})});input.value='';await loadManagerAiChat()}catch(x){err(x.message)}finally{send.disabled=false}};loadManagerAiChat();
}

async function renderManagerAiNeural(){
  if(!isManagerAiViewer())return;if(typeof LIVE_VIEW!=='undefined')LIVE_VIEW='ai';if(typeof LIVE_CHAT_ID!=='undefined')LIVE_CHAT_ID=null;try{sessionStorage.setItem('phygital_dashboard_view_v1','ai')}catch(_){}err('');const content=document.getElementById('content');if(!content)return;content.innerHTML='<div class="muted">Cargando aprendizaje...</div>';
  try{const s=await api('/api/admin-ai/status'),points=s.recent_points||[];content.innerHTML=`<div class="ai-neural-head"><div class="ai-neural-title"><div class="ai-core-icon">✦</div><div><h2 style="margin:0">IA · Aprendizaje</h2><div class="muted">Visualiza cómo aprende el sistema y aprueba nuevos puntos de conocimiento.</div></div></div><div class="ai-ai-badge">● Aprendizaje activo</div></div><div class="ai-neural-stats"><div class="ai-neural-stat"><b>${Number(s.score||0)}%</b><span>Nivel ${esc(s.level||'Inicial')}</span></div><div class="ai-neural-stat"><b>${Number(s.approved_points||0)}</b><span>Consolidadas</span></div><div class="ai-neural-stat"><b>${Number(s.pending_points||0)}</b><span>Pendientes</span></div><div class="ai-neural-stat"><b>${Number(s.companies_with_learning||0)}</b><span>Empresas aprendidas</span></div></div><div class="ai-neural-shell"><div class="card ai-neural-card"><div class="section-title"><div><h3>Mapa neuronal de aprendizaje</h3><div class="muted">Brillo intenso = aprobado · pulso ámbar = pendiente · tenue = rechazado</div></div><button id="aiRefreshMap">Actualizar mapa</button></div><div class="ai-neural-stage"><svg id="aiNeuralSvg" viewBox="0 0 860 535">${buildNeuralSvg(points,s)}</svg></div></div><div><div class="ai-neuron-detail" id="aiNeuronDetail"><div class="muted">Selecciona una neurona para revisar el aprendizaje.</div></div><div class="card" style="margin-top:12px;padding:12px"><h3 style="margin-top:0">Puntos de aprendizaje</h3><div class="ai-learning-list">${points.map(p=>`<div class="ai-learning-row" data-learning-id="${p.id}"><div class="ai-learning-num">N${p.id}</div><div><b>${esc((p.problem||'').slice(0,95))}</b><small>${esc(p.status)} · confianza ${Number(p.confidence||0)}%</small></div>${p.status==='pending'?'<span class="badge">Revisar</span>':'<span class="badge">Ver</span>'}</div>`).join('')||'<div class="muted">Aún no hay puntos de aprendizaje visibles.</div>'}</div></div></div></div>`;window.__managerAiPoints=points;const selectPoint=id=>{const p=points.find(x=>String(x.id)===String(id));if(p)renderManagerNeuronDetail(p)};content.querySelectorAll('[data-neuron-id]').forEach(el=>el.addEventListener('click',()=>selectPoint(el.dataset.neuronId)));content.querySelectorAll('[data-learning-id]').forEach(el=>el.addEventListener('click',()=>selectPoint(el.dataset.learningId)));const refresh=document.getElementById('aiRefreshMap');if(refresh)refresh.onclick=renderManagerAiNeural;installManagerAiChat();markDashboardNavActive('navAINeural')}catch(x){content.innerHTML=`<div class="danger">${esc(x.message)}</div>`}
}

function renderEditableNeuronDetail(point){
  const box=document.getElementById('aiNeuronDetail');if(!box||!point)return;const growth=typeof aiNeuralGrowth==='function'?aiNeuralGrowth(point):Number(point.confidence||0),phase=typeof aiNeuralPhase==='function'?aiNeuralPhase(point):point.status;
  box.innerHTML=`<h4>Neurona N${point.id} · ${esc(phase)}</h4><span class="badge status">${esc(point.status)}</span><div><b>Problema aprendido</b><div>${esc(point.problem||'')}</div></div><div style="margin-top:8px"><b>Respuesta / solución</b><div>${esc(point.solution||'')}</div></div><div style="margin-top:10px;display:flex;justify-content:space-between"><span>Desarrollo</span><b>${growth}%</b></div><div class="ai-growth"><i style="width:${growth}%"></i></div><div class="toolbar" style="margin-top:10px"><button class="aiEditNode">Editar</button>${point.status!=='approved'?`<button class="aiApproveSelected">Aprobar</button>`:''}${point.status!=='rejected'?`<button class="aiRejectSelected danger">Rechazar</button>`:''}<button class="aiDeleteNode ai-node-danger">Eliminar nodo</button></div><div class="ai-node-editor" style="display:none"><label>Problema<textarea class="aiEditProblem">${esc(point.problem||'')}</textarea></label><label>Solución / procedimiento<textarea class="aiEditSolution">${esc(point.solution||'')}</textarea></label><label>Confianza<input class="aiEditConfidence" type="number" min="0" max="100" value="${Number(point.confidence||0)}"></label><div class="toolbar"><button class="aiSaveNode">Guardar cambios</button><button class="aiCancelEdit">Cancelar</button></div></div>`;
  const edit=box.querySelector('.aiEditNode'),editor=box.querySelector('.ai-node-editor'),cancel=box.querySelector('.aiCancelEdit'),save=box.querySelector('.aiSaveNode'),del=box.querySelector('.aiDeleteNode'),approve=box.querySelector('.aiApproveSelected'),reject=box.querySelector('.aiRejectSelected');if(edit)edit.onclick=()=>editor.style.display='grid';if(cancel)cancel.onclick=()=>editor.style.display='none';if(approve)approve.onclick=()=>updateNeuralLearning(point.id,'approved');if(reject)reject.onclick=()=>updateNeuralLearning(point.id,'rejected');if(save)save.onclick=async()=>{const problem=box.querySelector('.aiEditProblem').value.trim(),solution=box.querySelector('.aiEditSolution').value.trim(),confidence=Number(box.querySelector('.aiEditConfidence').value||0);if(!problem||!solution)return err('Problema y solución no pueden quedar vacíos.');try{await api('/api/admin-ai/learning/'+point.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:point.status,problem,solution,confidence})});await renderRoleAiNeural()}catch(x){err(x.message)}};if(del)del.onclick=async()=>{if(!confirm(`Eliminar definitivamente la neurona N${point.id}?`))return;try{await api('/api/admin-ai/learning/'+point.id,{method:'DELETE'});await renderRoleAiNeural()}catch(x){err(x.message)}};
}

const _baseRenderAi=renderSuperAdminAiNeural;
async function renderRoleAiNeural(){if(isManagerAiViewer())return renderManagerAiNeural();return _baseRenderAi()}
renderSuperAdminAiNeural=renderRoleAiNeural;
const _baseShowNeuronDetail=typeof showNeuronDetail==='function'?showNeuronDetail:null;
showNeuronDetail=function(point){if(isManagerAiViewer())return renderManagerNeuronDetail(point);if(point)return renderEditableNeuronDetail(point);if(_baseShowNeuronDetail)return _baseShowNeuronDetail(point)};

const _ticketBaseCompanyPanel=typeof companyPanel==='function'?companyPanel:null;
if(_ticketBaseCompanyPanel){companyPanel=async function(key){await _ticketBaseCompanyPanel(key);await installTicketDisplayEditor(key)}}
const _ticketBaseTicketsView=typeof ticketsView==='function'?ticketsView:null;
if(_ticketBaseTicketsView){ticketsView=async function(){await loadTicketDisplayConfigs();return _ticketBaseTicketsView()}}
const _ticketBaseConv=typeof conv==='function'?conv:null;
if(_ticketBaseConv){conv=async function(companyId=null){await loadTicketDisplayConfigs();return _ticketBaseConv(companyId)}}
const _ticketBaseOpenChat=typeof openChat==='function'?openChat:null;
if(_ticketBaseOpenChat){openChat=async function(id){await loadTicketDisplayConfigs();return _ticketBaseOpenChat(id)}}

function wireOverviewShortcuts(){
  const root=document.getElementById('dashOverview');if(!root)return;const cards=[...root.querySelectorAll('.dash-action')],actions=[{run:()=>help(),nav:'navHelp'},{run:()=>conv(),nav:'navConv'},{run:()=>typeof users==='function'?users():null,nav:'navUsers'},{run:()=>canViewAiLearning()?renderRoleAiNeural():null,nav:'navAINeural'}];cards.forEach((card,i)=>{const action=actions[i];if(!action||card.dataset.navReady==='1')return;if(i===3&&!canViewAiLearning()){card.style.display='none';return}card.dataset.navReady='1';card.tabIndex=0;card.setAttribute('role','button');card.onclick=async()=>{await action.run();markDashboardNavActive(action.nav);window.scrollTo({top:0,behavior:'smooth'})}})
}
function wireSidebarNavigation(){['navHelp','navConv','navCompanies','navTickets','navReports','navUsers','navActivity','navAppearance','navAINeural'].forEach(id=>{const b=document.getElementById(id);if(!b||b.dataset.nav81==='1')return;b.dataset.nav81='1';b.addEventListener('click',()=>setTimeout(()=>markDashboardNavActive(id),0))})}

const _generalDecorate=typeof decorateDashboardView==='function'?decorateDashboardView:null;if(_generalDecorate){decorateDashboardView=function(){_generalDecorate();installGeneralNav();installSuperAdminAiNav();wireSidebarNavigation();wireOverviewShortcuts();applyManagerFriendlyChrome()}}
const _generalRefresh=typeof psRefreshRoleChrome==='function'?psRefreshRoleChrome:null;if(_generalRefresh){psRefreshRoleChrome=function(){_generalRefresh();installGeneralNav();installSuperAdminAiNav();wireSidebarNavigation();applyManagerFriendlyChrome()}}
const _generalShow=show;show=async function(){const out=await _generalShow();installGeneralNav();installSuperAdminAiNav();wireSidebarNavigation();setTimeout(()=>{wireOverviewShortcuts();applyManagerFriendlyChrome()},0);return out};
const _generalApplyPermission=typeof applyPermissionNavigation==='function'?applyPermissionNavigation:null;if(_generalApplyPermission){applyPermissionNavigation=function(){_generalApplyPermission();applyManagerFriendlyChrome()}}
const managerUiObserver=new MutationObserver(()=>{clearTimeout(window.__managerUiTimer);window.__managerUiTimer=setTimeout(applyManagerFriendlyChrome,20)});
document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{installGeneralNav();installSuperAdminAiNav();wireSidebarNavigation();wireOverviewShortcuts();applyManagerFriendlyChrome();loadTicketDisplayConfigs();const app=document.getElementById('app');if(app)managerUiObserver.observe(app,{childList:true,subtree:true})},80));
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_ai_training_interpretation():
    return _html()


@router.get('/dashboard.js')
def dashboard_ai_training_interpretation_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
