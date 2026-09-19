from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .tree_editor_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-company-routing'])
UI_VERSION = '2026.08.28-31'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.21-30', '2026.08.28-30'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '<h1>Dashboard</h1>',
        '<div class="dashboard-head"><h1>Dashboard</h1><div class="company-context"><label for="activeCompanySelect">Marca / Empresa</label><select id="activeCompanySelect"><option value="">Todas las empresas</option></select></div></div>',
    )
    html = html.replace(
        '</style></head>',
        '<style>.dashboard-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}.company-context{min-width:260px;max-width:420px;flex:1}.company-context label{display:block;font-size:12px;color:#8fa8c3}.router-route{border:1px solid rgba(76,182,255,.25);padding:12px;border-radius:12px;margin:10px 0;background:rgba(5,15,28,.46)}.router-grid{display:grid;grid-template-columns:2fr 1fr 100px 1.2fr;gap:8px}.router-actions{display:flex;gap:6px;flex-wrap:wrap}.router-actions button{width:auto}.node-type-badge{margin-left:8px}.fallback-box{border-top:1px solid rgba(130,180,230,.15);margin-top:12px;padding-top:12px}@media(max-width:800px){.router-grid{grid-template-columns:1fr}.company-context{max-width:none;width:100%}}</style></head>',
    )
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
const COMPANY_CONTEXT_KEY='phygital_active_company_v1';
let COMPANY_CONTEXT={key:'',id:null,name:'Todas las empresas'};
let COMPANY_ROWS=[];

function currentCompanyId(){return COMPANY_CONTEXT.id||null}
function currentCompanyKey(){return COMPANY_CONTEXT.key||''}
function companyQuery(path){const id=currentCompanyId();return id?path+(path.includes('?')?'&':'?')+'company_id='+encodeURIComponent(id):path}

async function loadCompanyContext(){
    const sel=$('activeCompanySelect');if(!sel)return;
    try{
        COMPANY_ROWS=(await api('/api/empresas/listar')).filter(c=>c.activa!==false);
        const stored=localStorage.getItem(COMPANY_CONTEXT_KEY)||'';
        const valid=COMPANY_ROWS.some(c=>c.empresa_id===stored)?stored:'';
        sel.innerHTML='<option value="">Todas las empresas</option>'+COMPANY_ROWS.map(c=>`<option value="${esc(c.empresa_id)}">${esc(c.nombre)}</option>`).join('');
        sel.value=valid;
        const chosen=COMPANY_ROWS.find(c=>c.empresa_id===valid);
        COMPANY_CONTEXT=chosen?{key:chosen.empresa_id,id:chosen.id,name:chosen.nombre}:{key:'',id:null,name:'Todas las empresas'};
        sel.onchange=async()=>{
            const row=COMPANY_ROWS.find(c=>c.empresa_id===sel.value);
            COMPANY_CONTEXT=row?{key:row.empresa_id,id:row.id,name:row.nombre}:{key:'',id:null,name:'Todas las empresas'};
            if(COMPANY_CONTEXT.key)localStorage.setItem(COMPANY_CONTEXT_KEY,COMPANY_CONTEXT.key);else localStorage.removeItem(COMPANY_CONTEXT_KEY);
            if(LIVE_VIEW==='help')await help();
            else if(LIVE_VIEW==='conv')await conv();
            else if(LIVE_VIEW==='companies'&&COMPANY_CONTEXT.key)await companyPanel(COMPANY_CONTEXT.key);
        };
    }catch(x){err(x.message)}
}

const _showWithCompanyContext=show;
show=async function(){await _showWithCompanyContext();await loadCompanyContext();if(currentCompanyId()&&LIVE_VIEW==='help')await help()};

help=async function(){
    LIVE_VIEW='help';LIVE_CHAT_ID=null;err('');
    try{
        const rows=await api(companyQuery('/api/conversaciones'));
        const pending=rows.filter(r=>!['help_pending','human_active'].includes(r.status));
        $('content').innerHTML=`<div class="section-title"><h2>Solicitudes</h2><span class="badge">${esc(COMPANY_CONTEXT.name)}</span></div><p class="muted">Aquí aparecen los chats nuevos mientras los atiende el bot. Si una persona pide atención humana, el chat pasará automáticamente a Conversaciones.</p>`+
            (pending.map(r=>`<div class="row" data-conv="${r.id}"><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · <span class="badge">bot activo</span></div><button class="open-request-chat">Abrir solicitud</button></div>`).join('')||'<div class="muted">No hay solicitudes activas en este contexto.</div>');
        document.querySelectorAll('.open-request-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));
    }catch(x){err(x.message)}
};

conv=async function(companyId=null){
    LIVE_VIEW='conv';LIVE_CHAT_ID=null;err('');
    try{
        const effectiveId=companyId||currentCompanyId();
        const rows=await api('/api/conversaciones'+(effectiveId?'?company_id='+encodeURIComponent(effectiveId):''));
        const active=rows.filter(r=>['help_pending','human_active'].includes(r.status));
        const canClose=admin();
        $('content').innerHTML=`<div class="section-title"><h2>Conversaciones</h2><span class="badge">${esc(COMPANY_CONTEXT.name)}</span></div><p class="muted">Aquí aparecen únicamente los chats que ya solicitaron apoyo de una persona o que están siendo atendidos por un humano.</p>`+
            (active.map(r=>{const approval=!canClose?'<div class="muted">En espera de confirmación por parte de gerente o soporte.</div>':'';return `<div class="row" data-conv="${r.id}"><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · <span class="badge">${r.status==='human_active'?'humano atendiendo':'esperando humano'}</span></div>${approval}<div class="toolbar"><button class="open-human-chat">Abrir conversación</button>${canClose?'<button class="close-conv-success">Cerrar con éxito</button><button class="close-conv-ignore danger">Cerrar sin éxito</button>':''}</div></div>`}).join('')||'<div class="muted">No hay conversaciones esperando atención humana en este contexto.</div>');
        document.querySelectorAll('.open-human-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));
        document.querySelectorAll('.close-conv-success,.close-conv-ignore').forEach(b=>b.onclick=async()=>{
            const row=b.closest('[data-conv]'),id=Number(row.dataset.conv),result=b.classList.contains('close-conv-success')?'resolved':'ignored';
            if(await closeCase(id,result))conv(effectiveId);
        });
    }catch(x){err(x.message)}
};

function normalizeRouterRoute(route,nodeKey){
    const words=Array.isArray(route?.palabras)?route.palabras:(Array.isArray(route?.keywords)?route.keywords:String(route?.comando||'').split(/[,;|]/));
    return {
        palabras:words.map(x=>String(x||'').trim()).filter(Boolean),
        coincidencia:String(route?.coincidencia||route?.match||route?.match_type||'contains'),
        prioridad:Number(route?.prioridad??route?.priority??0)||0,
        siguiente:String(route?.siguiente||route?.destino||route?.next||nodeKey),
        respuesta:String(route?.respuesta||route?.response||''),
        accion:String(route?.accion||route?.action||''),
    };
}

normalizeTree=function(raw){
    const nodes=raw&&(raw.nodos||raw.nodes);
    if(nodes&&Object.keys(nodes).length){
        const root=raw.nodo_raiz||raw.root||Object.keys(nodes)[0],clean={};
        Object.entries(nodes).forEach(([k,n])=>{
            const routes=Array.isArray(n?.rutas)?n.rutas:(Array.isArray(n?.routes)?n.routes:[]);
            const router=String(n?.tipo||n?.type||'').toLowerCase().includes('router')||routes.length>0;
            let fallback=n?.fallback??n?.default??null;
            if(typeof fallback==='string')fallback={siguiente:fallback,respuesta:'',accion:''};
            clean[k]={
                mensaje:String(n?.mensaje||n?.message||''),
                tipo:router?'router':'options',
                opciones:Array.isArray(n?.opciones)?n.opciones.map(o=>({comando:String(o?.comando??''),respuesta:String(o?.respuesta??''),siguiente:String(o?.siguiente??k),accion:String(o?.accion||'')})):[],
                rutas:routes.map(r=>normalizeRouterRoute(r,k)),
                fallback:fallback&&typeof fallback==='object'?{siguiente:String(fallback.siguiente||fallback.destino||fallback.next||''),respuesta:String(fallback.respuesta||fallback.response||''),accion:String(fallback.accion||fallback.action||'')}:null,
            };
        });
        return {nodo_raiz:clean[root]?root:Object.keys(clean)[0],nodos:clean,respuesta_sin_sentido_1:String(raw?.respuesta_sin_sentido_1||'No pude identificar una opción válida. Por favor describe nuevamente lo que necesitas o usa alguna de las opciones disponibles.'),respuesta_sin_sentido_2:String(raw?.respuesta_sin_sentido_2||'Sigo sin poder identificar tu solicitud. Revisa las opciones disponibles o escribe humano si necesitas atención de una persona.')};
    }
    return {nodo_raiz:'inicio',nodos:{inicio:{mensaje:'Escribe aquí el mensaje inicial.',tipo:'options',opciones:[],rutas:[],fallback:null}},respuesta_sin_sentido_1:'No pude identificar una opción válida. Por favor describe nuevamente lo que necesitas o usa alguna de las opciones disponibles.',respuesta_sin_sentido_2:'Sigo sin poder identificar tu solicitud. Revisa las opciones disponibles o escribe humano si necesitas atención de una persona.'};
};

function routerNodeOptions(sel,allowBlank=false){return (allowBlank?'<option value="">Sin fallback</option>':'')+Object.keys(treeDraft.nodos).map(k=>`<option value="${esc(k)}" ${k===sel?'selected':''}>${esc(k)}</option>`).join('')}

syncTree=function(){
    document.querySelectorAll('[data-node]').forEach(ne=>{
        const k=ne.dataset.node,n=treeDraft.nodos[k];
        n.mensaje=ne.querySelector('.nodeMessage').value;
        n.tipo=ne.querySelector('.nodeType')?.value||n.tipo||'options';
        if(n.tipo==='router'){
            n.rutas=[];
            ne.querySelectorAll('[data-route]').forEach(re=>n.rutas.push({
                palabras:re.querySelector('.routeWords').value.split(',').map(x=>x.trim()).filter(Boolean),
                coincidencia:re.querySelector('.routeMatch').value,
                prioridad:Number(re.querySelector('.routePriority').value||0),
                siguiente:re.querySelector('.routeNext').value,
                respuesta:re.querySelector('.routeResponse').value,
                accion:re.querySelector('.routeAction').value,
            }));
            const fbNext=ne.querySelector('.fallbackNext')?.value||'';
            n.fallback=fbNext?{siguiente:fbNext,respuesta:ne.querySelector('.fallbackResponse')?.value||'',accion:ne.querySelector('.fallbackAction')?.value||''}:null;
        }else{
            n.opciones=[];
            ne.querySelectorAll('[data-option]').forEach(oe=>n.opciones.push({comando:oe.querySelector('.optCommand').value,respuesta:oe.querySelector('.optResponse').value,siguiente:oe.querySelector('.optNext').value,accion:oe.querySelector('.optAction')?.value||''}));
        }
    });
    if($('rootNode'))treeDraft.nodo_raiz=$('rootNode').value;
    if($('noMatchFirst'))treeDraft.respuesta_sin_sentido_1=$('noMatchFirst').value;
    if($('noMatchRepeat'))treeDraft.respuesta_sin_sentido_2=$('noMatchRepeat').value;
};

renderTree=function(){
    const host=$('treeVisual'),keys=Object.keys(treeDraft.nodos);
    host.innerHTML=`<div class="card"><div class="section-title"><h3>Árbol de decisiones</h3>${admin()?'<div class="toolbar"><button id="addNode">+ Paso normal</button><button id="addRouterNode">+ Pregunta con enrutamiento</button></div>':''}</div><label>Paso inicial</label><select id="rootNode" ${admin()?'':'disabled'}>${routerNodeOptions(treeDraft.nodo_raiz)}</select><div id="nodesHost"></div><div class="card"><h4>Cuando no entiende el mensaje</h4><p class="muted">Se usa únicamente cuando el paso actual no tiene una coincidencia ni fallback configurado.</p><label>Primera vez</label><textarea id="noMatchFirst" ${admin()?'':'readonly'}>${esc(treeDraft.respuesta_sin_sentido_1||'')}</textarea><label>Si vuelve a insistir</label><textarea id="noMatchRepeat" ${admin()?'':'readonly'}>${esc(treeDraft.respuesta_sin_sentido_2||'')}</textarea></div>${admin()?'<button id="saveTree">Guardar árbol</button>':''}</div>`;
    $('nodesHost').innerHTML=keys.map(k=>{
        const n=treeDraft.nodos[k],isRouter=n.tipo==='router';
        const body=isRouter?`
            <p class="muted">El bot envía el mensaje general y, con la siguiente respuesta del cliente, elige la primera ruta que coincida por prioridad.</p>
            <div>${(n.rutas||[]).map((r,i)=>`<div class="router-route" data-route="${i}"><div class="router-grid"><input class="routeWords" value="${esc((r.palabras||[]).join(', '))}" placeholder="playera, textil, dtf"><select class="routeMatch"><option value="contains" ${r.coincidencia!=='exact'?'selected':''}>Contiene palabra/frase</option><option value="exact" ${r.coincidencia==='exact'?'selected':''}>Coincidencia exacta</option></select><input class="routePriority" type="number" value="${esc(r.prioridad||0)}" title="Prioridad"><select class="routeNext">${routerNodeOptions(r.siguiente)}</select></div><textarea class="routeResponse" rows="2" placeholder="Respuesta opcional antes de continuar; vacío = mensaje del destino">${esc(r.respuesta||'')}</textarea><div class="router-grid"><select class="routeAction"><option value="" ${!r.accion?'selected':''}>Acción normal</option><option value="human_help" ${r.accion==='human_help'?'selected':''}>Atención humana (silencio del bot)</option></select></div>${admin()?'<div class="router-actions"><button class="routeUp">↑ Subir</button><button class="routeDown">↓ Bajar</button><button class="delRoute danger">Eliminar ruta</button></div>':''}</div>`).join('')}</div>
            ${admin()?'<button class="addRoute">+ Agregar ruta</button>':''}
            <div class="fallback-box"><h4>Si ninguna ruta coincide</h4><select class="fallbackNext">${routerNodeOptions(n.fallback?.siguiente||'',true)}</select><textarea class="fallbackResponse" rows="2" placeholder="Respuesta opcional; vacío = mensaje del destino">${esc(n.fallback?.respuesta||'')}</textarea><select class="fallbackAction"><option value="" ${!n.fallback?.accion?'selected':''}>Acción normal</option><option value="human_help" ${n.fallback?.accion==='human_help'?'selected':''}>Atención humana (silencio del bot)</option></select></div>`:
            `<div>${(n.opciones||[]).map((o,i)=>`<div class="option" data-option="${i}"><div class="three"><input class="optCommand" value="${esc(o.comando)}" placeholder="Lo que escribe"><textarea class="optResponse" rows="4" placeholder="Respuesta">${esc(o.respuesta)}</textarea><select class="optNext">${routerNodeOptions(o.siguiente)}</select></div><select class="optAction"><option value="" ${!o.accion?'selected':''}>Acción normal</option><option value="human_help" ${o.accion==='human_help'?'selected':''}>Atención humana</option></select>${admin()?'<button class="delOpt danger">Quitar opción</button>':''}</div>`).join('')}</div>${admin()?'<button class="addOpt">+ Opción</button>':''}`;
        return `<div class="node" data-node="${esc(k)}"><div class="section-title"><div><b>${esc(k)}</b><span class="badge node-type-badge">${isRouter?'enrutamiento':'opciones'}</span></div>${admin()?`<select class="nodeType" style="width:auto"><option value="options" ${!isRouter?'selected':''}>Opciones normales</option><option value="router" ${isRouter?'selected':''}>Pregunta con enrutamiento</option></select>`:''}</div><textarea class="nodeMessage" ${admin()?'':'readonly'}>${esc(n.mensaje)}</textarea>${body}${admin()?`<div class="toolbar"><button class="dupNode">Duplicar paso</button>${keys.length>1?'<button class="delNode danger">Eliminar paso</button>':''}</div>`:''}</div>`;
    }).join('');
    if(!admin())return;
    document.querySelectorAll('.nodeType').forEach(s=>s.onchange=()=>{syncTree();const k=s.closest('[data-node]').dataset.node,n=treeDraft.nodos[k];n.tipo=s.value;if(s.value==='router'&&!Array.isArray(n.rutas))n.rutas=[];renderTree()});
    $('addNode').onclick=()=>{syncTree();let i=1;while(treeDraft.nodos['paso_'+i])i++;treeDraft.nodos['paso_'+i]={mensaje:'Nuevo paso',tipo:'options',opciones:[],rutas:[],fallback:null};renderTree()};
    $('addRouterNode').onclick=()=>{syncTree();let i=1;while(treeDraft.nodos['enrutador_'+i])i++;treeDraft.nodos['enrutador_'+i]={mensaje:'Cuéntame brevemente qué necesitas.',tipo:'router',opciones:[],rutas:[],fallback:null};renderTree()};
    document.querySelectorAll('.addOpt').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node;treeDraft.nodos[k].opciones.push({comando:'',respuesta:'',siguiente:k,accion:''});renderTree()});
    document.querySelectorAll('.delOpt').forEach(b=>b.onclick=()=>{syncTree();const n=b.closest('[data-node]').dataset.node,i=Number(b.closest('[data-option]').dataset.option);treeDraft.nodos[n].opciones.splice(i,1);renderTree()});
    document.querySelectorAll('.addRoute').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node;treeDraft.nodos[k].rutas.push({palabras:[],coincidencia:'contains',prioridad:0,siguiente:k,respuesta:'',accion:''});renderTree()});
    document.querySelectorAll('.delRoute').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node,i=Number(b.closest('[data-route]').dataset.route);treeDraft.nodos[k].rutas.splice(i,1);renderTree()});
    document.querySelectorAll('.routeUp').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node,i=Number(b.closest('[data-route]').dataset.route);if(i>0){const a=treeDraft.nodos[k].rutas;[a[i-1],a[i]]=[a[i],a[i-1]]}renderTree()});
    document.querySelectorAll('.routeDown').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node,i=Number(b.closest('[data-route]').dataset.route),a=treeDraft.nodos[k].rutas;if(i<a.length-1)[a[i],a[i+1]]=[a[i+1],a[i]];renderTree()});
    document.querySelectorAll('.dupNode').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node;let i=1,name=k+'_copia';while(treeDraft.nodos[name])name=k+'_copia_'+(++i);treeDraft.nodos[name]=JSON.parse(JSON.stringify(treeDraft.nodos[k]));renderTree()});
    document.querySelectorAll('.delNode').forEach(b=>b.onclick=()=>{syncTree();const k=b.closest('[data-node]').dataset.node;if(!confirm('¿Eliminar '+k+'?'))return;delete treeDraft.nodos[k];if(treeDraft.nodo_raiz===k)treeDraft.nodo_raiz=Object.keys(treeDraft.nodos)[0];renderTree()});
    $('saveTree').onclick=async()=>{syncTree();try{await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/arbol',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({structure:treeDraft})});err('Árbol guardado correctamente.')}catch(x){err(x.message)}};
};

const _companyPanelRouting=companyPanel;
companyPanel=async function(key){await _companyPanelRouting(key);LIVE_VIEW='companies';if(COMPANY_ROWS.length){const row=COMPANY_ROWS.find(c=>c.empresa_id===key);if(row){COMPANY_CONTEXT={key:row.empresa_id,id:row.id,name:row.nombre};localStorage.setItem(COMPANY_CONTEXT_KEY,row.empresa_id);const sel=$('activeCompanySelect');if(sel)sel.value=row.empresa_id}}};
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", patch + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_company_routing():
    return _html()


@router.get('/dashboard.js')
def dashboard_company_routing_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
