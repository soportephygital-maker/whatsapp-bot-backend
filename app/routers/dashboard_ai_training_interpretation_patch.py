from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_neural_entry_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-ai-training-interpretation'])
UI_VERSION = '2026.09.04-76'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-73', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-73', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="dashboardGeneralNavigation76">
#navGeneral{font-weight:700!important}.dash-action{cursor:pointer;transition:transform .16s ease,filter .16s ease,box-shadow .16s ease}.dash-action:hover{transform:translateY(-2px);filter:brightness(1.08);box-shadow:0 10px 26px rgba(0,0,0,.18)}.dash-action:focus{outline:2px solid #53aaff;outline-offset:2px}.dash-general-welcome{padding:16px 18px;margin-bottom:14px}.dash-general-welcome h2{margin:0 0 5px;font-size:24px}.dash-general-welcome p{margin:0;color:#8eacc8}.ai-node-editor{display:grid;gap:9px;margin-top:12px;padding:12px;border:1px solid #62431f;border-radius:12px;background:#0b0907}.ai-node-editor label{font-size:11px;color:#c9ad8d}.ai-node-editor textarea{min-height:88px}.ai-node-editor input[type=number]{max-width:130px}.ai-node-danger{background:#4a1920!important;border-color:#9d3e4c!important;color:#ffdce2!important}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
function installGeneralNav(){
  const nav=document.querySelector('.ps-side .nav');
  if(!nav||document.getElementById('navGeneral'))return;
  const b=document.createElement('button');
  b.id='navGeneral';
  b.type='button';
  b.innerHTML='<span>🏠</span> <span>General</span>';
  b.onclick=()=>renderGeneralDashboard();
  nav.insertBefore(b,nav.firstChild);
}
function markDashboardNavActive(id){
  document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));
  const b=document.getElementById(id);if(b)b.classList.add('ps-active');
}
async function renderGeneralDashboard(){
  if(typeof LIVE_VIEW!=='undefined')LIVE_VIEW='general';
  if(typeof LIVE_CHAT_ID!=='undefined')LIVE_CHAT_ID=null;
  try{sessionStorage.setItem('phygital_dashboard_view_v1','general')}catch(_){}
  err('');
  try{
    const s=await api('/api/stats');
    window.__dashStats=s||{};
    const stats=$('stats');if(stats&&typeof renderDashStats==='function')stats.innerHTML=renderDashStats(s);
  }catch(_){}
  const content=$('content');
  if(content){
    content.innerHTML='<div class="card dash-general-welcome"><h2>General</h2><p>Resumen de la operación, accesos directos y métricas del soporte.</p></div>';
    if(typeof decorateDashboardView==='function')decorateDashboardView();
  }
  markDashboardNavActive('navGeneral');
  window.scrollTo({top:0,behavior:'smooth'});
}
function wireOverviewShortcuts(){
  const root=document.getElementById('dashOverview');if(!root)return;
  const cards=[...root.querySelectorAll('.dash-action')];
  const actions=[
    {run:()=>help(),nav:'navHelp',label:'Abrir Solicitudes'},
    {run:()=>conv(),nav:'navConv',label:'Abrir Conversaciones'},
    {run:()=>typeof users==='function'?users():null,nav:'navUsers',label:'Abrir Usuarios y permisos'},
    {run:()=>typeof renderSuperAdminAiNeural==='function'?renderSuperAdminAiNeural():null,nav:'navAINeural',label:'Abrir IA Aprendizaje'},
  ];
  cards.forEach((card,i)=>{
    const action=actions[i];if(!action||card.dataset.navReady==='1')return;
    card.dataset.navReady='1';card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label',action.label);
    const go=async()=>{await action.run();markDashboardNavActive(action.nav);window.scrollTo({top:0,behavior:'smooth'})};
    card.onclick=go;card.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}};
  });
}
function wireSidebarNavigation(){
  const map={navHelp:'help',navConv:'conv',navCompanies:'companies',navTickets:'ticketsView',navReports:'reportsView',navUsers:'users',navActivity:'activity',navAINeural:'renderSuperAdminAiNeural'};
  Object.entries(map).forEach(([id,fn])=>{
    const b=document.getElementById(id);if(!b||b.dataset.nav76==='1')return;b.dataset.nav76='1';
    b.addEventListener('click',()=>setTimeout(()=>markDashboardNavActive(id),0));
  });
}

function renderEditableNeuronDetail(point){
  const box=document.getElementById('aiNeuronDetail');if(!box||!point)return;
  const growth=typeof aiNeuralGrowth==='function'?aiNeuralGrowth(point):Number(point.confidence||0);
  const phase=typeof aiNeuralPhase==='function'?aiNeuralPhase(point):point.status;
  box.innerHTML=`<h4>Neurona N${point.id} · ${esc(phase)}</h4><span class="badge status">${esc(point.status)}</span><div><b>Problema aprendido</b><div>${esc(point.problem||'Sin problema registrado')}</div></div><div style="margin-top:8px"><b>Respuesta / solución</b><div>${esc(point.solution||'Sin solución registrada')}</div></div><div style="margin-top:10px;display:flex;justify-content:space-between"><span>Desarrollo</span><b>${growth}%</b></div><div class="ai-growth"><i style="width:${growth}%"></i></div><div class="ai-neural-note">Confianza registrada: ${Number(point.confidence||0)}% · Ticket: ${point.ticket_id||'sin ticket'} · Empresa ID: ${point.company_id||'general'}</div><div class="toolbar" style="margin-top:10px"><button class="aiEditNode">Editar</button>${point.status!=='approved'?`<button class="aiApproveSelected" data-id="${point.id}">Aprobar</button>`:''}${point.status!=='rejected'?`<button class="aiRejectSelected danger" data-id="${point.id}">Rechazar</button>`:''}<button class="aiDeleteNode ai-node-danger">Eliminar nodo</button></div><div class="ai-node-editor" style="display:none"><label>Problema<textarea class="aiEditProblem">${esc(point.problem||'')}</textarea></label><label>Solución / procedimiento<textarea class="aiEditSolution">${esc(point.solution||'')}</textarea></label><label>Confianza<input class="aiEditConfidence" type="number" min="0" max="100" value="${Number(point.confidence||0)}"></label><div class="toolbar"><button class="aiSaveNode">Guardar cambios</button><button class="aiCancelEdit">Cancelar</button></div></div>`;
  const edit=box.querySelector('.aiEditNode'),editor=box.querySelector('.ai-node-editor'),cancel=box.querySelector('.aiCancelEdit'),save=box.querySelector('.aiSaveNode'),del=box.querySelector('.aiDeleteNode'),approve=box.querySelector('.aiApproveSelected'),reject=box.querySelector('.aiRejectSelected');
  if(edit)edit.onclick=()=>editor.style.display='grid';
  if(cancel)cancel.onclick=()=>editor.style.display='none';
  if(approve)approve.onclick=()=>updateNeuralLearning(point.id,'approved');
  if(reject)reject.onclick=()=>updateNeuralLearning(point.id,'rejected');
  if(save)save.onclick=async()=>{
    const problem=box.querySelector('.aiEditProblem').value.trim();
    const solution=box.querySelector('.aiEditSolution').value.trim();
    const confidence=Number(box.querySelector('.aiEditConfidence').value||0);
    if(!problem||!solution)return err('Problema y solución no pueden quedar vacíos.');
    try{
      await api('/api/admin-ai/learning/'+point.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:point.status,problem,solution,confidence})});
      await renderSuperAdminAiNeural();
    }catch(x){err(x.message)}
  };
  if(del)del.onclick=async()=>{
    if(!confirm(`Eliminar definitivamente la neurona N${point.id}? Esta acción quita este conocimiento del aprendizaje.`))return;
    try{await api('/api/admin-ai/learning/'+point.id,{method:'DELETE'});await renderSuperAdminAiNeural()}catch(x){err(x.message)}
  };
}
const _nodeDetailOriginal=typeof showNeuronDetail==='function'?showNeuronDetail:null;
if(_nodeDetailOriginal){showNeuronDetail=function(point){if(!point)return _nodeDetailOriginal(point);renderEditableNeuronDetail(point)}}

const _generalDecorate=typeof decorateDashboardView==='function'?decorateDashboardView:null;
if(_generalDecorate){
  decorateDashboardView=function(){
    _generalDecorate();
    installGeneralNav();wireSidebarNavigation();wireOverviewShortcuts();
  };
}
const _generalRefresh=typeof psRefreshRoleChrome==='function'?psRefreshRoleChrome:null;
if(_generalRefresh){psRefreshRoleChrome=function(){_generalRefresh();installGeneralNav();wireSidebarNavigation()}}
const _generalShow=show;
show=async function(){const out=await _generalShow();installGeneralNav();wireSidebarNavigation();setTimeout(wireOverviewShortcuts,0);return out};
document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{installGeneralNav();wireSidebarNavigation();wireOverviewShortcuts()},80));
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
