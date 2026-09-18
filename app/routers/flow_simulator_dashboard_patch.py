from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Company, GlobalSetting, User
from ..services.user_access import can_access_company, require_user_permission
from .global_entry_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-flow-simulator'])
UI_VERSION = '2026.08.28-35'

IMAGE_RECEPTION_MODE_KEYS = ('accesorios', 'aimms_pda', 'gateway_accesorios', 'preciadores')
IMAGE_RECEPTION_FIELDS = (
    'label',
    'receive_title', 'receive_text',
    'confirm_title', 'confirm_text',
    'close_title', 'close_text',
    'submenu_title', 'submenu_text',
    'add_title', 'add_text',
    'change_title', 'change_text',
    'loop_title', 'loop_text',
)

_IMAGE_RECEPTION_BASE = {
    'receive_title': '1. Recepción de imagen',
    'receive_text': 'El sistema identifica la foto y la asocia al ticket activo.',
    'confirm_title': '2. Confirmación',
    'confirm_text': '📷 ¿Esta foto es la correcta?\n1️⃣ Sí, cerrar el ticket con esta evidencia\n2️⃣ No, agregar o cambiar la foto',
    'close_title': 'Si responde 1',
    'close_text': 'Cerrar ticket → Pendiente de validación → generar expediente final.',
    'submenu_title': 'Si responde 2',
    'submenu_text': 'Mostrar submenú: 1️⃣ Agregar · 2️⃣ Cambiar.',
    'add_title': '1️⃣ Agregar',
    'add_text': 'Conservar la foto actual y esperar una evidencia adicional.',
    'change_title': '2️⃣ Cambiar',
    'change_text': 'Retirar la foto anterior del expediente y esperar la nueva.',
    'loop_title': 'Nueva foto recibida',
    'loop_text': 'Volver al paso “¿Esta foto es la correcta?” y repetir la confirmación.',
}
IMAGE_RECEPTION_DEFAULTS = {
    'accesorios': {**_IMAGE_RECEPTION_BASE, 'label': 'Accesorios'},
    'aimms_pda': {**_IMAGE_RECEPTION_BASE, 'label': 'AIMMS de la PDA'},
    'gateway_accesorios': {**_IMAGE_RECEPTION_BASE, 'label': 'Gateway de los accesorios'},
    'preciadores': {**_IMAGE_RECEPTION_BASE, 'label': 'Preciadores'},
}


class ImageReceptionFlowConfig(BaseModel):
    modes: dict[str, dict[str, str]]


def _image_reception_setting_key(company_id: int) -> str:
    return f'image_reception_flow:{company_id}'


def _image_reception_company(company_key: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    return company


def _image_reception_value(company: Company, db: Session) -> dict:
    row = db.get(GlobalSetting, _image_reception_setting_key(company.id))
    saved = row.value if row and isinstance(row.value, dict) else {}
    saved_modes = saved.get('modes') if isinstance(saved.get('modes'), dict) else {}
    modes = {}
    for key in IMAGE_RECEPTION_MODE_KEYS:
        base = dict(IMAGE_RECEPTION_DEFAULTS[key])
        incoming = saved_modes.get(key) if isinstance(saved_modes.get(key), dict) else {}
        for field in IMAGE_RECEPTION_FIELDS:
            value = incoming.get(field)
            if isinstance(value, str) and value.strip():
                base[field] = value.strip()[:1200]
        modes[key] = base
    return {'modes': modes}


@router.get('/api/empresas/{company_key}/image-reception-flow')
def get_image_reception_flow(
    company_key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = _image_reception_company(company_key, db)
    if not can_access_company(db, user, company.id):
        raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
    return _image_reception_value(company, db)


@router.put('/api/empresas/{company_key}/image-reception-flow')
def update_image_reception_flow(
    company_key: str,
    data: ImageReceptionFlowConfig,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = _image_reception_company(company_key, db)
    if not can_access_company(db, user, company.id):
        raise HTTPException(status_code=403, detail='No tienes acceso a esta empresa')
    require_user_permission(db, user, 'manage_company_tree')

    current = _image_reception_value(company, db)['modes']
    cleaned = {}
    for key in IMAGE_RECEPTION_MODE_KEYS:
        incoming = data.modes.get(key) if isinstance(data.modes.get(key), dict) else {}
        mode = dict(current[key])
        for field in IMAGE_RECEPTION_FIELDS:
            if field not in incoming:
                continue
            value = str(incoming.get(field) or '').strip()
            if not value:
                raise HTTPException(status_code=422, detail=f'{key}.{field} no puede quedar vacío')
            mode[field] = value[:1200]
        cleaned[key] = mode

    setting_key = _image_reception_setting_key(company.id)
    row = db.get(GlobalSetting, setting_key)
    value = {'modes': cleaned}
    if row:
        row.value = value
        row.updated_by = user.username
    else:
        db.add(GlobalSetting(key=setting_key, value=value, updated_by=user.username))
    db.commit()
    return {'status': 'ok', 'config': value}


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-34', '2026.08.28-33', '2026.08.28-32'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '''<style>
.flow-card{overflow:auto}.flow-canvas{min-width:900px;padding:20px 10px 30px}.flow-level{display:flex;justify-content:center;gap:18px;align-items:stretch;margin:20px 0;position:relative}.flow-level:not(:last-child):after{content:"↓";position:absolute;bottom:-24px;left:50%;font-size:20px;color:#4cb6ff}.flow-node{width:230px;min-height:108px;border:1px solid rgba(76,182,255,.42);border-radius:14px;padding:12px;background:rgba(5,15,28,.88);box-shadow:0 8px 28px rgba(0,0,0,.18)}.flow-node.root{border-color:#79f0b3}.flow-node.human{border-color:#ff9ea8}.flow-node .flow-key{font-size:11px;color:#8fa8c3;text-transform:uppercase;letter-spacing:.06em}.flow-node .flow-msg{font-size:13px;margin-top:6px}.flow-branches{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.flow-branches span{font-size:10px;padding:3px 6px;border-radius:999px;background:rgba(76,182,255,.15)}
.image-reception-card{margin-top:22px}.image-reception-grid{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:14px;margin-top:14px}.image-mode{border:1px solid rgba(76,182,255,.38);border-radius:14px;padding:14px;background:rgba(5,15,28,.72)}.image-mode h4{margin:0 0 10px;font-size:15px}.image-mode-flow{display:grid;gap:7px}.image-step{border-left:3px solid rgba(76,182,255,.65);padding:8px 10px;background:rgba(76,182,255,.08);border-radius:8px;font-size:12px;line-height:1.4}.image-step strong{display:block;margin-bottom:2px}.image-branch{display:grid;grid-template-columns:1fr 1fr;gap:7px}.image-close{border-left-color:#79f0b3}.image-change{border-left-color:#f2b96b}.image-loop{border-left-color:#9f8cff}.image-mode-badge{display:inline-block;font-size:10px;padding:3px 7px;border-radius:999px;background:rgba(76,182,255,.15);margin-bottom:8px}.image-reception-note{margin-top:12px;padding:10px 12px;border-radius:10px;background:rgba(121,240,179,.08);border:1px solid rgba(121,240,179,.25);font-size:12px}.image-reception-actions{display:flex;gap:8px;align-items:center}.image-reception-actions button{width:auto;margin:0}.ir-editable{white-space:pre-wrap;border-radius:5px;outline:none;transition:background .15s ease,box-shadow .15s ease}.ir-editable[contenteditable="true"]{cursor:text}.ir-editable[contenteditable="true"]:hover{background:rgba(76,182,255,.08)}.ir-editable[contenteditable="true"]:focus{background:rgba(76,182,255,.12);box-shadow:0 0 0 1px rgba(76,182,255,.55);padding:2px 4px;margin:-2px -4px}.image-edit-hint{font-size:11px;color:#8fa8c3;margin-top:8px}.image-save-state{font-size:11px;color:#79f0b3}@media(max-width:900px){.image-reception-grid{grid-template-columns:1fr}.image-branch{grid-template-columns:1fr}}
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
function looksLikeCoppelCompany(){const row=COMPANY_ROWS.find(c=>c.empresa_id===activeCompanyKey);return /coppel|cpp/i.test((row?.nombre||'')+' '+(row?.empresa_id||''))}
const IMAGE_RECEPTION_FALLBACK={
    accesorios:{label:'Accesorios',receive_title:'1. Recepción de imagen',receive_text:'El sistema identifica la foto y la asocia al ticket activo.',confirm_title:'2. Confirmación',confirm_text:'📷 ¿Esta foto es la correcta?\n1️⃣ Sí, cerrar el ticket con esta evidencia\n2️⃣ No, agregar o cambiar la foto',close_title:'Si responde 1',close_text:'Cerrar ticket → Pendiente de validación → generar expediente final.',submenu_title:'Si responde 2',submenu_text:'Mostrar submenú: 1️⃣ Agregar · 2️⃣ Cambiar.',add_title:'1️⃣ Agregar',add_text:'Conservar la foto actual y esperar una evidencia adicional.',change_title:'2️⃣ Cambiar',change_text:'Retirar la foto anterior del expediente y esperar la nueva.',loop_title:'Nueva foto recibida',loop_text:'Volver al paso “¿Esta foto es la correcta?” y repetir la confirmación.'},
    aimms_pda:{label:'AIMMS de la PDA'},gateway_accesorios:{label:'Gateway de los accesorios'},preciadores:{label:'Preciadores'}
};
['aimms_pda','gateway_accesorios','preciadores'].forEach(k=>IMAGE_RECEPTION_FALLBACK[k]={...IMAGE_RECEPTION_FALLBACK.accesorios,...IMAGE_RECEPTION_FALLBACK[k]});
let IMAGE_RECEPTION_CONFIG=null;
function irField(mode,field,value,tag='div',cls=''){
    const editable=admin()?'true':'false';
    return `<${tag} class="ir-editable ${cls}" data-ir-mode="${esc(mode)}" data-ir-field="${esc(field)}" contenteditable="${editable}" spellcheck="true">${esc(value||'')}</${tag}>`;
}
function imageReceptionModeHtml(key,mode){
    return `<div class="image-mode" data-image-mode="${esc(key)}"><span class="image-mode-badge">Modo de evidencia</span>${irField(key,'label',mode.label,'h4')}<div class="image-mode-flow">
        <div class="image-step">${irField(key,'receive_title',mode.receive_title,'strong')}${irField(key,'receive_text',mode.receive_text)}</div>
        <div class="image-step">${irField(key,'confirm_title',mode.confirm_title,'strong')}${irField(key,'confirm_text',mode.confirm_text)}</div>
        <div class="image-branch">
            <div class="image-step image-close">${irField(key,'close_title',mode.close_title,'strong')}${irField(key,'close_text',mode.close_text)}</div>
            <div class="image-step image-change">${irField(key,'submenu_title',mode.submenu_title,'strong')}${irField(key,'submenu_text',mode.submenu_text)}</div>
        </div>
        <div class="image-branch">
            <div class="image-step">${irField(key,'add_title',mode.add_title,'strong')}${irField(key,'add_text',mode.add_text)}</div>
            <div class="image-step">${irField(key,'change_title',mode.change_title,'strong')}${irField(key,'change_text',mode.change_text)}</div>
        </div>
        <div class="image-step image-loop">${irField(key,'loop_title',mode.loop_title,'strong')}${irField(key,'loop_text',mode.loop_text)}</div>
    </div></div>`;
}
function readImageReceptionEditor(){
    const modes=JSON.parse(JSON.stringify(IMAGE_RECEPTION_CONFIG?.modes||IMAGE_RECEPTION_FALLBACK));
    document.querySelectorAll('#imageReceptionSection [data-ir-mode][data-ir-field]').forEach(el=>{
        const mode=el.dataset.irMode,field=el.dataset.irField;
        if(!modes[mode])modes[mode]={};
        modes[mode][field]=(el.innerText||el.textContent||'').trim();
    });
    return {modes};
}
async function saveImageReceptionFlow(){
    const btn=$('saveImageReceptionFlow'),state=$('imageReceptionSaveState');
    if(!admin())return err('No tienes permiso para editar este flujo.');
    if(btn)btn.disabled=true;if(state)state.textContent='Guardando...';
    try{
        const payload=readImageReceptionEditor();
        const r=await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/image-reception-flow',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        IMAGE_RECEPTION_CONFIG=r.config||payload;
        if(state)state.textContent='✅ Cambios guardados';
        err('Recepción de imagen actualizada.');
    }catch(x){if(state)state.textContent='❌ No se pudo guardar';err(x.message)}
    finally{if(btn)btn.disabled=false}
}
async function addImageReceptionSection(){
    const content=$('content');if(!content||$('imageReceptionSection')||!looksLikeCoppelCompany())return;
    let config={modes:IMAGE_RECEPTION_FALLBACK};
    try{config=await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/image-reception-flow')}catch(_){}
    IMAGE_RECEPTION_CONFIG=config;
    const card=document.createElement('div');card.id='imageReceptionSection';card.className='card image-reception-card';
    const order=['accesorios','aimms_pda','gateway_accesorios','preciadores'];
    card.innerHTML=`<div class="section-title"><div><h3>📷 Recepción de imagen</h3><div class="muted">Acciones automáticas que se ejecutan cuando cada modo recibe evidencia fotográfica.</div></div><div class="image-reception-actions">${admin()?'<span id="imageReceptionSaveState" class="image-save-state"></span><button id="saveImageReceptionFlow">Guardar cambios</button>':'<span class="badge">Solo lectura</span>'}</div></div><div class="image-reception-grid">${order.map(k=>imageReceptionModeHtml(k,config.modes?.[k]||IMAGE_RECEPTION_FALLBACK[k])).join('')}</div><div class="image-reception-note"><b>Regla común:</b> en cualquiera de los cuatro modos, la opción 1 de la confirmación cierra el ticket; la opción 2 abre el submenú Agregar / Cambiar. Cada nueva foto vuelve a la confirmación inicial.</div>${admin()?'<div class="image-edit-hint">✏️ Haz clic directamente sobre cualquier título o texto para editarlo y después pulsa <b>Guardar cambios</b>.</div>':''}`;
    content.appendChild(card);
    if($('saveImageReceptionFlow'))$('saveImageReceptionFlow').onclick=saveImageReceptionFlow;
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
companyPanel=async function(key){await _companyPanelFlow(key);addFlowCard();await addImageReceptionSection();addIqosTemplateButton();showSimulator();resetSimulator()};
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
