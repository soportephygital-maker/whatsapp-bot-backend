import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_operator
from ..database import get_db
from ..models import AuditLog, Conversation, Message, SupportTicket, User
from ..services import case_report_runtime_patch  # noqa: F401
from . import dashboard_image_gallery_patch, image_evidence_listo_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
router.include_router(image_evidence_listo_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-108'
DIAGNOSTICS_BASE_URL = 'https://whatsapp-bot-backend-142e.onrender.com'


class MobileBridgeDiagnostic(BaseModel):
    event_time_ms: int | None = None
    device_id: str = ''
    app_version: str = ''
    build_code: int | None = None
    stage: str = ''
    detail: str = ''
    package_name: str = ''
    conversation: str = ''
    text: str = ''
    can_reply: bool | None = None
    request_url: str = ''
    whatsapp_enabled: bool | None = None
    whatsapp_business_enabled: bool | None = None
    selected_store_ids: list[str] = []


def _require_admin(user: User) -> None:
    if str(user.role or '').strip().lower() != 'admin':
        raise HTTPException(status_code=403, detail='Solo el administrador puede ver el diagnóstico integral')


def _diagnostic_url(detail: str, explicit: str = '') -> str:
    if explicit:
        return explicit[:1200]
    match = re.search(r'URL=([^|\\s]+)', str(detail or ''))
    return match.group(1)[:1200] if match else ''


@router.post('/api/local-bridge/diagnostics')
def receive_mobile_bridge_diagnostic(
    data: MobileBridgeDiagnostic,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    details = {
        'event_time_ms': data.event_time_ms,
        'device_id': data.device_id[:160],
        'app_version': data.app_version[:40],
        'build_code': data.build_code,
        'stage': data.stage[:80],
        'detail': data.detail[:4000],
        'package_name': data.package_name[:160],
        'conversation': data.conversation[:240],
        'text': data.text[:2000],
        'can_reply': data.can_reply,
        'request_url': _diagnostic_url(data.detail, data.request_url),
        'whatsapp_enabled': data.whatsapp_enabled,
        'whatsapp_business_enabled': data.whatsapp_business_enabled,
        'selected_store_ids': [str(x)[:40] for x in (data.selected_store_ids or [])][:50],
    }
    db.add(AuditLog(
        username=f'bridge:{operator.username}',
        action='mobile_bridge_diagnostic',
        entity='android_bridge',
        entity_id=(data.device_id or 'unknown')[:80],
        details=details,
    ))
    db.commit()
    return {'status': 'ok'}


@router.get('/api/admin/diagnostics')
def admin_diagnostics(
    limit: int = 300,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(user)
    limit = max(20, min(int(limit or 300), 1000))

    diag_rows = db.query(AuditLog).filter(
        AuditLog.action == 'mobile_bridge_diagnostic'
    ).order_by(AuditLog.id.desc()).limit(limit).all()

    messages = db.query(Message).order_by(Message.id.desc()).limit(min(limit, 500)).all()
    conversation_ids = sorted({m.conversation_id for m in messages if m.conversation_id})
    conversations = {
        row.id: row for row in (
            db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).all()
            if conversation_ids else []
        )
    }
    tickets = {
        row.conversation_id: row for row in (
            db.query(SupportTicket).filter(SupportTicket.conversation_id.in_(conversation_ids)).all()
            if conversation_ids else []
        )
    }

    error_rows = db.query(AuditLog).filter(
        AuditLog.action.like('%error%')
    ).order_by(AuditLog.id.desc()).limit(min(limit, 300)).all()

    diagnostics = []
    for row in diag_rows:
        details = dict(row.details or {})
        diagnostics.append({
            'id': row.id,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'username': row.username,
            **details,
        })

    message_rows = []
    for row in messages:
        conv = conversations.get(row.conversation_id)
        ticket = tickets.get(row.conversation_id)
        raw = dict(row.raw_payload or {}) if isinstance(row.raw_payload, dict) else {}
        message_rows.append({
            'id': row.id,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'conversation_id': row.conversation_id,
            'conversation_status': conv.status if conv else None,
            'conversation_state': conv.state if conv else None,
            'wa_user_id': conv.wa_user_id if conv else None,
            'ticket_id': ticket.id if ticket else None,
            'ticket_status': ticket.status if ticket else None,
            'direction': row.direction,
            'sender': row.sender,
            'body': row.body,
            'provider_message_id': row.provider_message_id,
            'request_url': DIAGNOSTICS_BASE_URL + '/api/local-bridge/inbound',
            'raw_payload': raw,
        })

    errors = [{
        'id': row.id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'username': row.username,
        'action': row.action,
        'entity': row.entity,
        'entity_id': row.entity_id,
        'details': row.details or {},
    } for row in error_rows]

    return {
        'base_url': DIAGNOSTICS_BASE_URL,
        'diagnostics': diagnostics,
        'messages': message_rows,
        'errors': errors,
    }


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in (
        '2026.09.04-83','2026.09.04-84','2026.09.04-85','2026.09.04-86','2026.09.04-87',
        '2026.09.04-88','2026.09.04-89','2026.09.04-90','2026.09.04-91','2026.09.04-92',
        '2026.09.04-93','2026.09.04-94','2026.09.04-95','2026.09.04-96','2026.09.04-97','2026.09.04-98','2026.09.04-99','2026.09.04-100','2026.09.04-101','2026.09.04-102','2026.09.04-103','2026.09.04-104','2026.09.04-105','2026.09.04-106','2026.09.04-107',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    nav_insert = '<button id="navDiagnostics" class="h">🧪 Diagnóstico integral</button>'
    if 'id="navDiagnostics"' not in html:
        if '<button id="logoutBtn">' in html:
            html = html.replace('<button id="logoutBtn">', nav_insert + '<button id="logoutBtn">', 1)
        else:
            html = html.replace('</aside>', nav_insert + '</aside>', 1)
    html = html.replace(
        '</style></head>',
        '''<style>
.diag-admin-grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px;margin:12px 0}.diag-event{border:1px solid rgba(76,182,255,.3);border-radius:12px;padding:12px;margin:9px 0;background:rgba(4,15,28,.72)}.diag-event.error{border-color:#ff7474}.diag-event.discarded{border-color:#f0b562}.diag-event.ok{border-color:#79f0b3}.diag-head{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}.diag-stage{font-weight:700}.diag-url{font-family:ui-monospace,Consolas,monospace;font-size:11px;word-break:break-all;padding:7px;border-radius:7px;background:rgba(76,182,255,.08);margin-top:6px}.diag-text{white-space:pre-wrap;word-break:break-word}.diag-raw{white-space:pre-wrap;word-break:break-word;font:11px ui-monospace,Consolas,monospace;max-height:300px;overflow:auto}.diag-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.diag-tabs button{width:auto}.diag-filter{display:grid;grid-template-columns:1fr 180px auto;gap:8px;align-items:end}.diag-count{font-size:24px;font-weight:800}.diag-label{font-size:11px;opacity:.72}@media(max-width:850px){.diag-admin-grid{grid-template-columns:1fr 1fr}.diag-filter{grid-template-columns:1fr}}
</style></head>''',
        1,
    )
    return html


def _js() -> str:
    js = dashboard_image_gallery_patch._js()
    patch = r'''
function injectMobileSupportAccount97(){
  const root=document.getElementById('content');
  if(!root||root.querySelector('#mobileSupportAccount97'))return;
  const box=document.createElement('div');box.id='mobileSupportAccount97';box.className='card';box.style.marginBottom='14px';
  box.innerHTML=`<h3>Cuenta Soporte app móvil</h3><div class="muted">La cuenta Soporte se crea automáticamente como operador. Aquí puedes establecer o cambiar su contraseña.</div><div style="display:grid;grid-template-columns:minmax(160px,1fr) minmax(180px,1fr) auto;gap:8px;align-items:end;margin-top:10px"><label>Usuario<input value="Soporte" disabled></label><label>Contraseña<input id="mobileSupportPass97" type="password" placeholder="Nueva contraseña de Soporte"></label><button type="button" id="mobileSupportActivate97">Guardar contraseña</button></div><div id="mobileSupportStatus97" class="muted" style="margin-top:8px"></div>`;
  root.prepend(box);const button=box.querySelector('#mobileSupportActivate97');button.onclick=async()=>{const pass=box.querySelector('#mobileSupportPass97').value,status=box.querySelector('#mobileSupportStatus97');if(!pass){status.textContent='Escribe la contraseña que usará la app.';return}button.disabled=true;status.textContent='Guardando cuenta Soporte...';try{const response=await fetch('/api/auth/soporte/activar',{method:'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify({username:'Soporte',password:pass})});const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(data.detail||`HTTP ${response.status}`);box.querySelector('#mobileSupportPass97').value='';status.textContent='✅ Cuenta Soporte activa. Ya puedes iniciar sesión en la app.';if(typeof users==='function')setTimeout(()=>users(),300)}catch(e){status.textContent='❌ '+e.message}finally{button.disabled=false}};
}
const _users97=typeof users==='function'?users:null;if(_users97){users=async function(){const out=await _users97();setTimeout(injectMobileSupportAccount97,30);return out}}
const mobileSupportObserver97=new MutationObserver(()=>{clearTimeout(window.__support97Timer);window.__support97Timer=setTimeout(injectMobileSupportAccount97,40)});
document.addEventListener('DOMContentLoaded',()=>{const content=document.getElementById('content');if(content)mobileSupportObserver97.observe(content,{childList:true,subtree:true});setTimeout(injectMobileSupportAccount97,150)});

async function showChatPhotos99(conversationId){
  const content=document.getElementById('content');if(!content)return;
  const old=document.getElementById('chatPhotos99');if(old)old.remove();
  const ticket=await ticketForConversationId(conversationId);if(!ticket)return;
  let rows=[];try{rows=await api(`/api/tickets/${ticket.id}/adjuntos`)}catch(_){return}
  const photos=(rows||[]).filter(x=>String(x.content_type||'').toLowerCase().startsWith('image/'));if(!photos.length)return;
  const box=document.createElement('div');box.id='chatPhotos99';box.className='case-photo-gallery';box.innerHTML=`<h3>📷 Fotos recibidas en este chat</h3><div class="muted">${photos.length} imagen(es) asociadas al ticket.</div><div class="case-photo-grid"></div>`;
  const grid=box.querySelector('.case-photo-grid');
  for(const p of photos){const item=document.createElement('div');item.className='case-photo-item';item.innerHTML=`<div class="case-photo-loading">Cargando...</div><div class="case-photo-meta">${esc(p.filename||'imagen')}</div>`;grid.appendChild(item);try{const url=await casePhotoBlobUrl(ticket.id,p.id);item.querySelector('.case-photo-loading')?.remove();const img=document.createElement('img');img.src=url;img.alt=p.filename||'Evidencia';img.onclick=()=>openCasePhoto(url);item.insertBefore(img,item.firstChild)}catch(_){item.querySelector('.case-photo-loading').textContent='No disponible'}}
  const firstCard=content.querySelector('.card');if(firstCard)firstCard.insertAdjacentElement('afterend',box);else content.prepend(box);
}
const _openChat99=typeof openChat==='function'?openChat:null;if(_openChat99){openChat=async function(id){const out=await _openChat99(id);setTimeout(()=>showChatPhotos99(id),80);return out}}

function diagnosticsIsAdmin(){try{return (typeof role==='function'?role():localStorage.getItem('phygital_role')||'')==='admin'}catch(_){return false}}
function diagEsc(v){return typeof esc==='function'?esc(String(v??'')):String(v??'').replace(/[&<>"]/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]))}
function diagJson(v){try{return JSON.stringify(v||{},null,2)}catch(_){return String(v||'')}}
function diagEventClass(stage){const s=String(stage||'').toUpperCase();if(s.includes('ERROR')||s.includes('FAILED'))return 'error';if(s.includes('DISCARDED'))return 'discarded';return 'ok'}
function diagAppRow(r){
  const url=r.request_url||'Sin petición HTTP en este evento';
  return `<div class="diag-event ${diagEventClass(r.stage)}"><div class="diag-head"><span class="diag-stage">APP · ${diagEsc(r.stage||'EVENTO')}</span><span class="muted">${diagEsc(r.created_at||'')}</span></div><div><b>Conversación:</b> ${diagEsc(r.conversation||'-')} · <b>App:</b> ${diagEsc(r.package_name||'-')}</div><div class="diag-text"><b>Texto:</b> ${diagEsc(r.text||'-')}</div><div class="diag-text"><b>Detalle:</b> ${diagEsc(r.detail||'-')}</div><div class="diag-url"><b>URL:</b> ${diagEsc(url)}</div><div class="muted">Dispositivo: ${diagEsc(r.device_id||'-')} · Android app: ${diagEsc(r.app_version||'-')} build ${diagEsc(r.build_code??'-')} · Responder: ${r.can_reply===true?'Sí':(r.can_reply===false?'No':'Sin comprobar')}</div><details><summary>Datos completos</summary><pre class="diag-raw">${diagEsc(diagJson(r))}</pre></details></div>`;
}
function diagMessageRow(r){
  const cls=r.direction==='inbound'?'ok':'';
  return `<div class="diag-event ${cls}"><div class="diag-head"><span class="diag-stage">BACKEND · ${diagEsc(String(r.direction||'').toUpperCase())}</span><span class="muted">${diagEsc(r.created_at||'')}</span></div><div><b>Chat:</b> ${diagEsc(r.wa_user_id||'-')} · conversación #${diagEsc(r.conversation_id||'-')} · estado ${diagEsc(r.conversation_state||'-')}</div><div><b>Ticket:</b> ${diagEsc(r.ticket_id||'-')} · ${diagEsc(r.ticket_status||'-')}</div><div class="diag-text"><b>${r.direction==='inbound'?'Escribió':'Respondió'}:</b> ${diagEsc(r.body||'')}</div><div class="diag-url"><b>URL:</b> ${diagEsc(r.request_url||'')}</div><details><summary>Payload completo</summary><pre class="diag-raw">${diagEsc(diagJson(r.raw_payload))}</pre></details></div>`;
}
function diagErrorRow(r){
 return `<div class="diag-event error"><div class="diag-head"><span class="diag-stage">BACKEND ERROR · ${diagEsc(r.action||'error')}</span><span class="muted">${diagEsc(r.created_at||'')}</span></div><div>${diagEsc(r.entity||'')} #${diagEsc(r.entity_id||'')}</div><pre class="diag-raw">${diagEsc(diagJson(r.details))}</pre></div>`;
}
async function adminDiagnostics(){
 if(!diagnosticsIsAdmin())return err('Solo el administrador puede abrir el diagnóstico integral.');
 try{
   const data=await api('/api/admin/diagnostics?limit=500');
   const app=data.diagnostics||[],msgs=data.messages||[],errors=data.errors||[];
   const failures=app.filter(x=>/ERROR|FAILED/i.test(x.stage||'')).length;
   const discarded=app.filter(x=>/DISCARDED/i.test(x.stage||'')).length;
   const http500=app.filter(x=>/HTTP 500/i.test(x.detail||'')).length;
   $('content').innerHTML=`<div id="adminDiagnosticsRoot"><div class="section-title"><div><h2>🧪 Diagnóstico integral</h2><div class="muted">Solo administrador · seguimiento App Android ↔ Backend ↔ WhatsApp</div></div><button id="diagRefresh" style="width:auto">Actualizar</button></div><div class="diag-admin-grid"><div class="card"><div class="diag-count">${app.length}</div><div class="diag-label">Eventos de la app</div></div><div class="card"><div class="diag-count">${failures}</div><div class="diag-label">Errores / fallos</div></div><div class="card"><div class="diag-count">${discarded}</div><div class="diag-label">Descartados</div></div><div class="card"><div class="diag-count">${http500}</div><div class="diag-label">HTTP 500</div></div></div><div class="diag-filter"><label>Buscar<input id="diagSearch" placeholder="texto, teléfono, URL, error..."></label><label>Vista<select id="diagView"><option value="app">Eventos de app</option><option value="messages">Mensajes backend</option><option value="errors">Errores backend</option><option value="all">Todo</option></select></label><button id="diagApply" style="width:auto">Filtrar</button></div><div class="card"><b>Backend base:</b><div class="diag-url">${diagEsc(data.base_url||'')}</div></div><div id="diagRows"></div></div>`;
   const render=()=>{const q=String($('diagSearch')?.value||'').toLowerCase(),view=$('diagView')?.value||'app';let html='';const match=x=>!q||diagJson(x).toLowerCase().includes(q);if(view==='app'||view==='all')html+=app.filter(match).map(diagAppRow).join('');if(view==='messages'||view==='all')html+=msgs.filter(match).map(diagMessageRow).join('');if(view==='errors'||view==='all')html+=errors.filter(match).map(diagErrorRow).join('');$('diagRows').innerHTML=html||'<div class="card muted">No hay registros para este filtro.</div>'};
   $('diagRefresh').onclick=adminDiagnostics;$('diagApply').onclick=render;$('diagSearch').onkeydown=e=>{if(e.key==='Enter')render()};$('diagView').onchange=render;render();
 }catch(x){err(x.message)}
}
document.addEventListener('DOMContentLoaded',()=>{const b=$('navDiagnostics');if(!b)return;b.classList.toggle('h',!diagnosticsIsAdmin());b.onclick=adminDiagnostics});
setInterval(()=>{if(document.getElementById('adminDiagnosticsRoot')&&diagnosticsIsAdmin())adminDiagnostics()},10000);
'''
    marker='\n})();'
    if marker in js:
        head, tail = js.rsplit(marker, 1)
        return head + '\n' + patch + marker + tail
    return js + '\n' + patch


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return HTMLResponse(_html(), headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})
