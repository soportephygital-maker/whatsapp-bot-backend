from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .manager_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-tree-multiline'])
UI_VERSION = '2026.08.21-25'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.21-16', '2026.08.21-17', '2026.08.21-18', '2026.08.21-19', '2026.08.21-20', '2026.08.21-21', '2026.08.21-22', '2026.08.21-23', '2026.08.21-24'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '<style>.optResponse{min-height:110px;resize:vertical;white-space:pre-wrap;line-height:1.45}.nodeMessage{min-height:110px;resize:vertical;white-space:pre-wrap;line-height:1.45}</style></head>',
    )
    return html


def _js() -> str:
    js = base_js()
    js = js.replace(
        '<input class="optResponse" value="${esc(o.respuesta)}" placeholder="Respuesta">',
        '<textarea class="optResponse" rows="5" placeholder="Respuesta. Puedes usar Enter para separar párrafos.">${esc(o.respuesta)}</textarea>',
    )
    js = js.replace(
        "if(LIVE_VIEW==='help')await _help();else if(LIVE_VIEW==='conv')await _conv();",
        "if(LIVE_VIEW==='help')await help();else if(LIVE_VIEW==='conv')await conv();",
    )

    flow_code = r'''
help=async function(){
    LIVE_VIEW='help';LIVE_CHAT_ID=null;err('');
    try{
        const rows=await api('/api/conversaciones');
        const pending=rows.filter(r=>!['help_pending','human_active'].includes(r.status));
        $('content').innerHTML='<h2>Solicitudes</h2><p class="muted">Aquí aparecen los chats nuevos mientras los atiende el bot. Si una persona pide atención humana, el chat pasará automáticamente a Conversaciones.</p>'+
            (pending.map(r=>`<div class="row" data-conv="${r.id}"><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · <span class="badge">bot activo</span></div><button class="open-request-chat">Abrir solicitud</button></div>`).join('')||'<div class="muted">No hay solicitudes activas.</div>');
        document.querySelectorAll('.open-request-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));
    }catch(x){err(x.message)}
};

conv=async function(companyId=null){
    LIVE_VIEW='conv';LIVE_CHAT_ID=null;err('');
    try{
        const [rows,helps]=await Promise.all([
            api('/api/conversaciones'+(companyId?'?company_id='+encodeURIComponent(companyId):'')),
            api('/api/help-requests')
        ]);
        const active=rows.filter(r=>['help_pending','human_active'].includes(r.status));
        const activeHelp=new Map();
        helps.filter(h=>['new','reviewing'].includes(h.status)).forEach(h=>{if(!activeHelp.has(Number(h.conversation_id)))activeHelp.set(Number(h.conversation_id),h)});
        $('content').innerHTML='<h2>Conversaciones</h2><p class="muted">Aquí aparecen únicamente los chats que ya solicitaron apoyo de una persona o que están siendo atendidos por un humano.</p>'+
            (active.map(r=>{const h=activeHelp.get(Number(r.id));return `<div class="row" data-conv="${r.id}" ${h?`data-help="${h.id}"`:''}><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · <span class="badge">${r.status==='human_active'?'humano atendiendo':'esperando humano'}</span></div><div class="toolbar"><button class="open-human-chat">Abrir conversación</button>${h&&operate()?'<button class="close-human-success">Cerrar atendido</button><button class="close-human-ignore danger">Cerrar sin éxito</button>':''}</div></div>`}).join('')||'<div class="muted">No hay conversaciones esperando atención humana.</div>');
        document.querySelectorAll('.open-human-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));
        document.querySelectorAll('.close-human-success,.close-human-ignore').forEach(b=>b.onclick=async()=>{
            const row=b.closest('[data-help]');if(!row)return;
            const status=b.classList.contains('close-human-success')?'resolved':'ignored';
            try{await api('/api/help-requests/'+row.dataset.help,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});conv(companyId)}catch(x){err(x.message)}
        });
    }catch(x){err(x.message)}
};
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", flow_code + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_tree_multiline():
    return _html()


@router.get('/dashboard.js')
def dashboard_tree_multiline_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
