from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_permission_visibility_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-ai-neural'])
UI_VERSION = '2026.09.04-68'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-67', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-67', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</style></head>', '''<style>
.ps-ai-nav{background:linear-gradient(180deg,#3a210f,#211307)!important;border-color:#8d4b16!important;color:#ffd79a!important}.ps-ai-nav:hover,.ps-ai-nav.ps-active{background:linear-gradient(180deg,#5a3012,#321a09)!important;border-color:#e07823!important;box-shadow:0 0 22px rgba(255,122,24,.22)!important}
.ai-neural-shell{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.75fr);gap:14px}.ai-neural-card{background:radial-gradient(circle at 50% 46%,rgba(255,112,19,.12),transparent 34%),linear-gradient(180deg,#070b10,#030506)!important;border:1px solid #613416!important;box-shadow:inset 0 0 60px rgba(255,111,18,.04),0 15px 45px rgba(0,0,0,.28)!important;overflow:hidden}.ai-neural-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}.ai-neural-title{display:flex;align-items:center;gap:10px}.ai-core-icon{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle,#ffd57c 0 8%,#ff8a18 28%,#612107 58%,#080706 72%);box-shadow:0 0 26px rgba(255,116,20,.72);color:#1f0c00;font-weight:900}.ai-neural-stage{position:relative;min-height:535px;border:1px solid #3b2415;border-radius:14px;margin-top:12px;background:radial-gradient(circle at 50% 50%,rgba(255,112,17,.08),transparent 34%),repeating-radial-gradient(circle at 50% 50%,rgba(238,115,32,.06) 0 1px,transparent 1px 52px),#020405;overflow:hidden}.ai-neural-stage:before,.ai-neural-stage:after{content:"";position:absolute;inset:16px;border:1px solid rgba(255,119,28,.15);pointer-events:none}.ai-neural-stage:after{inset:42px;border-color:rgba(255,119,28,.08);transform:rotate(45deg)}#aiNeuralSvg{width:100%;height:535px;display:block}.ai-neuron-line{stroke:#d35e1b;stroke-width:1;opacity:.22}.ai-neuron-line.approved{opacity:.5;stroke:#ff8c24}.ai-neuron-line.pending{stroke:#ffbd4a;opacity:.32;stroke-dasharray:5 5}.ai-neuron-node{cursor:pointer;transition:.2s}.ai-neuron-node:hover{filter:brightness(1.35)}.ai-neuron-dot{stroke:#ffc46b;stroke-width:1.5}.ai-neuron-dot.approved{fill:#ff851d;filter:url(#aiGlow)}.ai-neuron-dot.pending{fill:#ffd166;filter:url(#aiGlowPending);animation:aiPulse 1.8s ease-in-out infinite}.ai-neuron-dot.rejected{fill:#6f2c1e;stroke:#a94b2d;opacity:.55}.ai-neuron-label{fill:#ffc26f;font-size:10px;font-family:ui-monospace,monospace;pointer-events:none}.ai-core-ring{fill:none;stroke:#ff7a1c;filter:url(#aiGlow);opacity:.65}.ai-core-ring.secondary{stroke:#b84210;opacity:.42;stroke-dasharray:8 10}.ai-core{fill:url(#aiCoreGradient);filter:url(#aiGlowStrong)}.ai-core-text{fill:#fff2d8;font-size:18px;font-weight:800;text-anchor:middle}.ai-core-score{fill:#ffbf61;font-size:12px;text-anchor:middle}@keyframes aiPulse{0%,100%{opacity:.62}50%{opacity:1}}
.ai-neural-stats{display:grid;grid-template-columns:repeat(4,minmax(100px,1fr));gap:9px;margin:12px 0}.ai-neural-stat{padding:10px 11px;border:1px solid #593218;border-radius:11px;background:linear-gradient(180deg,#211207,#0d0906)}.ai-neural-stat b{display:block;font-size:22px;color:#ffc36d}.ai-neural-stat span{font-size:11px;color:#bca993}.ai-neuron-detail{min-height:165px;border:1px solid #60401f;border-radius:12px;padding:12px;background:#100b07}.ai-neuron-detail h4{margin:0 0 8px;color:#ffd79c}.ai-neuron-detail .status{display:inline-flex;margin-bottom:8px}.ai-growth{height:8px;border-radius:999px;background:#26150a;overflow:hidden;border:1px solid #593217}.ai-growth>i{display:block;height:100%;background:linear-gradient(90deg,#a33c0b,#ff831e,#ffd16b);box-shadow:0 0 12px rgba(255,126,27,.55)}.ai-learning-list{max-height:380px;overflow:auto;margin-top:10px}.ai-learning-row{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:9px;align-items:center;padding:9px;border-bottom:1px solid #332013;cursor:pointer}.ai-learning-row:hover{background:#171008}.ai-learning-num{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#321a0b;border:1px solid #8a4718;color:#ffc16a;font-size:11px;font-weight:800}.ai-learning-row small{color:#a99583}.ai-chat-panel{margin-top:14px}.ai-chat-panel .ai-chat-log{background:#06111c;border-color:#29445a;max-height:300px}.ai-chat-panel textarea{min-height:92px}.ai-ai-badge{display:inline-flex;gap:6px;align-items:center;padding:5px 9px;border-radius:999px;background:#28160b;border:1px solid #774018;color:#ffc36d;font-size:11px}.ai-neural-empty{height:100%;display:grid;place-items:center;text-align:center;color:#bca78f;padding:40px}.ai-neural-note{font-size:11px;color:#978675;margin-top:8px;line-height:1.45}
@media(max-width:1100px){.ai-neural-shell{grid-template-columns:1fr}.ai-neural-stats{grid-template-columns:repeat(2,1fr)}}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
function aiNeuralPhase(point){
  if(point.status==='approved')return 'Consolidada';
  if(point.status==='pending')return 'En formación';
  return 'Descartada';
}
function aiNeuralGrowth(point){
  const c=Math.max(0,Math.min(100,Number(point.confidence||0)));
  if(point.status==='approved')return Math.max(70,c);
  if(point.status==='pending')return Math.max(12,Math.round(c*.72));
  return Math.min(20,Math.round(c*.2));
}
function installSuperAdminAiNav(){
  const nav=document.querySelector('.ps-side .nav');if(!nav)return;
  let btn=document.getElementById('navAINeural');
  if(!psIsSuperAdmin()){if(btn)btn.remove();return}
  if(btn)return;
  btn=document.createElement('button');btn.id='navAINeural';btn.className='ps-ai-nav';btn.innerHTML='<span>✦</span> <span>IA · Aprendizaje</span>';
  const users=document.getElementById('navUsers');if(users)nav.insertBefore(btn,users);else nav.appendChild(btn);
  btn.onclick=async()=>{document.querySelectorAll('.ps-side .nav button').forEach(x=>x.classList.remove('ps-active'));btn.classList.add('ps-active');await renderSuperAdminAiNeural();};
}
function aiNeuronColor(status){return status==='approved'?'approved':status==='pending'?'pending':'rejected'}
function aiNeuronPosition(index,total){
  const cx=430,cy=265,golden=2.399963229728653;
  const ratio=(index+1)/(Math.max(1,total));
  const radius=72+Math.sqrt(ratio)*180;
  const angle=index*golden-1.15;
  return {x:cx+Math.cos(angle)*radius,y:cy+Math.sin(angle)*radius};
}
function buildNeuralSvg(points,status){
  const defs=`<defs><filter id="aiGlow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter><filter id="aiGlowPending"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter><filter id="aiGlowStrong"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter><radialGradient id="aiCoreGradient"><stop offset="0" stop-color="#fff0b1"/><stop offset=".16" stop-color="#ffb129"/><stop offset=".48" stop-color="#ef6812"/><stop offset="1" stop-color="#4a1405"/></radialGradient></defs>`;
  if(!points.length)return defs+'<foreignObject x="80" y="80" width="700" height="360"><div xmlns="http://www.w3.org/1999/xhtml" class="ai-neural-empty"><div><b>Aún no hay neuronas de aprendizaje.</b><br/>Cuando se cierren casos y se generen puntos de aprendizaje, aparecerán aquí para que los revises.</div></div></foreignObject>';
  const pos=points.map((_,i)=>aiNeuronPosition(i,points.length));
  let lines='';
  points.forEach((p,i)=>{const q=pos[i],cls=aiNeuronColor(p.status);lines+=`<line class="ai-neuron-line ${cls}" x1="430" y1="265" x2="${q.x.toFixed(1)}" y2="${q.y.toFixed(1)}"/>`;if(i>0){const prev=pos[i-1];lines+=`<line class="ai-neuron-line ${cls}" x1="${prev.x.toFixed(1)}" y1="${prev.y.toFixed(1)}" x2="${q.x.toFixed(1)}" y2="${q.y.toFixed(1)}"/>`;}});
  let nodes='';
  points.forEach((p,i)=>{const q=pos[i],cls=aiNeuronColor(p.status),r=(5+Math.max(0,Math.min(100,Number(p.confidence||0)))/22).toFixed(1);nodes+=`<g class="ai-neuron-node" data-neuron-id="${p.id}"><circle class="ai-neuron-dot ${cls}" cx="${q.x.toFixed(1)}" cy="${q.y.toFixed(1)}" r="${r}"/><circle cx="${q.x.toFixed(1)}" cy="${q.y.toFixed(1)}" r="${Number(r)+7}" fill="none" stroke="#ff8121" opacity=".12"/><text class="ai-neuron-label" x="${(q.x+10).toFixed(1)}" y="${(q.y-8).toFixed(1)}">N${p.id}</text></g>`;});
  const score=Number(status.score||0);
  return defs+lines+`<circle class="ai-core-ring secondary" cx="430" cy="265" r="66"/><circle class="ai-core-ring" cx="430" cy="265" r="48"/><circle class="ai-core" cx="430" cy="265" r="33"/><text class="ai-core-text" x="430" y="260">IA</text><text class="ai-core-score" x="430" y="280">${score}%</text>`+nodes;
}
function showNeuronDetail(point){
  const box=document.getElementById('aiNeuronDetail');if(!box)return;
  if(!point){box.innerHTML='<div class="muted">Selecciona una neurona del mapa para revisar qué aprendió y cuánto ha madurado.</div>';return}
  const growth=aiNeuralGrowth(point),phase=aiNeuralPhase(point);
  box.innerHTML=`<h4>Neurona N${point.id} · ${esc(phase)}</h4><span class="badge status">${esc(point.status)}</span><div><b>Problema aprendido</b><div>${esc(point.problem||'Sin problema registrado')}</div></div><div style="margin-top:8px"><b>Respuesta / solución</b><div>${esc(point.solution||'Sin solución registrada')}</div></div><div style="margin-top:10px;display:flex;justify-content:space-between"><span>Desarrollo</span><b>${growth}%</b></div><div class="ai-growth"><i style="width:${growth}%"></i></div><div class="ai-neural-note">Confianza registrada: ${Number(point.confidence||0)}% · Ticket: ${point.ticket_id||'sin ticket'} · Empresa ID: ${point.company_id||'general'}</div>${point.status==='pending'?`<div class="toolbar" style="margin-top:10px"><button class="aiApproveSelected" data-id="${point.id}">Aprobar aprendizaje</button><button class="aiRejectSelected danger" data-id="${point.id}">Rechazar</button></div>`:''}`;
  const approve=box.querySelector('.aiApproveSelected'),reject=box.querySelector('.aiRejectSelected');
  if(approve)approve.onclick=()=>updateNeuralLearning(point.id,'approved');if(reject)reject.onclick=()=>updateNeuralLearning(point.id,'rejected');
}
async function updateNeuralLearning(id,status){
  try{await api('/api/admin-ai/learning/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});await renderSuperAdminAiNeural()}catch(x){err(x.message)}
}
async function renderSuperAdminAiNeural(){
  if(!psIsSuperAdmin())return;
  err('');
  const content=document.getElementById('content');if(!content)return;
  content.innerHTML='<div class="muted">Cargando mapa de aprendizaje...</div>';
  try{
    const [s,history,companies]=await Promise.all([api('/api/admin-ai/status'),api('/api/admin-ai/chat').catch(()=>[]),api('/api/empresas/listar').catch(()=>[])]);
    const points=s.recent_points||[];
    content.innerHTML=`<div class="ai-neural-head"><div class="ai-neural-title"><div class="ai-core-icon">✦</div><div><h2 style="margin:0">Núcleo de aprendizaje Phygital</h2><div class="muted">Cada nodo representa un punto de aprendizaje obtenido de casos reales y revisable por ti.</div></div></div><div class="ai-ai-badge">${s.configured?'● IA conectada':'○ Falta OPENAI_API_KEY'} · ${esc(s.model||'modelo no definido')}</div></div><div class="ai-neural-stats"><div class="ai-neural-stat"><b>${Number(s.score||0)}%</b><span>Nivel ${esc(s.level||'Inicial')}</span></div><div class="ai-neural-stat"><b>${Number(s.approved_points||0)}</b><span>Neuronas consolidadas</span></div><div class="ai-neural-stat"><b>${Number(s.pending_points||0)}</b><span>En formación</span></div><div class="ai-neural-stat"><b>${Number(s.companies_with_learning||0)}</b><span>Empresas aprendidas</span></div></div><div class="ai-neural-shell"><div class="card ai-neural-card"><div class="section-title"><div><h3>Mapa neuronal de aprendizaje</h3><div class="muted">Brillo intenso = aprobado · pulso ámbar = pendiente · tenue = rechazado</div></div><button id="aiRefreshMap">Actualizar mapa</button></div><div class="ai-neural-stage"><svg id="aiNeuralSvg" viewBox="0 0 860 535" preserveAspectRatio="xMidYMid meet">${buildNeuralSvg(points,s)}</svg></div><div class="ai-neural-note">Visualización operativa: cada “neurona” corresponde a un punto guardado en la base de conocimiento; no representa literalmente una neurona interna ni los pesos del modelo.</div></div><div><div id="aiNeuronDetail" class="ai-neuron-detail"><div class="muted">Selecciona una neurona para ver su desarrollo punto por punto.</div></div><div class="card" style="margin-top:12px"><div class="section-title"><h3>Desarrollo punto a punto</h3><span class="badge">${points.length} recientes</span></div><div class="ai-learning-list">${points.map(p=>`<div class="ai-learning-row" data-learning-row="${p.id}"><div class="ai-learning-num">N${p.id}</div><div><b>${esc((p.problem||'Sin problema').slice(0,85))}</b><small>${esc(aiNeuralPhase(p))} · confianza ${Number(p.confidence||0)}% · desarrollo ${aiNeuralGrowth(p)}%</small></div><span class="badge">${esc(p.status)}</span></div>`).join('')||'<div class="muted">Sin puntos de aprendizaje todavía.</div>'}</div></div></div></div><div class="card ai-chat-panel"><div class="section-title"><div><h3>Chat de entrenamiento con el administrador</h3><div class="muted">Aquí puedes decirle a la IA cómo debe responder, corregir criterios o pedirle qué información necesita.</div></div><select id="aiCompanyContext" style="width:auto;min-width:220px"><option value="">Contexto general</option>${companies.map(c=>`<option value="${c.id}">${esc(c.nombre||c.name||c.empresa_id)}</option>`).join('')}</select></div><div id="aiNeuralChatLog" class="ai-chat-log">${history.map(m=>`<div class="ai-chat-msg ${m.role==='assistant'?'assistant':''}"><b>${m.role==='assistant'?'IA':'Tú'}</b><div>${esc(m.body)}</div></div>`).join('')||'<div class="muted">Todavía no hay conversación de entrenamiento.</div>'}</div><textarea id="aiNeuralPrompt" placeholder="Ejemplo: cuando una PDA marque Timeout, primero pregunta si realizaron Refresh. Si no sabes qué hacer, pregúntame antes de sugerir algo."></textarea><button id="aiNeuralSend">Enviar guía a la IA</button></div>`;
    document.getElementById('aiRefreshMap').onclick=renderSuperAdminAiNeural;
    document.querySelectorAll('.ai-neuron-node').forEach(node=>node.addEventListener('click',()=>showNeuronDetail(points.find(p=>String(p.id)===String(node.dataset.neuronId)))));
    document.querySelectorAll('[data-learning-row]').forEach(row=>row.onclick=()=>showNeuronDetail(points.find(p=>String(p.id)===String(row.dataset.learningRow))));
    document.getElementById('aiNeuralSend').onclick=async()=>{const prompt=document.getElementById('aiNeuralPrompt'),message=prompt.value.trim();if(!message)return;const companyId=Number(document.getElementById('aiCompanyContext').value)||null;try{const r=await api('/api/admin-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,company_id:companyId})});const log=document.getElementById('aiNeuralChatLog');log.insertAdjacentHTML('beforeend',`<div class="ai-chat-msg"><b>Tú</b><div>${esc(message)}</div></div><div class="ai-chat-msg assistant"><b>IA</b><div>${esc(r.reply)}</div></div>`);prompt.value='';log.scrollTop=log.scrollHeight}catch(x){err(x.message)}};
    psPermissionSweep();
  }catch(x){content.innerHTML='<div class="err">No se pudo cargar la IA de aprendizaje: '+esc(x.message)+'</div>'}
}
const _aiPsRefreshRoleChrome=psRefreshRoleChrome;
psRefreshRoleChrome=function(){_aiPsRefreshRoleChrome();installSuperAdminAiNav();};
const _aiPsInstallShell=psInstallShell;
psInstallShell=function(){_aiPsInstallShell();installSuperAdminAiNav();};
document.addEventListener('DOMContentLoaded',()=>setTimeout(installSuperAdminAiNav,100));
'''
    marker='\n})();'
    if marker in js:
        head,tail=js.rsplit(marker,1)
        return head+'\n'+patch+marker+tail
    return js+'\n'+patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_ai_neural():
    return _html()


@router.get('/dashboard.js')
def dashboard_ai_neural_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
