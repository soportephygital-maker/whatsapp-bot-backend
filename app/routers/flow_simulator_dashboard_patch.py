from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .global_entry_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-flow-simulator'])
UI_VERSION = '2026.08.28-35'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-34', '2026.08.28-33', '2026.08.28-32'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '''<style>
.flow-card{overflow:auto}.flow-canvas{min-width:900px;padding:20px 10px 30px}.flow-level{display:flex;justify-content:center;gap:18px;align-items:stretch;margin:20px 0;position:relative}.flow-level:not(:last-child):after{content:"↓";position:absolute;bottom:-24px;left:50%;font-size:20px;color:#4cb6ff}.flow-node{width:230px;min-height:108px;border:1px solid rgba(76,182,255,.42);border-radius:14px;padding:12px;background:rgba(5,15,28,.88);box-shadow:0 8px 28px rgba(0,0,0,.18)}.flow-node.root{border-color:#79f0b3}.flow-node.human{border-color:#ff9ea8}.flow-node .flow-key{font-size:11px;color:#8fa8c3;text-transform:uppercase;letter-spacing:.06em}.flow-node .flow-msg{font-size:13px;margin-top:6px}.flow-branches{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.flow-branches span{font-size:10px;padding:3px 6px;border-radius:999px;background:rgba(76,182,255,.15)}
#botSimulatorLaunch{position:fixed;right:24px;bottom:22px;z-index:1000;width:auto;padding:12px 18px;border-radius:999px;box-shadow:0 8px 30px rgba(0,0,0,.35)}#botSimulatorPanel{position:fixed;right:24px;bottom:76px;z-index:1001;width:min(390px,calc(100vw - 32px));height:560px;max-height:calc(100vh - 110px);display:flex;flex-direction:column;background:#07111f;border:1px solid rgba(76,182,255,.5);border-radius:18px;box-shadow:0 18px 60px rgba(0,0,0,.5);overflow:hidden}#botSimulatorPanel.h{display:none!important}.sim-head{padding:12px 14px;border-bottom:1px solid rgba(130,180,230,.18);display:flex;align-items:center;justify-content:space-between}.sim-head button{width:auto;margin:0}.sim-chat{flex:1;overflow:auto;padding:12px}.sim-bubble{max-width:88%;padding:9px 11px;border-radius:13px;margin:8px 0;white-space:pre-wrap;font-size:13px}.sim-bot{background:#10243a;margin-right:auto}.sim-user{background:#153a2c;margin-left:auto}.sim-system{background:#351421;margin-right:auto}.sim-input{padding:10px;border-top:1px solid rgba(130,180,230,.18)}.sim-input .toolbar{display:grid;grid-template-columns:1fr auto}.sim-input button{width:auto}.flow-toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.flow-toolbar button{width:auto}.iqos-template-btn{width:auto}
</style></head>''',
    )
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
let SIM_STATE='';
let SIM_OPEN=false;

function simNormalize(v){return String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim()}
function simCriteria(v){return String(v||'').split(/[,;|]+/).map(simNormalize).filter(Boolean)}
function simMatches(command,text,mode='contains'){
    const msg=simNormalize(text),criteria=Array.isArray(command)?command.map(simNormalize):simCriteria(command);
    if(simNormalize(mode)==='exact')return criteria.some(c=>msg===c);
    return criteria.some(c=>(' '+msg+' ').includes(' '+c+' '));
}
function simResult(state,text){
    const nodes=treeDraft?.nodos||{},root=treeDraft?.nodo_raiz||Object.keys(nodes)[0],node=nodes[state]||nodes[root];
    if(!node)return {matched:false,state};
    if(node.tipo==='router'||Array.isArray(node.rutas)){
        const routes=[...(node.rutas||[])].sort((a,b)=>(Number(b.prioridad||0)-Number(a.prioridad||0)));
        for(const r of routes){if(simMatches(r.palabras||r.comando||'',text,r.coincidencia||'contains')){const next=r.siguiente||state;return {matched:true,state:next,response:r.respuesta||nodes[next]?.mensaje||'Continuemos.',action:r.accion||''}}}
        if(node.fallback){const f=node.fallback,next=f.siguiente||state;return {matched:true,state:next,response:f.respuesta||nodes[next]?.mensaje||'Continuemos.',action:f.accion||''}}
    }
    for(const o of node.opciones||[]){if(simMatches(o.comando||'',text)){const next=o.siguiente||state;return {matched:true,state:next,response:o.respuesta||nodes[next]?.mensaje||'Continuemos.',action:o.accion||''}}}
    return {matched:false,state,response:treeDraft?.respuesta_sin_sentido_1||'No pude identificar una opción válida.'};
}
function simulatorElements(){return {panel:$('botSimulatorPanel'),chat:$('botSimulatorChat'),input:$('botSimulatorInput')}}
function simBubble(text,kind='bot'){const e=document.createElement('div');e.className='sim-bubble sim-'+kind;e.textContent=text;return e}
function simSay(text,kind='bot'){if(!text)return;const {chat}=simulatorElements();if(!chat)return;chat.appendChild(simBubble(text,kind));chat.scrollTop=chat.scrollHeight}
function resetSimulator(){
    if(!treeDraft?.nodos)return;
    SIM_STATE=treeDraft.nodo_raiz||Object.keys(treeDraft.nodos)[0];
    const {chat}=simulatorElements();if(chat)chat.innerHTML='';
    simSay(treeDraft.nodos[SIM_STATE]?.mensaje||'Escribe un mensaje para comenzar.');
}
function sendSimulator(){
    const {input}=simulatorElements();if(!input)return;const text=input.value.trim();if(!text)return;input.value='';simSay(text,'user');
    const r=simResult(SIM_STATE,text);
    if(r.matched)SIM_STATE=r.state;
    if(r.action==='human_help'){simSay('Aquí el bot se quedaría en silencio y la conversación pasaría a atención humana.','system');return}
    simSay(r.response||treeDraft.nodos[SIM_STATE]?.mensaje||'Continuemos.');
}
function ensureSimulator(){
    if($('botSimulatorLaunch'))return;
    document.body.insertAdjacentHTML('beforeend',`<button id="botSimulatorLaunch">▶ Simular bot</button><div id="botSimulatorPanel" class="h"><div class="sim-head"><div><b>Simulador del bot</b><div class="muted">No envía mensajes reales</div></div><div class="toolbar"><button id="botSimulatorReset">↻</button><button id="botSimulatorClose">×</button></div></div><div id="botSimulatorChat" class="sim-chat"></div><div class="sim-input"><div class="toolbar"><input id="botSimulatorInput" placeholder="Escribe como si fueras el usuario..."><button id="botSimulatorSend">Enviar</button></div></div></div>`);
    $('botSimulatorLaunch').onclick=()=>{SIM_OPEN=!SIM_OPEN;$('botSimulatorPanel').classList.toggle('h',!SIM_OPEN);if(SIM_OPEN)resetSimulator()};
    $('botSimulatorClose').onclick=()=>{SIM_OPEN=false;$('botSimulatorPanel').classList.add('h')};
    $('botSimulatorReset').onclick=resetSimulator;
    $('botSimulatorSend').onclick=sendSimulator;
    $('botSimulatorInput').onkeydown=e=>{if(e.key==='Enter')sendSimulator()};
}
function hideSimulator(){if($('botSimulatorLaunch'))$('botSimulatorLaunch').classList.add('h');if($('botSimulatorPanel'))$('botSimulatorPanel').classList.add('h');SIM_OPEN=false}
function showSimulator(){ensureSimulator();$('botSimulatorLaunch')?.classList.remove('h')}

function treeLevels(){
    const nodes=treeDraft?.nodos||{},root=treeDraft?.nodo_raiz||Object.keys(nodes)[0];if(!root)return [];
    const q=[[root,0]],seen=new Set(),levels=[];
    while(q.length){const [key,depth]=q.shift();if(seen.has(key)||!nodes[key])continue;seen.add(key);(levels[depth]||(levels[depth]=[])).push(key);const n=nodes[key];const dest=[];(n.opciones||[]).forEach(o=>dest.push(o.siguiente));(n.rutas||[]).forEach(r=>dest.push(r.siguiente));if(n.fallback?.siguiente)dest.push(n.fallback.siguiente);dest.filter(Boolean).forEach(k=>q.push([k,depth+1]));}
    Object.keys(nodes).filter(k=>!seen.has(k)).forEach(k=>(levels[levels.length]||(levels[levels.length]=[])).push(k));
    return levels;
}
function branchLabels(node){
    const labels=[];(node.opciones||[]).slice(0,5).forEach(o=>labels.push(o.accion==='human_help'?'→ humano':`${o.comando} → ${o.siguiente}`));(node.rutas||[]).slice(0,5).forEach(r=>labels.push(`${(r.palabras||[]).join('/')} → ${r.siguiente}`));return labels;
}
function renderDecisionFlow(){
    const host=$('decisionFlow');if(!host||!treeDraft?.nodos)return;
    const root=treeDraft.nodo_raiz,levels=treeLevels();
    host.innerHTML=levels.map(level=>`<div class="flow-level">${level.map(k=>{const n=treeDraft.nodos[k]||{},human=k==='humano'||(n.opciones||[]).length===0&&!n.mensaje;return `<div class="flow-node ${k===root?'root':''} ${human?'human':''}"><div class="flow-key">${esc(k)}</div><div class="flow-msg">${esc(n.mensaje||'Atención humana / fin del flujo')}</div><div class="flow-branches">${branchLabels(n).map(x=>`<span>${esc(x)}</span>`).join('')}</div></div>`}).join('')}</div>`).join('');
}
function addFlowCard(){
    if(!$('treeVisual')||$('decisionFlowCard'))return;
    $('treeVisual').insertAdjacentHTML('beforebegin',`<div id="decisionFlowCard" class="card flow-card"><div class="section-title"><div><h3>Vista del flujo</h3><div class="muted">Visualiza cómo se conecta cada paso antes de editarlo.</div></div><div class="flow-toolbar"><button id="refreshFlow">Actualizar vista</button></div></div><div id="decisionFlow" class="flow-canvas"></div></div>`);
    $('refreshFlow').onclick=()=>{try{syncTree()}catch(_){}renderDecisionFlow();resetSimulator()};renderDecisionFlow();
}
function looksLikeIqosCompany(){const row=COMPANY_ROWS.find(c=>c.empresa_id===activeCompanyKey);return /iqos|seven[- ]?cck/i.test((row?.nombre||'')+' '+(row?.empresa_id||''))}
function addIqosTemplateButton(){
    if(!admin()||!looksLikeIqosCompany()||$('applyIqosTemplate'))return;
    const h=$('content')?.querySelector('h2');if(!h)return;
    const b=document.createElement('button');b.id='applyIqosTemplate';b.className='iqos-template-btn';b.textContent='Aplicar / restaurar flujo IQOS';
    b.onclick=async()=>{if(!confirm('Esto reemplazará el árbol actual de esta empresa por el flujo IQOS de soporte. ¿Continuar?'))return;try{await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/plantilla-iqos',{method:'POST'});err('Flujo IQOS aplicado correctamente.');await companyPanel(activeCompanyKey)}catch(x){err(x.message)}};
    h.insertAdjacentElement('afterend',b);
}

const _companyPanelFlow=companyPanel;
companyPanel=async function(key){await _companyPanelFlow(key);addFlowCard();addIqosTemplateButton();showSimulator();resetSimulator()};
const _companiesFlow=companies;
companies=async function(){hideSimulator();await _companiesFlow()};
const _helpFlow=help;help=async function(){hideSimulator();await _helpFlow()};
const _convFlow=conv;conv=async function(...args){hideSimulator();await _convFlow(...args)};
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", patch + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_flow_simulator():
    return _html()


@router.get('/dashboard.js')
def dashboard_flow_simulator_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
