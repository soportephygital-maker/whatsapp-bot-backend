from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .dashboard_ai_training_interpretation_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-manager-ai-chat'])
UI_VERSION = '2026.09.04-78'


def _html() -> str:
    html = base_html()
    html = html.replace('UI 2026.09.04-77', f'UI {UI_VERSION}')
    html = html.replace('/dashboard.js?v=2026.09.04-77', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</head>', '''<style id="managerAiChat78">
.ai-manager-note{display:none!important}.ai-manager-chat{margin-top:14px}.ai-manager-chat-log{max-height:300px;overflow:auto;background:#06111c;border:1px solid #29445a;border-radius:12px;padding:10px}.ai-manager-chat textarea{min-height:92px;width:100%;margin-top:10px}.ai-manager-chat .toolbar{margin-top:8px}.ai-manager-chat .bubble{margin:7px 0;padding:9px 11px;border-radius:12px}.ai-manager-chat .bubble.user{background:#102842;border:1px solid #234864}.ai-manager-chat .bubble.ai{background:#0d2c27;border:1px solid #1b594d}.ai-manager-chat-label{font-size:12px;color:#9eb8ce;margin-bottom:8px}.ai-manager-scope{font-size:11px;color:#9eb8ce}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
function managerAiCleanCopy(){
  if(!isManagerAiViewer())return;
  document.querySelectorAll('.ai-manager-note').forEach(el=>el.remove());
  document.querySelectorAll('#content').forEach(root=>{
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
    nodes.forEach(n=>{
      const t=String(n.nodeValue||'');
      if(/super\s*admin|administrador principal|solo lectura|no puedes editar|no puedes entrenar|no puedes rechazar|no puedes eliminar/i.test(t)){
        const parent=n.parentElement;
        if(parent)parent.remove();
      }
    });
  });
}
function renderManagerNeuronDetail(point){
  const box=document.getElementById('aiNeuronDetail');if(!box)return;
  if(!point){box.innerHTML='<div class="muted">Selecciona una neurona para revisar el aprendizaje.</div>';return}
  const growth=typeof aiNeuralGrowth==='function'?aiNeuralGrowth(point):Number(point.confidence||0);
  const phase=typeof aiNeuralPhase==='function'?aiNeuralPhase(point):point.status;
  box.innerHTML=`<h4>Neurona N${point.id} · ${esc(phase)}</h4><span class="badge status">${esc(point.status)}</span><div><b>Problema aprendido</b><div>${esc(point.problem||'Sin problema registrado')}</div></div><div style="margin-top:8px"><b>Respuesta / solución</b><div>${esc(point.solution||'Sin solución registrada')}</div></div><div style="margin-top:10px;display:flex;justify-content:space-between"><span>Desarrollo</span><b>${growth}%</b></div><div class="ai-growth"><i style="width:${growth}%"></i></div><div class="ai-neural-note">Confianza registrada: ${Number(point.confidence||0)}% · Ticket: ${point.ticket_id||'sin ticket'} · Empresa ID: ${point.company_id||'general'}</div>${point.status==='pending'?`<div class="toolbar" style="margin-top:10px"><button class="aiManagerApprove ai-manager-approve">Aprobar aprendizaje</button></div>`:''}`;
  const approve=box.querySelector('.aiManagerApprove');
  if(approve)approve.onclick=async()=>{
    try{await api('/api/admin-ai/learning/'+point.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'approved'})});await renderManagerAiNeural()}catch(x){err(x.message)}
  };
}
async function loadManagerAiChat(){
  try{
    const history=await api('/api/manager-ai/chat');
    const log=document.getElementById('managerAiChatLog');if(!log)return;
    log.innerHTML=(history||[]).map(m=>`<div class="bubble ${m.role==='admin'?'user':'ai'}"><b>${m.role==='admin'?'Tú':'IA'}</b><div>${esc(m.body||'')}</div></div>`).join('')||'<div class="muted">Todavía no hay mensajes de entrenamiento.</div>';
    log.scrollTop=log.scrollHeight;
  }catch(x){err(x.message)}
}
function installManagerAiChat(){
  if(!isManagerAiViewer())return;
  const content=document.getElementById('content');if(!content||document.getElementById('managerAiChatPanel'))return;
  const panel=document.createElement('div');panel.id='managerAiChatPanel';panel.className='card ai-manager-chat';
  panel.innerHTML=`<div class="section-title"><div><h3 style="margin:0">Chat de entrenamiento</h3><div class="ai-manager-chat-label">Puedes enseñarle procedimientos, corregir criterios o pedirle que te haga preguntas cuando falte información.</div></div></div><div id="managerAiChatLog" class="ai-manager-chat-log"></div><textarea id="managerAiChatInput" placeholder="Ejemplo: cuando una etiqueta esté apagada, primero verifica si la tinta está manchada. Si falta información, pregúntame antes de guardar el aprendizaje."></textarea><div class="toolbar"><button id="managerAiChatSend">Enviar guía a la IA</button></div><div class="ai-manager-scope">El entrenamiento se aplica al contexto de empresa seleccionado y a las empresas a las que tienes acceso.</div>`;
  content.appendChild(panel);
  const send=document.getElementById('managerAiChatSend');
  if(send)send.onclick=async()=>{
    const input=document.getElementById('managerAiChatInput');const message=(input?.value||'').trim();if(!message)return;
    let companyId=null;
    try{companyId=COMPANY_CONTEXT?.id||null}catch(_){}
    try{
      send.disabled=true;
      await api('/api/manager-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,company_id:companyId})});
      input.value='';
      await loadManagerAiChat();
      if(typeof renderManagerAiNeural==='function')setTimeout(()=>renderManagerAiNeural(),250);
    }catch(x){err(x.message)}finally{send.disabled=false}
  };
  loadManagerAiChat();
}
const _managerAi78=renderManagerAiNeural;
renderManagerAiNeural=async function(){
  const out=await _managerAi78();
  managerAiCleanCopy();
  installManagerAiChat();
  return out;
};
const _managerDetail78=renderManagerNeuronDetail;
showNeuronDetail=function(point){
  if(isManagerAiViewer())return renderManagerNeuronDetail(point);
  if(typeof renderEditableNeuronDetail==='function')return renderEditableNeuronDetail(point);
  return _managerDetail78(point);
};
const _refreshChrome78=typeof psRefreshRoleChrome==='function'?psRefreshRoleChrome:null;
if(_refreshChrome78){psRefreshRoleChrome=function(){_refreshChrome78();managerAiCleanCopy()}}
document.addEventListener('DOMContentLoaded',()=>setTimeout(managerAiCleanCopy,120));
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_manager_ai_chat():
    return _html()


@router.get('/dashboard.js')
def dashboard_manager_ai_chat_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
