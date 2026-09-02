from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .report_download_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-login-recovery'])
UI_VERSION = '2026.09.02-44'


def _html() -> str:
    html = base_html()
    for old in (
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
/* El árbol nunca debe ensanchar el dashboard. Su lienzo se desplaza dentro de su propia zona. */
#decisionFlow,.live-tree-wrap{width:100%!important;max-width:100%!important;min-width:0!important;overflow:auto!important;overscroll-behavior:contain;scrollbar-gutter:stable both-edges}
.live-tree-wrap{max-height:72vh;padding:18px 12px 34px!important;border:1px solid rgba(76,182,255,.12);border-radius:14px}
.live-tree{width:max-content!important;min-width:100%!important;max-width:none!important;margin:0 auto!important}
#content,.card,.two,.three{min-width:0}
.ticket-status-card{border:1px solid rgba(121,240,179,.28);border-radius:12px;padding:10px 12px;margin:9px 0;background:rgba(10,35,31,.35)}
.ticket-status-open{color:#ffd08a}.ticket-status-closed{color:#79f0b3}.ticket-followup{display:grid;grid-template-columns:180px 1fr auto;gap:8px;align-items:center}.ticket-followup button{width:auto}.ticket-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;word-break:break-all}
@media(max-width:800px){.ticket-followup{grid-template-columns:1fr}.live-tree-wrap{max-height:65vh}}
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
async function loadMyAccess(){
    try{USER_ACCESS=await api('/api/access-control/me');applyPermissionNavigation()}catch(_){applyPermissionNavigation()}
}
const _showPermissionAware=show;
show=async function(){await _showPermissionAware();await loadMyAccess()};

function ticketStateHtml(t){
    if(!t)return '<div class="muted">Ticket en preparación.</div>';
    const tr=t.tracking||{};
    const closed=t.status==='closed';
    return `<div class="ticket-status-card"><div><b class="ticket-code">${esc(t.code)}</b> <span class="badge ${closed?'ticket-status-closed':'ticket-status-open'}">${closed?'CERRADO':'ABIERTO'}</span></div><div><b>${esc(tr.status_label|| (closed?'Cerrado':'En atención'))}</b></div><div>${esc(tr.message||'Tu caso está siendo atendido por nuestro equipo.')}</div>${tr.updated_at?`<div class="muted">Última actualización: ${esc(tr.updated_at)}</div>`:''}</div>`;
}
async function ticketMapForCompany(companyId=null){
    const q=companyId?'?company_id='+encodeURIComponent(companyId):'';
    const rows=await api('/api/tickets'+q);const map=new Map();rows.forEach(t=>map.set(Number(t.conversation_id),t));return {rows,map};
}

conv=async function(companyId=null){
    LIVE_VIEW='conversations';LIVE_CHAT_ID=null;hideSimulator();err('');
    try{
        const q=companyId?'?company_id='+encodeURIComponent(companyId):'';
        const [a,ticketsData]=await Promise.all([api('/api/conversaciones'+q),ticketMapForCompany(companyId)]);
        $('content').innerHTML='<div class="section-title"><h2>Conversaciones</h2><button id="goTickets">Tickets</button></div>'+a.map(r=>{const t=ticketsData.map.get(Number(r.id));return `<div class="row" data-conv="${r.id}"><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · ${esc(r.status)}</div>${ticketStateHtml(t)}<button class="open-chat">Abrir chat</button></div>`}).join('');
        if($('goTickets'))$('goTickets').onclick=ticketsView;
        document.querySelectorAll('.open-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));
    }catch(x){err(x.message)}
};

openChat=async function(id){
    LIVE_VIEW='chat';LIVE_CHAT_ID=id;hideSimulator();err('');
    try{
        const [all,msgs,ticketData]=await Promise.all([api('/api/conversaciones'),api('/api/conversaciones/'+id+'/mensajes'),ticketMapForCompany()]);
        const c=all.find(x=>x.id===id),t=ticketData.map.get(Number(id));
        $('content').innerHTML=`<button id="backChats">← Conversaciones</button><h2>Chat</h2><div><b>${esc(c?.company_name||'')}</b> · ${esc(c?.wa_user_id||'')}</div>${ticketStateHtml(t)}${t&&operate()?`<div class="ticket-followup"><select id="chatTicketStatus"><option>En atención</option><option>En revisión</option><option>Esperando información</option><option>Visita programada</option><option>Refacción / cambio en proceso</option><option>Resuelto pendiente de confirmación</option></select><input id="chatTicketFollowup" placeholder="Mensaje de seguimiento para este ticket"><button id="saveChatFollowup">Guardar seguimiento</button></div>`:''}<div id="chatBox" class="card chat">${msgs.map(m=>`<div class="bubble ${m.direction==='inbound'?'in':'out'}"><b>${m.direction==='inbound'?'Cliente':esc(m.sender||'Bot')}</b><div>${esc(m.body)}</div><div class="muted">${esc(m.created_at)}</div></div>`).join('')||'<div class="muted">Sin mensajes.</div>'}</div>${operate()?'<textarea id="replyText" placeholder="Escribe una respuesta manual..."></textarea><button id="sendReply">Enviar respuesta</button>':'<div class="muted">Tu rol es Lector: puedes revisar el chat, pero no responder.</div>'}`;
        $('backChats').onclick=()=>conv(c?.company_id||null);const box=$('chatBox');box.scrollTop=box.scrollHeight;
        if($('saveChatFollowup'))$('saveChatFollowup').onclick=async()=>{const message=$('chatTicketFollowup').value.trim();if(!message)return err('Escribe el mensaje de seguimiento.');try{await api('/api/tickets/'+t.id+'/seguimiento',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status_label:$('chatTicketStatus').value,message})});await openChat(id);err('Seguimiento guardado.')}catch(x){err(x.message)}};
        if($('sendReply'))$('sendReply').onclick=async()=>{const text=$('replyText').value.trim();if(!text)return;try{await api('/api/conversaciones/'+id+'/responder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});openChat(id)}catch(x){err(x.message)}};
    }catch(x){err(x.message)}
};

async function ticketsView(){
    LIVE_VIEW='tickets';LIVE_CHAT_ID=null;hideSimulator();err('');
    try{
        const id=currentCompanyId();const q=id?'?company_id='+encodeURIComponent(id):'';const rows=await api('/api/tickets'+q);
        $('content').innerHTML=`<div class="section-title"><div><h2>Tickets</h2><div class="muted">Seguimiento operativo por empresa y tienda.</div></div><button id="refreshTickets">Actualizar</button></div>${rows.map(t=>`<div class="row" data-ticket-id="${t.id}" data-conversation-id="${t.conversation_id}"><div class="section-title"><div><b class="ticket-code">${esc(t.code)}</b><div>${esc(t.company_name)} · ${esc(t.store_name)}</div></div><span class="badge ${t.status==='closed'?'ticket-status-closed':'ticket-status-open'}">${t.status==='closed'?'CERRADO':'ABIERTO'}</span></div>${ticketStateHtml(t)}<div class="muted">${esc(t.description||'')}</div><div class="toolbar"><button class="ticketOpenChat">Abrir conversación</button><button class="ticketReport">Descargar reporte</button></div>${operate()?`<div class="ticket-followup"><select class="ticketFollowupStatus"><option>En atención</option><option>En revisión</option><option>Esperando información</option><option>Visita programada</option><option>Refacción / cambio en proceso</option><option>Resuelto pendiente de confirmación</option></select><input class="ticketFollowupMessage" placeholder="Escribe una actualización o mensaje de seguimiento"><button class="ticketSaveFollowup">Guardar</button></div>`:''}</div>`).join('')||'<div class="muted">No hay tickets para la empresa seleccionada.</div>'}`;
        $('refreshTickets').onclick=ticketsView;
        document.querySelectorAll('[data-ticket-id]').forEach(row=>{const id=row.dataset.ticketId,convId=Number(row.dataset.conversationId);row.querySelector('.ticketOpenChat').onclick=()=>openChat(convId);row.querySelector('.ticketReport').onclick=()=>downloadAuthenticatedText('/api/tickets/'+id+'/reporte.csv',(row.querySelector('.ticket-code')?.textContent||'ticket')+'.csv');const save=row.querySelector('.ticketSaveFollowup');if(save)save.onclick=async()=>{const message=row.querySelector('.ticketFollowupMessage').value.trim();if(!message)return err('Escribe el mensaje de seguimiento.');try{await api('/api/tickets/'+id+'/seguimiento',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status_label:row.querySelector('.ticketFollowupStatus').value,message})});await ticketsView();err('Seguimiento guardado.')}catch(x){err(x.message)}}});
    }catch(x){err(x.message)}
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
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})
