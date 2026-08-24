from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from .manager_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-tree-multiline'])
UI_VERSION = '2026.08.21-27'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.21-16', '2026.08.21-17', '2026.08.21-18', '2026.08.21-19', '2026.08.21-20', '2026.08.21-21', '2026.08.21-22', '2026.08.21-23', '2026.08.21-24', '2026.08.21-25', '2026.08.21-26'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '<style>.optResponse{min-height:110px;resize:vertical;white-space:pre-wrap;line-height:1.45}.nodeMessage{min-height:110px;resize:vertical;white-space:pre-wrap;line-height:1.45}.case-actions{border:1px solid rgba(76,182,255,.35);padding:14px;border-radius:12px;margin:12px 0}</style></head>',
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
    js = js.replace(
        "else if(LIVE_VIEW==='users')await _users();",
        "else if(LIVE_VIEW==='users')await users();",
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

async function closeCase(conversationId,result){
    const label=result==='resolved'?'cerrar el caso como atendido con éxito':'cerrar el caso sin éxito';
    if(!confirm('¿Seguro que deseas '+label+'? El chatbot volverá a quedar disponible para este chat.'))return false;
    try{
        await api('/api/conversaciones/'+conversationId+'/cerrar?resultado='+encodeURIComponent(result),{method:'POST'});
        return true;
    }catch(x){err(x.message);return false}
}

async function deleteConversation(conversationId){
    if(!confirm('¿ELIMINAR esta conversación definitivamente? Se borrarán sus mensajes, solicitudes y datos asociados del dashboard. Esta acción no se puede deshacer.'))return false;
    try{
        await api('/api/conversaciones/'+conversationId+'/olvidar',{method:'DELETE'});
        return true;
    }catch(x){err(x.message);return false}
}

conv=async function(companyId=null){
    LIVE_VIEW='conv';LIVE_CHAT_ID=null;err('');
    try{
        const rows=await api('/api/conversaciones'+(companyId?'?company_id='+encodeURIComponent(companyId):''));
        const active=rows.filter(r=>['help_pending','human_active'].includes(r.status));
        const canClose=admin();
        $('content').innerHTML='<h2>Conversaciones</h2><p class="muted">Aquí aparecen únicamente los chats que ya solicitaron apoyo de una persona o que están siendo atendidos por un humano.</p>'+
            (active.map(r=>{const approval=!canClose?'<div class="muted">En espera de confirmación por parte de gerente o soporte.</div>':'';return `<div class="row" data-conv="${r.id}"><b>${esc(r.company_name)}</b> · ${esc(r.wa_user_id)} <span class="badge">${r.known_contact?'contacto':'no agregado'}</span><div>${esc(r.state)} · <span class="badge">${r.status==='human_active'?'humano atendiendo':'esperando humano'}</span></div>${approval}<div class="toolbar"><button class="open-human-chat">Abrir conversación</button>${canClose?'<button class="close-conv-success">Cerrar con éxito</button><button class="close-conv-ignore danger">Cerrar sin éxito</button>':''}</div></div>`}).join('')||'<div class="muted">No hay conversaciones esperando atención humana.</div>');
        document.querySelectorAll('.open-human-chat').forEach(b=>b.onclick=()=>openChat(Number(b.closest('[data-conv]').dataset.conv)));
        document.querySelectorAll('.close-conv-success,.close-conv-ignore').forEach(b=>b.onclick=async()=>{
            const row=b.closest('[data-conv]'),id=Number(row.dataset.conv),result=b.classList.contains('close-conv-success')?'resolved':'ignored';
            if(await closeCase(id,result))conv(companyId);
        });
    }catch(x){err(x.message)}
};

const _openChatWithCaseTools=openChat;
openChat=async function(id){
    await _openChatWithCaseTools(id);
    LIVE_VIEW='chat';LIVE_CHAT_ID=Number(id);
    const content=$('content');if(!content)return;
    const controls=document.createElement('div');controls.className='case-actions';
    if(admin()){
        controls.innerHTML='<b>Control del caso</b><div class="muted">Solo Administrador y Gerente pueden cerrar o eliminar una conversación.</div><div class="toolbar"><button id="caseCloseSuccess">Cerrar con éxito</button><button id="caseCloseFail" class="danger">Cerrar sin éxito</button><button id="caseDelete" class="danger">Eliminar conversación</button></div>';
        const anchor=content.querySelector('#chatBox');
        if(anchor)anchor.insertAdjacentElement('beforebegin',controls);else content.prepend(controls);
        $('caseCloseSuccess').onclick=async()=>{if(await closeCase(Number(id),'resolved'))conv()};
        $('caseCloseFail').onclick=async()=>{if(await closeCase(Number(id),'ignored'))conv()};
        $('caseDelete').onclick=async()=>{if(await deleteConversation(Number(id)))conv()};
    }else{
        controls.innerHTML='<b>Caso pendiente de cierre</b><div class="muted">En espera de confirmación por parte de gerente o soporte. Puedes atender la conversación si tu rol lo permite, pero no cerrarla ni eliminarla.</div>';
        const anchor=content.querySelector('#chatBox');
        if(anchor)anchor.insertAdjacentElement('beforebegin',controls);else content.prepend(controls);
    }
};

const _usersWithAliasBase=users;
users=async function(){
    await _usersWithAliasBase();
    LIVE_VIEW='users';LIVE_CHAT_ID=null;
    if(!rootAdmin())return;
    try{
        const data=await api('/api/settings/owner-alias');
        const content=$('content');if(!content)return;
        const card=document.createElement('div');card.className='card';card.id='ownerAliasCard';
        card.innerHTML=`<h3>Identidad visible del propietario</h3><p class="muted">Para Gerentes, Operadores y Lectores, la cuenta propietaria nunca se mostrará como Administrador ni con su usuario técnico. Solo tú puedes ver y cambiar este seudónimo.</p><label>Seudónimo visible<input id="ownerAliasInput" maxlength="80" value="${esc(data.alias||'Zoe Ortiz')}"></label><div class="muted">Cuenta interna real: <b>${esc(data.internal_username||'')}</b> · visible únicamente para ti.</div><button id="saveOwnerAlias">Guardar seudónimo</button>`;
        content.prepend(card);
        $('saveOwnerAlias').onclick=async()=>{
            const alias=$('ownerAliasInput').value.trim();if(alias.length<2)return err('El seudónimo debe tener al menos 2 caracteres.');
            try{await api('/api/settings/owner-alias',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({alias})});err('Seudónimo actualizado. Los mensajes del propietario ya se mostrarán con este nombre.')}catch(x){err(x.message)}
        };
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
