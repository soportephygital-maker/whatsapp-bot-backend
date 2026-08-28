from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .routing_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-global-entry'])
UI_VERSION = '2026.08.28-32'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-31', '2026.08.21-30', '2026.08.28-30'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '<style>.global-entry-card{border:1px solid rgba(76,182,255,.38);background:rgba(6,19,34,.78)}.global-entry-card h3{margin-bottom:4px}.global-entry-card textarea{min-height:92px;resize:vertical}.global-entry-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.global-entry-toggle{display:flex;align-items:center;gap:10px;margin:10px 0}.global-entry-toggle input{width:auto}.global-entry-flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:8px 0 16px}.global-entry-flow .badge{font-size:12px}@media(max-width:800px){.global-entry-grid{grid-template-columns:1fr}}</style></head>',
    )
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
const GLOBAL_ENTRY_DEFAULTS={
    enabled:true,
    entry_message:'Hola. Gracias por comunicarte con nosotros.',
    request_message:'Para ayudarte mejor, indícame por favor la cadena o empresa, el nombre o número de tienda y una breve descripción del problema o solicitud.',
    matched_message:'',
    unmatched_message:'No logré identificar la empresa o cadena. Por favor indícame el nombre exacto de la empresa, el número o nombre de tienda y tu problema.'
};

function globalEntryEditorHtml(cfg){
    const editable=admin();
    return `<div id="globalEntryCard" class="card global-entry-card">
        <div class="section-title"><div><h3>Inicio global del bot</h3><div class="muted">Este bloque ocurre antes de entrar al árbol de cualquier empresa.</div></div><span class="badge">GLOBAL</span></div>
        <div class="global-entry-flow"><span class="badge">Mensaje inicial</span><span>→</span><span class="badge">Solicitar datos</span><span>→</span><span class="badge">Detectar empresa</span><span>→</span><span class="badge">Árbol de empresa</span></div>
        <label class="global-entry-toggle"><input id="globalEntryEnabled" type="checkbox" ${cfg.enabled!==false?'checked':''} ${editable?'':'disabled'}><span>Usar bloque de inicio global</span></label>
        <div class="global-entry-grid">
            <div><label>Mensaje de entrada</label><textarea id="globalEntryMessage" ${editable?'':'readonly'} placeholder="Ej. Hola, gracias por comunicarte...">${esc(cfg.entry_message||'')}</textarea><div class="muted">Es la primera respuesta general que recibe cualquier persona.</div></div>
            <div><label>Respuesta para solicitar información</label><textarea id="globalRequestMessage" ${editable?'':'readonly'} placeholder="Solicita empresa, tienda y problema...">${esc(cfg.request_message||'')}</textarea><div class="muted">Aquí defines qué datos debe enviarte el usuario antes de dirigirlo a una empresa.</div></div>
            <div><label>Respuesta al identificar la empresa</label><textarea id="globalMatchedMessage" ${editable?'':'readonly'} placeholder="Opcional. Déjalo vacío para pasar directo al árbol de la empresa.">${esc(cfg.matched_message||'')}</textarea><div class="muted">Mensaje opcional antes de continuar con el árbol específico.</div></div>
            <div><label>Respuesta si no identifica la empresa</label><textarea id="globalUnmatchedMessage" ${editable?'':'readonly'} placeholder="Ej. No pude identificar la empresa...">${esc(cfg.unmatched_message||'')}</textarea><div class="muted">Se envía para pedir nuevamente los datos cuando no se puede enrutar.</div></div>
        </div>
        ${editable?'<button id="saveGlobalEntry">Guardar bloque de inicio</button>':''}
    </div>`;
}

async function loadGlobalEntryEditor(){
    const content=$('content');
    if(!content||!document.getElementById('companiesList'))return;
    try{
        const raw=await api('/api/settings/global-entry');
        const cfg={...GLOBAL_ENTRY_DEFAULTS,...raw};
        document.getElementById('globalEntryCard')?.remove();
        const heading=content.querySelector('h2');
        if(heading)heading.insertAdjacentHTML('afterend',globalEntryEditorHtml(cfg));
        else content.insertAdjacentHTML('afterbegin',globalEntryEditorHtml(cfg));
        if($('saveGlobalEntry'))$('saveGlobalEntry').onclick=async()=>{
            const payload={
                enabled:$('globalEntryEnabled').checked,
                entry_message:$('globalEntryMessage').value.trim(),
                request_message:$('globalRequestMessage').value.trim(),
                matched_message:$('globalMatchedMessage').value.trim(),
                unmatched_message:$('globalUnmatchedMessage').value.trim(),
            };
            if(!payload.entry_message)return err('Escribe el mensaje de entrada del bloque global.');
            if(!payload.request_message)return err('Escribe la respuesta para solicitar información.');
            if(!payload.unmatched_message)return err('Escribe la respuesta para cuando no se identifique la empresa.');
            try{
                await api('/api/settings/global-entry',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
                err('Bloque de inicio global guardado correctamente.');
            }catch(x){err(x.message)}
        };
    }catch(x){err(x.message)}
}

const _companiesWithGlobalEntry=companies;
companies=async function(){await _companiesWithGlobalEntry();LIVE_VIEW='companies';await loadGlobalEntryEditor()};
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", patch + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_global_entry():
    return _html()


@router.get('/dashboard.js')
def dashboard_global_entry_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
