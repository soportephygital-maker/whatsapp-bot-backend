from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .report_download_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-login-recovery'])
UI_VERSION = '2026.09.02-48'


def _html() -> str:
    html = base_html()
    for old in (
        '2026.09.02-47',
        '2026.09.02-46',
        '2026.09.02-45',
        '2026.09.02-44',
        '2026.08.31-43',
        '2026.08.31-42',
        '2026.08.28-41',
        '2026.08.28-40',
        '2026.08.28-39',
        '2026.08.28-38',
        '2026.08.28-37',
        '2026.08.28-36',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '<button id="navReports">Reportes</button>',
        '<button id="navTickets">Tickets</button><button id="navReports">Reportes</button>',
    )
    html = html.replace(
        '</style></head>',
        '''<style>
#decisionFlow,.live-tree-wrap{width:100%!important;max-width:100%!important;min-width:0!important;overflow:auto!important;overscroll-behavior:contain;scrollbar-gutter:stable}
.live-tree-wrap{height:58vh;max-height:58vh;padding:16px!important;border:1px solid rgba(76,182,255,.12);border-radius:14px;position:relative;contain:layout paint style}
.live-tree{width:100%!important;min-width:0!important;max-width:100%!important;margin:0!important;text-align:center}
.compact-tree{display:flex;flex-direction:column;gap:24px;width:100%;min-width:0;padding:4px}
.compact-tree-level{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;align-items:start;width:100%;position:relative}
.compact-tree-level+.compact-tree-level:before{content:'↓';position:absolute;top:-22px;left:50%;transform:translateX(-50%);color:#4cb6ff;font-size:18px}
.compact-tree-card{min-width:0;border:1px solid rgba(76,182,255,.55);border-radius:10px;padding:9px 10px;background:rgba(5,15,28,.94);cursor:pointer;box-shadow:0 5px 14px rgba(0,0,0,.18)}
.compact-tree-card.root{border-color:#79f0b3}.compact-tree-card.human{border-color:#ff8e9b}.compact-tree-card.resolved{border-color:#79f0b3}
.compact-tree-card .key{font-size:10px;text-transform:uppercase;color:#8fa8c3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.compact-tree-card .msg{font-size:12px;margin-top:4px;line-height:1.3;max-height:48px;overflow:hidden}.compact-tree-card .links{font-size:10px;color:#9fc5df;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#content,.card,.two,.three{min-width:0;max-width:100%}
.ticket-status-card{border:1px solid rgba(121,240,179,.28);border-radius:12px;padding:10px 12px;margin:9px 0;background:rgba(10,35,31,.35)}
.ticket-status-open{color:#ffd08a}.ticket-status-closed{color:#79f0b3}.ticket-followup{display:grid;grid-template-columns:180px 1fr auto;gap:8px;align-items:center}.ticket-followup button{width:auto}.ticket-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;word-break:break-all}
@media(max-width:800px){.ticket-followup{grid-template-columns:1fr}.live-tree-wrap{height:52vh;max-height:52vh}.compact-tree-level{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}}
</style></head>''',
    )
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
let USER_ACCESS={dashboard:true,permissions:{},company_ids:null};
function permissionAllowed(key){return USER_ACCESS?.permissions?.[key]===true}
function setNavVisible(id,visible){const el=document.getElementById(id);if(el)el.classList.toggle('h',!visible)}
function applyPermissionNavigation(){
    setNavVisible('navHelp',permissionAllowed('view_requests'));
    setNavVisible('navConv',permissionAllowed('view_conversations'));
    setNavVisible('navContacts',permissionAllowed('view_contacts'));
    setNavVisible('navCompanies',permissionAllowed('view_companies'));
    setNavVisible('navTickets',permissionAllowed('view_conversations')||permissionAllowed('view_reports'));
    setNavVisible('navReports',permissionAllowed('view_reports'));
    setNavVisible('navActivity',permissionAllowed('view_activity'));
    setNavVisible('navAppearance',permissionAllowed('manage_appearance'));
    setNavVisible('navUsers',permissionAllowed('manage_users')||permissionAllowed('manage_user_permissions')||permissionAllowed('manage_user_companies'));
}

/* Cache corto en memoria + sessionStorage para evitar repetir consultas al cambiar de vista. */
const UI_CACHE_TTL=30000;
const UI_CACHE=new Map();
function cacheKey(path){return 'phygital-cache:'+path}
function cacheRead(path){
    const now=Date.now(),mem=UI_CACHE.get(path);
    if(mem&&now-mem.time<UI_CACHE_TTL)return mem.value;
    try{const raw=sessionStorage.getItem(cacheKey(path));if(raw){const x=JSON.parse(raw);if(now-x.time<UI_CACHE_TTL){UI_CACHE.set(path,x);return x.value}}}catch(_){}
    return undefined;
}
function cacheWrite(path,value){
    const item={time:Date.now(),value};UI_CACHE.set(path,item);
    try{sessionStorage.setItem(cacheKey(path),JSON.stringify(item))}catch(_){}
    return value;
}
async function cachedApi(path,opt={}){
    const method=(opt.method||'GET').toUpperCase();
    if(method!=='GET')return api(path,opt);
    const hit=cacheRead(path);if(hit!==undefined)return hit;
    const value=await api(path,opt);return cacheWrite(path,value);
}
function invalidateUiCache(prefix=''){
    [...UI_CACHE.keys()].filter(k=>!prefix||k.startsWith(prefix)).forEach(k=>UI_CACHE.delete(k));
    try{for(let i=sessionStorage.length-1;i>=0;i--){const k=sessionStorage.key(i);if(k&&k.startsWith('phygital-cache:')&&(!prefix||k.slice(15).startsWith(prefix)))sessionStorage.removeItem(k)}}catch(_){}
}
async function warmUiCache(){
    const paths=['/api/empresas/listar','/api/conversaciones','/api/tickets'];
    await Promise.allSettled(paths.map(p=>cachedApi(p)));
}
async function loadMyAccess(){
    try{USER_ACCESS=await cachedApi('/api/access-control/me');applyPermissionNavigation()}catch(_){applyPermissionNavigation()}
}
const _showPermissionAware=show;
show=async function(){await _showPermissionAware();await loadMyAccess();setTimeout(warmUiCache,50)};

/* Render compacto: cada nodo se dibuja una sola vez. Evita la expansión recursiva que congelaba la página. */
function compactEdges(node){
    const out=[];
    (node?.opciones||[]).forEach(o=>{if(o.siguiente)out.push({next:o.siguiente,label:o.comando||'opción',action:o.accion||''})});
    (node?.rutas||[]).forEach(r=>{if(r.siguiente)out.push({next:r.siguiente,label:(r.palabras||[]).join(' / ')||'ruta',action:r.accion||''})});
    if(node?.fallback?.siguiente)out.push({next:node.fallback.siguiente,label:'si no coincide',action:node.fallback.accion||''});
    return out;
}
renderDecisionFlow=function(){
    const host=$('decisionFlow');if(!host||!treeDraft?.nodos)return;
    const nodes=treeDraft.nodos,root=treeDraft.nodo_raiz||Object.keys(nodes)[0];
    if(!root||!nodes[root]){host.innerHTML='<div class="muted">No hay nodos para mostrar.</div>';return}
    const levels=[],visited=new Set(),queue=[{key:root,level:0}];
    while(queue.length){const item=queue.shift();if(visited.has(item.key)||!nodes[item.key])continue;visited.add(item.key);(levels[item.level]??=[]).push(item.key);compactEdges(nodes[item.key]).forEach(e=>{if(!visited.has(e.next))queue.push({key:e.next,level:item.level+1})})}
    const orphan=Object.keys(nodes).filter(k=>!visited.has(k));if(orphan.length)levels.push(orphan);
    host.className='live-tree-wrap';
    host.innerHTML=`<div class="compact-tree">${levels.map((level,i)=>`<div class="compact-tree-level" data-level="${i}">${level.map(key=>{const node=nodes[key],edges=compactEdges(node),human=key==='humano'||edges.some(e=>e.action==='human_help')&&!node.mensaje,resolved=/resuelto|final/i.test(key);return `<div class="compact-tree-card ${key===root?'root':''} ${human?'human':''} ${resolved?'resolved':''}" data-flow-node="${esc(key)}"><div class="key">${esc(key)}</div><div class="msg">${esc(node.mensaje||'Atención humana / fin del flujo')}</div>${edges.length?`<div class="links">→ ${esc(edges.map(e=>e.next).join(' · '))}</div>`:''}</div>`}).join('')}</div>`).join('')}</div>`;
    host.scrollLeft=0;host.scrollTop=0;
    host.querySelectorAll('[data-flow-node]').forEach(box=>box.onclick=()=>jumpToTreeEditor(box.dataset.flowNode));
};

function ticketStateHtml(t){
    if(!t)return '<div class="muted">Ticket en preparación.</div>';
    const tr=t.tracking||{};const closed=t.status==='closed';
    return `<div class="ticket-status-card"><div><b class="ticket-code">${esc(t.code)}</b> <span class="badge ${closed?'ticket-status-closed':'ticket-status-open'}">${closed?'CERRADO':'ABIERTO'}</span></div><div><b>${esc(tr.status_label||(closed?'Cerrado':'En atención'))}</b></div><div>${esc(tr.message||'Tu caso está siendo atendido por nuestro equipo.')}</div>${tr.updated_at?`<div class="muted">Última actualización: ${esc(tr.updated_at)}</div>`:''}</div>`;
}
async function ticketMapForCompany(companyId=null){const q=companyId?'?company_id='+encodeURIComponent(companyId):'';const rows=await cachedApi('/api/tickets'+q);const map=new Map();rows.forEach(t=>map.set(Number(t.conversation_id),t));return {rows,map}}

conv=async function(companyId=null){
    LIVE_VIEW='conversations';LIVE_CHAT_ID=null;hideSimulator();err('');
    try{const q=companyId?'?company_id='+encodeURIComponent(companyId):'';const [a,ticketsData]=await Promise.all([cachedApi('/api/conversaciones'+q),ticketMapForCompany(companyId)]);$('content').innerHTML='<div class="section-title"><h2>Conversaciones</h2><button id="goTickets">Tickets</button></div>'+a.map(r=>{const t=ticketsData.map.get(Number(r.id));return `<div class="row" data-conv="${r.id}"><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · ${esc(r.status)}</div>${ticketStateHtml(t)}<button class="open-chat">Abrir chat</button></div>`}).join('');if($('goTickets'))$('goTickets').onclick=ticketsView;document.querySelectorAll('.open-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)))}catch(x){err(x.message)}
};

openChat=async function(id){
    LIVE_VIEW='chat';LIVE_CHAT_ID=id;hideSimulator();err('');
    try{const [all,msgs,ticketData]=await Promise.all([cachedApi('/api/conversaciones'),api('/api/conversaciones/'+id+'/mensajes'),ticketMapForCompany()]);const c=all.find(x=>x.id===id),t=ticketData.map.get(Number(id));$('content').innerHTML=`<button id="backChats">← Conversaciones</button><h2>Chat</h2><div><b>${esc(c?.company_name||'')}</b> · ${esc(c?.wa_user_id||'')}</div>${ticketStateHtml(t)}${t&&operate()?`<div class="ticket-followup"><select id="chatTicketStatus"><option>En atención</option><option>En revisión</option><option>Esperando información</option><option>Visita programada</option><option>Refacción / cambio en proceso</option><option>Resuelto pendiente de confirmación</option></select><input id="chatTicketFollowup" placeholder="Mensaje de seguimiento para este ticket"><button id="saveChatFollowup">Guardar seguimiento</button></div>`:''}<div id="chatBox" class="card chat">${msgs.map(m=>`<div class="bubble ${m.direction==='inbound'?'in':'out'}"><b>${m.direction==='inbound'?'Cliente':esc(m.sender||'Bot')}</b><div>${esc(m.body)}</div><div class="muted">${esc(m.created_at)}</div></div>`).join('')||'<div class="muted">Sin mensajes.</div>'}</div>${operate()?'<textarea id="replyText" placeholder="Escribe una respuesta manual..."></textarea><button id="sendReply">Enviar respuesta</button>':'<div class="muted">Tu rol es Lector: puedes revisar el chat, pero no responder.</div>'}`;$('backChats').onclick=()=>conv(c?.company_id||null);const box=$('chatBox');box.scrollTop=box.scrollHeight;if($('saveChatFollowup'))$('saveChatFollowup').onclick=async()=>{const message=$('chatTicketFollowup').value.trim();if(!message)return err('Escribe el mensaje de seguimiento.');try{await api('/api/tickets/'+t.id+'/seguimiento',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status_label:$('chatTicketStatus').value,message})});invalidateUiCache('/api/tickets');await openChat(id);err('Seguimiento guardado.')}catch(x){err(x.message)}};if($('sendReply'))$('sendReply').onclick=async()=>{const text=$('replyText').value.trim();if(!text)return;try{await api('/api/conversaciones/'+id+'/responder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});invalidateUiCache('/api/conversaciones');openChat(id)}catch(x){err(x.message)}}}catch(x){err(x.message)}
};

async function ticketsView(){
    LIVE_VIEW='tickets';LIVE_CHAT_ID=null;hideSimulator();err('');
    try{const id=currentCompanyId();const q=id?'?company_id='+encodeURIComponent(id):'';const rows=await cachedApi('/api/tickets'+q);$('content').innerHTML=`<div class="section-title"><div><h2>Tickets</h2><div class="muted">Seguimiento operativo por empresa y tienda.</div></div><button id="refreshTickets">Actualizar</button></div>${rows.map(t=>`<div class="row" data-ticket-id="${t.id}" data-conversation-id="${t.conversation_id}"><div class="section-title"><div><b class="ticket-code">${esc(t.code)}</b><div>${esc(t.company_name)} · ${esc(t.store_name)}</div></div><span class="badge ${t.status==='closed'?'ticket-status-closed':'ticket-status-open'}">${t.status==='closed'?'CERRADO':'ABIERTO'}</span></div>${ticketStateHtml(t)}<div class="muted">${esc(t.description||'')}</div><div class="toolbar"><button class="ticketOpenChat">Abrir conversación</button><button class="ticketReport">Descargar reporte</button></div>${operate()?`<div class="ticket-followup"><select class="ticketFollowupStatus"><option>En atención</option><option>En revisión</option><option>Esperando información</option><option>Visita programada</option><option>Refacción / cambio en proceso</option><option>Resuelto pendiente de confirmación</option></select><input class="ticketFollowupMessage" placeholder="Escribe una actualización o mensaje de seguimiento"><button class="ticketSaveFollowup">Guardar</button></div>`:''}</div>`).join('')||'<div class="muted">No hay tickets para la empresa seleccionada.</div>'}`;$('refreshTickets').onclick=()=>{invalidateUiCache('/api/tickets');ticketsView()};document.querySelectorAll('[data-ticket-id]').forEach(row=>{const tid=row.dataset.ticketId,convId=Number(row.dataset.conversationId);row.querySelector('.ticketOpenChat').onclick=()=>openChat(convId);row.querySelector('.ticketReport').onclick=()=>downloadAuthenticatedText('/api/tickets/'+tid+'/reporte.csv',(row.querySelector('.ticket-code')?.textContent||'ticket')+'.csv');const save=row.querySelector('.ticketSaveFollowup');if(save)save.onclick=async()=>{const message=row.querySelector('.ticketFollowupMessage').value.trim();if(!message)return err('Escribe el mensaje de seguimiento.');try{await api('/api/tickets/'+tid+'/seguimiento',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status_label:row.querySelector('.ticketFollowupStatus').value,message})});invalidateUiCache('/api/tickets');await ticketsView();err('Seguimiento guardado.')}catch(x){err(x.message)}}})}catch(x){err(x.message)}
}

document.addEventListener('DOMContentLoaded',()=>{if($('navTickets'))$('navTickets').onclick=ticketsView});
'''
    marker = '\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_login_recovery():
    return _html()


@router.get('/dashboard.js')
def dashboard_login_recovery_js():
    return Response(
        _js(),
        media_type='application/javascript',
        headers={'Cache-Control': 'public, max-age=31536000, immutable'},
    )
