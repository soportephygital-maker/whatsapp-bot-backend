from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .login_recovery_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-fullscreen-support'])
UI_VERSION = '2026.09.04-62'


def _html() -> str:
    html = base_html()
    for old in (
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
@media(max-width:900px){.support-person-email-grid{grid-template-columns:1fr}}
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
    const labels={
        human_help_ack:'Atención humana + confirmación',
        ticket_open:'Abrir o mantener ticket',
        ticket_close:'Cerrar ticket como resuelto',
        ticket_reopen:'Reabrir ticket',
        ticket_status:'Consultar estado de ticket',
        visit_status:'Consultar visita o seguimiento',
        ticket_add_info:'Agregar información al ticket',
        finish:'Finalizar conversación'
    };
    return (labels[base]||'Acción automática')+(detail?' · '+detail:'');
}
function preserveActionValue(select,value){
    if(!select||!value)return;
    if(![...select.options].some(option=>option.value===value)){
        const option=document.createElement('option');option.value=value;option.textContent=advancedActionLabel(value);select.appendChild(option);
    }
    select.value=value;
    const row=select.closest('[data-option],[data-route],.fallback-box');
    if(row&&!row.querySelector('.advanced-action-note')){
        const note=document.createElement('div');note.className='advanced-action-note';note.textContent='Acción automática del flujo: consérvala para mantener tickets, cierres o canalización.';row.appendChild(note);
    }
}
function preserveTreeAdvancedActions(){
    if(!treeDraft?.nodos)return;
    document.querySelectorAll('[data-node]').forEach(nodeEl=>{
        const node=treeDraft.nodos[nodeEl.dataset.node];if(!node)return;
        nodeEl.querySelectorAll('[data-option]').forEach((row,index)=>preserveActionValue(row.querySelector('.optAction'),node.opciones?.[index]?.accion||''));
        nodeEl.querySelectorAll('[data-route]').forEach((row,index)=>preserveActionValue(row.querySelector('.routeAction'),node.rutas?.[index]?.accion||''));
        preserveActionValue(nodeEl.querySelector('.fallbackAction'),node.fallback?.accion||'');
    });
}
if(typeof renderTree==='function'){
    const _renderTreeAdvancedActions=renderTree;
    renderTree=function(){_renderTreeAdvancedActions();preserveTreeAdvancedActions()};
}

function activeCompanyIsCoppel(){
    const row=(typeof COMPANY_ROWS!=='undefined'?COMPANY_ROWS:[]).find(c=>c.empresa_id===activeCompanyKey);
    return /coppel/i.test(String(activeCompanyKey||'')+' '+String(row?.nombre||''));
}
function installCoppelTreeVersionNote(){
    if(!activeCompanyIsCoppel()||$('coppelTreeVersionNote'))return;
    const tools=$('treeFullscreenTools');if(!tools)return;
    const count=Object.keys(treeDraft?.nodos||{}).length;
    const note=document.createElement('div');note.id='coppelTreeVersionNote';note.className='tree-version-note';
    note.innerHTML=`<strong>Flujo Coppel v5 · 3 niveles</strong><span>${count} pasos cargados</span><span>PDA · AIMS · tickets · evidencia · soporte humano</span>`;
    tools.insertAdjacentElement('afterend',note);
    const templateButton=$('applyCoppelTemplate');if(templateButton)templateButton.textContent='Aplicar / restaurar flujo Coppel v5 (3 niveles)';
}

async function installSupportPeopleEmailCard(){
    if(!admin()||!activeCompanyKey||$('supportPeopleEmailCard'))return;
    try{
        const rows=await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/personal-soporte-correos');
        const card=document.createElement('div');card.className='card';card.id='supportPeopleEmailCard';
        card.innerHTML=`<div class="section-title"><div><h3>Correos del personal de soporte</h3><div class="muted">Estos correos reciben las alertas de apertura y cierre de tickets. Los correos creados en “Correos para incidencias” también aparecen aquí.</div></div><button id="testSupportEmail">Enviar correo de prueba</button></div>${rows.map(r=>`<div class="support-person-email-grid" ${r.support_id?`data-support-id="${r.support_id}"`:''}><b>${esc(r.name)}${r.source==='incident_email'?'<div class="support-email-linked">Ligado desde Correos para incidencias</div>':''}</b><span>${esc(r.phone||'Sin teléfono asociado')}</span><input class="supportPersonEmail" type="email" value="${esc(r.email||'')}" placeholder="correo@empresa.com" ${r.support_id?'':'readonly'}>${r.support_id?'<button class="saveSupportPersonEmail">Guardar correo</button>':'<span class="support-email-linked">Activo</span>'}</div>`).join('')||'<div class="muted">No hay personal ni correos de soporte configurados en esta empresa.</div>'}`;
        const anchor=$('treeVisual')||$('content').firstElementChild;$('content').insertBefore(card,anchor);
        card.querySelectorAll('.saveSupportPersonEmail').forEach(b=>b.onclick=async()=>{const row=b.closest('[data-support-id]'),email=row.querySelector('.supportPersonEmail').value.trim();if(!email)return err('Escribe un correo.');try{await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/personal-soporte-correos/'+row.dataset.supportId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});err('Correo de soporte guardado.')}catch(x){err(x.message)}});
        if($('testSupportEmail'))$('testSupportEmail').onclick=async()=>{try{const r=await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/correo-prueba-soporte',{method:'POST'});err('Correo de prueba enviado a: '+(r.recipients||[]).join(', '))}catch(x){err(x.message)}};
    }catch(x){err(x.message)}
}

const _companyPanelFullscreenSupport=companyPanel;
companyPanel=async function(key){
    await _companyPanelFullscreenSupport(key);
    installTreeFullscreenTools();
    preserveTreeAdvancedActions();
    installCoppelTreeVersionNote();
    await installSupportPeopleEmailCard();
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
