from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .login_recovery_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-fullscreen-support'])
UI_VERSION = '2026.09.04-64'


def _html() -> str:
    html = base_html()
    for old in (
        '2026.09.04-63',
        '2026.09.04-62',
        '2026.09.04-61',
        '2026.09.04-60',
        '2026.09.04-59',
        '2026.09.04-58',
        '2026.09.04-57',
        '2026.09.04-56',
        '2026.09.04-55',
        '2026.09.02-54',
        '2026.09.02-53',
        '2026.09.02-52',
        '2026.09.02-51',
        '2026.09.02-50',
        '2026.09.02-49',
        '2026.09.02-48',
        '2026.09.02-47',
        '2026.09.02-46',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace('</style></head>', '''<style>
.tree-fullscreen-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.tree-fullscreen-toolbar button{width:auto}
#decisionFlow:fullscreen,#treeVisual:fullscreen{background:#07111f;color:#edf6ff;padding:24px;overflow:auto}
#decisionFlow:fullscreen{height:100vh!important;max-height:none!important}
.support-person-email-grid{display:grid;grid-template-columns:minmax(150px,1fr) minmax(160px,1fr) minmax(220px,1.4fr) auto;gap:8px;align-items:center}.support-person-email-grid button{width:auto}.support-email-linked{font-size:11px;color:#79f0b3}
.tree-version-note{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0 14px;padding:10px 12px;border:1px solid rgba(121,240,179,.25);border-radius:12px;background:rgba(15,51,42,.24)}
.tree-version-note strong{color:#79f0b3}.advanced-action-note{font-size:10px;color:#ffd08a;margin-top:4px;line-height:1.35}
.ai-learning-grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px;margin:10px 0}.ai-learning-metric{padding:10px;border:1px solid rgba(76,182,255,.2);border-radius:10px}.ai-chat-log{max-height:260px;overflow:auto;border:1px solid rgba(76,182,255,.16);border-radius:10px;padding:10px;margin:8px 0}.ai-chat-msg{padding:8px 10px;margin:6px 0;border-radius:10px;background:rgba(20,49,78,.35)}.ai-chat-msg.assistant{background:rgba(21,58,44,.45)}.ai-point{border-top:1px solid rgba(143,168,195,.15);padding:10px 0}.case-download{width:auto!important}
@media(max-width:900px){.support-person-email-grid{grid-template-columns:1fr}.ai-learning-grid{grid-template-columns:1fr 1fr}}
</style></head>''')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
function installTreeFullscreenTools(){
    const flow=$('decisionFlow'),editor=$('treeVisual');
    if(!flow||!editor||$('treeFullscreenTools'))return;
    const tools=document.createElement('div');tools.id='treeFullscreenTools';tools.className='tree-fullscreen-toolbar';
    tools.innerHTML='<button id="viewTreeFullscreen">Visualizar en pantalla completa</button><button id="editTreeFullscreen">Editar en pantalla completa</button><button id="refreshTreeView">Actualizar vista</button>';
    flow.insertAdjacentElement('beforebegin',tools);
    $('viewTreeFullscreen').onclick=async()=>{try{renderDecisionFlow();await flow.requestFullscreen()}catch(x){err('No se pudo abrir pantalla completa: '+x.message)}};
    $('editTreeFullscreen').onclick=async()=>{try{await editor.requestFullscreen()}catch(x){err('No se pudo abrir el editor en pantalla completa: '+x.message)}};
    $('refreshTreeView').onclick=()=>{try{syncTree();renderDecisionFlow()}catch(x){err(x.message)}};
}

function advancedActionLabel(value){
    const raw=String(value||''),parts=raw.split(':'),base=parts.shift(),detail=parts.join(':');
    const labels={human_help_ack:'Atención humana + confirmación',ticket_open:'Abrir o mantener ticket',ticket_close:'Cerrar ticket como resuelto',ticket_reopen:'Reabrir ticket',ticket_status:'Consultar estado de ticket',visit_status:'Consultar visita o seguimiento',ticket_add_info:'Agregar información al ticket',finish:'Finalizar conversación'};
    return (labels[base]||'Acción automática')+(detail?' · '+detail:'');
}
function preserveActionValue(select,value){
    if(!select||!value)return;
    if(![...select.options].some(option=>option.value===value)){const option=document.createElement('option');option.value=value;option.textContent=advancedActionLabel(value);select.appendChild(option)}
    select.value=value;
    const row=select.closest('[data-option],[data-route],.fallback-box');
    if(row&&!row.querySelector('.advanced-action-note')){const note=document.createElement('div');note.className='advanced-action-note';note.textContent='Acción automática del flujo: consérvala para mantener tickets, cierres o canalización.';row.appendChild(note)}
}
function preserveTreeAdvancedActions(){
    if(!treeDraft?.nodos)return;
    document.querySelectorAll('[data-node]').forEach(nodeEl=>{const node=treeDraft.nodos[nodeEl.dataset.node];if(!node)return;nodeEl.querySelectorAll('[data-option]').forEach((row,index)=>preserveActionValue(row.querySelector('.optAction'),node.opciones?.[index]?.accion||''));nodeEl.querySelectorAll('[data-route]').forEach((row,index)=>preserveActionValue(row.querySelector('.routeAction'),node.rutas?.[index]?.accion||''));preserveActionValue(nodeEl.querySelector('.fallbackAction'),node.fallback?.accion||'')});
}
if(typeof renderTree==='function'){const _renderTreeAdvancedActions=renderTree;renderTree=function(){_renderTreeAdvancedActions();preserveTreeAdvancedActions()}}

function activeCompanyIsCoppel(){const row=(typeof COMPANY_ROWS!=='undefined'?COMPANY_ROWS:[]).find(c=>c.empresa_id===activeCompanyKey);return /coppel/i.test(String(activeCompanyKey||'')+' '+String(row?.nombre||''))}
function installCoppelTreeVersionNote(){
    if(!activeCompanyIsCoppel()||$('coppelTreeVersionNote'))return;
    const tools=$('treeFullscreenTools');if(!tools)return;const count=Object.keys(treeDraft?.nodos||{}).length;const note=document.createElement('div');note.id='coppelTreeVersionNote';note.className='tree-version-note';note.innerHTML=`<strong>Flujo Coppel v5 · 3 niveles</strong><span>${count} pasos cargados</span><span>PDA · AIMS · tickets · evidencia · soporte humano</span>`;tools.insertAdjacentElement('afterend',note);const templateButton=$('applyCoppelTemplate');if(templateButton)templateButton.textContent='Aplicar / restaurar flujo Coppel v5 (3 niveles)';
}

async function installSupportPeopleEmailCard(){
    if(!admin()||!activeCompanyKey||$('supportPeopleEmailCard'))return;
    try{
        const rows=await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/personal-soporte-correos');
        const card=document.createElement('div');card.className='card';card.id='supportPeopleEmailCard';
        card.innerHTML=`<div class="section-title"><div><h3>Correos del personal de soporte</h3><div class="muted">Reciben correos en hitos importantes: atención humana, cambio de estado y conclusión del caso. La apertura inicial ya no genera correo.</div></div><button id="testSupportEmail">Enviar correo de prueba</button></div>${rows.map(r=>`<div class="support-person-email-grid" ${r.support_id?`data-support-id="${r.support_id}"`:''}><b>${esc(r.name)}${r.source==='incident_email'?'<div class="support-email-linked">Ligado desde Correos para incidencias</div>':''}</b><span>${esc(r.phone||'Sin teléfono asociado')}</span><input class="supportPersonEmail" type="email" value="${esc(r.email||'')}" placeholder="correo@empresa.com" ${r.support_id?'':'readonly'}>${r.support_id?'<button class="saveSupportPersonEmail">Guardar correo</button>':'<span class="support-email-linked">Activo</span>'}</div>`).join('')||'<div class="muted">No hay personal ni correos de soporte configurados en esta empresa.</div>'}`;
        const anchor=$('treeVisual')||$('content').firstElementChild;$('content').insertBefore(card,anchor);
        card.querySelectorAll('.saveSupportPersonEmail').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-support-id]'),email=row.querySelector('.supportPersonEmail').value.trim();if(!email)return err('Escribe un correo.');try{await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/personal-soporte-correos/'+row.dataset.supportId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});err('Correo de soporte guardado.')}catch(x){err(x.message)}});
        if($('testSupportEmail'))$('testSupportEmail').onclick=async()=>{try{const r=await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/correo-prueba-soporte',{method:'POST'});err('Correo de prueba enviado a: '+(r.recipients||[]).join(', '))}catch(x){err(x.message)}};
    }catch(x){err(x.message)}
}

async function installAdminAiCard(){
    if(!admin()||$('adminAiLearningCard'))return;
    let s;try{s=await api('/api/admin-ai/status')}catch(_){return}
    let history=[];try{history=await api('/api/admin-ai/chat')}catch(_){}
    const card=document.createElement('div');card.className='card';card.id='adminAiLearningCard';
    const points=s.recent_points||[];
    card.innerHTML=`<div class="section-title"><div><h3>IA de aprendizaje · solo administrador principal</h3><div class="muted">Aprende de casos cerrados mediante puntos revisables. Nada pendiente se usa para responder clientes hasta que tú lo apruebes.</div></div><span class="badge">${s.configured?'IA conectada':'Falta OPENAI_API_KEY'}</span></div><div class="ai-learning-grid"><div class="ai-learning-metric"><b>${s.score}%</b><div class="muted">Nivel ${esc(s.level)}</div></div><div class="ai-learning-metric"><b>${s.approved_points}</b><div class="muted">Puntos aprobados</div></div><div class="ai-learning-metric"><b>${s.pending_points}</b><div class="muted">Por revisar</div></div><div class="ai-learning-metric"><b>${s.companies_with_learning}</b><div class="muted">Empresas con aprendizaje</div></div></div><h4>Chat para guiar a la IA</h4><div class="ai-chat-log" id="aiChatLog">${history.map(m=>`<div class="ai-chat-msg ${m.role==='assistant'?'assistant':''}"><b>${m.role==='assistant'?'IA':'Tú'}</b><div>${esc(m.body)}</div></div>`).join('')||'<div class="muted">Todavía no hay conversación con la IA.</div>'}</div><textarea id="aiAdminPrompt" placeholder="Ejemplo: cuando una PDA marque Timeout, primero quiero que pregunte si ya intentaron Refresh..."></textarea><button id="sendAiAdminPrompt">Enviar guía a la IA</button><h4>Puntos de aprendizaje recientes</h4><div>${points.map(p=>`<div class="ai-point" data-learning-id="${p.id}"><b>${esc(p.problem||'Sin problema definido')}</b><div>${esc(p.solution||'Sin solución definida')}</div><div class="muted">Estado: ${esc(p.status)} · confianza ${p.confidence}%</div>${p.status==='pending'?'<div class="toolbar"><button class="approveLearning">Aprobar</button><button class="rejectLearning danger">Rechazar</button></div>':''}</div>`).join('')||'<div class="muted">Aún no hay casos convertidos en puntos de aprendizaje.</div>'}</div>`;
    const anchor=$('content').firstElementChild;$('content').insertBefore(card,anchor);
    $('sendAiAdminPrompt').onclick=async()=>{const message=$('aiAdminPrompt').value.trim();if(!message)return;try{const companyId=typeof currentCompanyId==='function'?currentCompanyId():null;const r=await api('/api/admin-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,company_id:companyId})});$('aiAdminPrompt').value='';$('aiChatLog').insertAdjacentHTML('beforeend',`<div class="ai-chat-msg"><b>Tú</b><div>${esc(message)}</div></div><div class="ai-chat-msg assistant"><b>IA</b><div>${esc(r.reply)}</div></div>`);$('aiChatLog').scrollTop=$('aiChatLog').scrollHeight}catch(x){err(x.message)}};
    card.querySelectorAll('.approveLearning,.rejectLearning').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-learning-id]'),status=b.classList.contains('approveLearning')?'approved':'rejected';try{await api('/api/admin-ai/learning/'+row.dataset.learningId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});card.remove();await installAdminAiCard()}catch(x){err(x.message)}});
}

async function downloadCaseBinary(url,filename){
    try{const token=localStorage.getItem('phygital_token')||'';const r=await fetch(url,{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error(await r.text());const blob=await r.blob();const a=document.createElement('a');const u=URL.createObjectURL(blob);a.href=u;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500)}catch(x){err(x.message)}
}
function installCaseDownloadButtons(){
    document.querySelectorAll('[data-ticket-id]').forEach(row=>{if(row.querySelector('.case-download'))return;const id=row.dataset.ticketId;if(!id)return;const code=(row.querySelector('.ticket-code')?.textContent||'ticket').trim();const toolbar=row.querySelector('.toolbar')||row;const b=document.createElement('button');b.className='case-download';b.textContent='Descargar expediente completo';b.onclick=()=>downloadCaseBinary('/api/tickets/'+id+'/expediente.zip',code+'-expediente.zip');toolbar.appendChild(b)})
}
if(typeof ticketsView==='function'){const _ticketsViewCaseArchive=ticketsView;ticketsView=async function(){await _ticketsViewCaseArchive();installCaseDownloadButtons()}}

const _companyPanelFullscreenSupport=companyPanel;
companyPanel=async function(key){
    await _companyPanelFullscreenSupport(key);
    installTreeFullscreenTools();preserveTreeAdvancedActions();installCoppelTreeVersionNote();await installSupportPeopleEmailCard();await installAdminAiCard();
};
'''
    marker='\n})();'
    if marker in js:
        head,tail=js.rsplit(marker,1)
        return head+'\n'+patch+marker+tail
    return js+'\n'+patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_fullscreen_support():
    return _html()


@router.get('/dashboard.js')
def dashboard_fullscreen_support_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
