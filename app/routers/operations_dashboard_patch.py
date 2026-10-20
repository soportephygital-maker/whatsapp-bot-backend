from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .flow_simulator_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-operations'])
UI_VERSION = '2026.08.28-36'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-35', '2026.08.28-34', '2026.08.28-33'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '<button id="navAppearance"',
        '<button id="navReports">Reportes</button><button id="navAppearance"',
    )
    html = html.replace(
        '</style></head>',
        '''<style>
.live-tree-wrap{overflow:auto;padding:18px 8px 32px}.live-tree{display:table;margin:0 auto;text-align:center;min-width:max-content}.live-tree ul{padding-top:28px;position:relative;display:flex;justify-content:center;margin:0;padding-left:0}.live-tree li{list-style:none;position:relative;padding:28px 10px 0;display:flex;flex-direction:column;align-items:center}.live-tree li:before,.live-tree li:after{content:"";position:absolute;top:0;right:50%;border-top:2px solid rgba(76,182,255,.55);width:50%;height:28px}.live-tree li:after{right:auto;left:50%;border-left:2px solid rgba(76,182,255,.55)}.live-tree li:only-child:after,.live-tree li:only-child:before{display:none}.live-tree li:only-child{padding-top:0}.live-tree li:first-child:before,.live-tree li:last-child:after{border:0}.live-tree li:last-child:before{border-right:2px solid rgba(76,182,255,.55);border-radius:0 8px 0 0}.live-tree li:first-child:after{border-radius:8px 0 0 0}.live-tree ul ul:before{content:"";position:absolute;top:0;left:50%;border-left:2px solid rgba(76,182,255,.55);height:28px}.tree-box{width:220px;max-width:220px;border:1px solid rgba(76,182,255,.6);border-radius:10px;padding:10px;background:rgba(5,15,28,.94);cursor:pointer;transition:.15s;box-shadow:0 7px 22px rgba(0,0,0,.2)}.tree-box:hover{transform:translateY(-2px);border-color:#9bd7ff;box-shadow:0 8px 26px rgba(76,182,255,.18)}.tree-box.root{border-color:#79f0b3}.tree-box.human{border-color:#ff8e9b}.tree-box.resolved{border-color:#79f0b3}.tree-box .key{font-size:11px;text-transform:uppercase;color:#8fa8c3}.tree-box .msg{font-size:12px;margin-top:5px;max-height:58px;overflow:hidden}.tree-edge-label{position:absolute;top:3px;max-width:180px;font-size:10px;padding:2px 6px;border-radius:8px;background:#07111f;color:#b7d7ef;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;z-index:2}.node-edit-highlight{outline:3px solid rgba(121,240,179,.65)!important;box-shadow:0 0 26px rgba(121,240,179,.3)!important}.reports-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.report-chart{padding:14px;border:1px solid rgba(76,182,255,.25);border-radius:14px}.bar-row{display:grid;grid-template-columns:minmax(90px,1fr) 3fr auto;gap:8px;align-items:center;margin:8px 0}.bar-track{height:18px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden}.bar-fill{height:100%;background:currentColor;min-width:2px}.bar-open{color:#ffba66}.bar-closed{color:#79f0b3}.email-manager-grid{display:grid;grid-template-columns:1fr 1fr auto;gap:8px}.email-row{display:grid;grid-template-columns:1fr 1.5fr auto;gap:8px;align-items:center}.ticket-table{overflow:auto}.ticket-table table{width:100%;border-collapse:collapse}.ticket-table th,.ticket-table td{padding:8px;border-bottom:1px solid rgba(120,170,220,.15);text-align:left;font-size:12px}@media(max-width:800px){.email-manager-grid,.email-row{grid-template-columns:1fr}.tree-box{width:180px;max-width:180px}}
</style></head>''',
    )
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
function liveTreeEdges(node){
    const edges=[];
    (node?.opciones||[]).forEach(o=>{if(o.siguiente)edges.push({label:o.comando||'opción',next:o.siguiente,action:o.accion||''})});
    (node?.rutas||[]).forEach(r=>{if(r.siguiente)edges.push({label:(r.palabras||[]).join(' / ')||'ruta',next:r.siguiente,action:r.accion||''})});
    if(node?.fallback?.siguiente)edges.push({label:'si no coincide',next:node.fallback.siguiente,action:node.fallback.accion||''});
    return edges;
}
function liveTreeNode(key,label='',path=[]){
    const node=treeDraft?.nodos?.[key];if(!node)return '';
    const cycle=path.includes(key),human=key==='humano'||liveTreeEdges(node).some(x=>x.action==='human_help')&&!node.mensaje;
    const resolved=/resuelto|final/i.test(key);
    const box=`<div class="tree-box ${key===treeDraft.nodo_raiz?'root':''} ${human?'human':''} ${resolved?'resolved':''}" data-flow-node="${esc(key)}"><div class="key">${esc(key)}</div><div class="msg">${esc(node.mensaje||'Atención humana / fin del flujo')}</div></div>`;
    if(cycle)return `<li>${label?`<span class="tree-edge-label">${esc(label)}</span>`:''}${box}</li>`;
    const edges=liveTreeEdges(node);
    return `<li>${label?`<span class="tree-edge-label">${esc(label)}</span>`:''}${box}${edges.length?`<ul>${edges.map(e=>liveTreeNode(e.next,e.action==='human_help'?'Atención humana':e.label,[...path,key])).join('')}</ul>`:''}</li>`;
}
function renderDecisionFlow(){
    const host=$('decisionFlow');if(!host||!treeDraft?.nodos)return;
    const root=treeDraft.nodo_raiz||Object.keys(treeDraft.nodos)[0];
    host.className='live-tree-wrap';
    host.innerHTML=`<div class="live-tree"><ul>${liveTreeNode(root,'',[])}</ul></div>`;
    host.querySelectorAll('[data-flow-node]').forEach(box=>box.onclick=()=>jumpToTreeEditor(box.dataset.flowNode));
}
function jumpToTreeEditor(key){
    const target=document.querySelector(`[data-node="${CSS.escape(key)}"]`);
    if(!target)return err('No encontré el bloque editable de '+key);
    document.querySelectorAll('.node-edit-highlight').forEach(x=>x.classList.remove('node-edit-highlight'));
    target.classList.add('node-edit-highlight');
    target.scrollIntoView({behavior:'smooth',block:'center'});
    setTimeout(()=>target.classList.remove('node-edit-highlight'),2600);
}
let LIVE_TREE_TIMER=null;
function bindLiveTree(){
    const editor=$('treeVisual');if(!editor||editor.dataset.liveTreeBound)return;
    editor.dataset.liveTreeBound='1';
    const update=()=>{clearTimeout(LIVE_TREE_TIMER);LIVE_TREE_TIMER=setTimeout(()=>{try{syncTree();renderDecisionFlow()}catch(_){}},180)};
    editor.addEventListener('input',update);editor.addEventListener('change',update);editor.addEventListener('click',e=>{if(e.target.closest('button'))setTimeout(()=>{try{syncTree();renderDecisionFlow()}catch(_){}},80)});
}
const _addFlowCardLive=addFlowCard;
addFlowCard=function(){_addFlowCardLive();renderDecisionFlow();bindLiveTree()};

function looksLikeCoppelCompany(){const row=COMPANY_ROWS.find(c=>c.empresa_id===activeCompanyKey);return /coppel/i.test((row?.nombre||'')+' '+(row?.empresa_id||''))}
function addCoppelTemplateButton(){
    if(!admin()||!looksLikeCoppelCompany()||$('applyCoppelTemplate'))return;
    const h=$('content')?.querySelector('h2');if(!h)return;
    const b=document.createElement('button');b.id='applyCoppelTemplate';b.style.width='auto';b.textContent='Aplicar / restaurar flujo Coppel';
    b.onclick=async()=>{if(!confirm('Esto reemplazará el árbol actual de Coppel por el flujo de Accesorios y Etiquetas. ¿Continuar?'))return;try{await api('/api/empresas/'+encodeURIComponent(activeCompanyKey)+'/plantilla-coppel-v1',{method:'POST'});err('Flujo Coppel aplicado.');await companyPanel(activeCompanyKey)}catch(x){err(x.message)}};
    h.insertAdjacentElement('afterend',b);
}
const _companyPanelOps=companyPanel;
companyPanel=async function(key){await _companyPanelOps(key);addCoppelTemplateButton();bindLiveTree();renderDecisionFlow()};

async function loadSupportEmailManager(selectedKey=''){
    const host=$('content');if(!host)return;
    try{
        const companies=COMPANY_ROWS.length?COMPANY_ROWS:await api('/api/empresas/listar');
        const key=selectedKey||currentCompanyKey()||companies[0]?.empresa_id||'';
        if(!key)return;
        const emails=await api('/api/empresas/'+encodeURIComponent(key)+'/correos-soporte');
        $('supportEmailManager')?.remove();
        host.insertAdjacentHTML('afterbegin',`<div id="supportEmailManager" class="card"><div class="section-title"><div><h3>Correos para incidencias</h3><div class="muted">Reciben apertura y cierre de tickets de la empresa seleccionada.</div></div></div><label>Empresa</label><select id="supportEmailCompany">${companies.map(c=>`<option value="${esc(c.empresa_id)}" ${c.empresa_id===key?'selected':''}>${esc(c.nombre)}</option>`).join('')}</select>${admin()?`<div class="email-manager-grid"><input id="supportEmailName" placeholder="Nombre"><input id="supportEmailAddress" type="email" placeholder="correo@empresa.com"><button id="addSupportEmail">Agregar correo</button></div>`:''}<div>${emails.map(r=>`<div class="email-row" data-email-id="${r.id}"><b>${esc(r.name)}</b><span>${esc(r.email)}</span>${admin()?'<button class="removeSupportEmail danger">Eliminar</button>':''}</div>`).join('')||'<div class="muted">No hay correos configurados para esta empresa.</div>'}</div></div>`);
        $('supportEmailCompany').onchange=()=>loadSupportEmailManager($('supportEmailCompany').value);
        if($('addSupportEmail'))$('addSupportEmail').onclick=async()=>{const name=$('supportEmailName').value.trim()||'Soporte',email=$('supportEmailAddress').value.trim();if(!email)return err('Escribe un correo');try{await api('/api/empresas/'+encodeURIComponent(key)+'/correos-soporte',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email})});await loadSupportEmailManager(key);err('Correo agregado.')}catch(x){err(x.message)}};
        document.querySelectorAll('.removeSupportEmail').forEach(b=>b.onclick=async()=>{if(!confirm('¿Eliminar este correo de notificaciones?'))return;try{await api('/api/empresas/'+encodeURIComponent(key)+'/correos-soporte/'+b.closest('[data-email-id]').dataset.emailId,{method:'DELETE'});await loadSupportEmailManager(key)}catch(x){err(x.message)}});
    }catch(x){err(x.message)}
}
const _contactsOps=contacts;
contacts=async function(){await _contactsOps();await loadSupportEmailManager()};

function chartRows(rows,labelKey){const max=Math.max(1,...rows.map(r=>Math.max(r.open||0,r.closed||0)));return rows.map(r=>`<div><b>${esc(r[labelKey])}</b><div class="bar-row"><span>Abiertos</span><div class="bar-track"><div class="bar-fill bar-open" style="width:${Math.round((r.open||0)*100/max)}%"></div></div><span>${r.open||0}</span></div><div class="bar-row"><span>Cerrados</span><div class="bar-track"><div class="bar-fill bar-closed" style="width:${Math.round((r.closed||0)*100/max)}%"></div></div><span>${r.closed||0}</span></div></div>`).join('')||'<div class="muted">Sin datos.</div>'}
function downloadSvgChart(title,rows,labelKey,filename){
    const max=Math.max(1,...rows.map(r=>Math.max(r.open||0,r.closed||0))),w=900,rowH=54,h=70+rows.length*rowH;
    const escXml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
    let y=50,svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="100%" height="100%" fill="white"/><text x="20" y="28" font-size="20" font-family="Arial">${escXml(title)}</text>`;
    rows.forEach(r=>{const label=escXml(r[labelKey]),ow=Math.round((r.open||0)*500/max),cw=Math.round((r.closed||0)*500/max);svg+=`<text x="20" y="${y}" font-size="12" font-family="Arial">${label}</text><rect x="230" y="${y-13}" width="${ow}" height="14" fill="#d99032"/><text x="${240+ow}" y="${y-2}" font-size="11" font-family="Arial">Abiertos ${r.open||0}</text><rect x="230" y="${y+8}" width="${cw}" height="14" fill="#3a9b68"/><text x="${240+cw}" y="${y+19}" font-size="11" font-family="Arial">Cerrados ${r.closed||0}</text>`;y+=rowH});svg+='</svg>';
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
async function reportsView(){
    LIVE_VIEW='reports';LIVE_CHAT_ID=null;hideSimulator();err('');
    try{
        const companies=COMPANY_ROWS.length?COMPANY_ROWS:await api('/api/empresas/listar');
        const id=currentCompanyId();const q=id?'?company_id='+encodeURIComponent(id):'';
        const [summary,tickets]=await Promise.all([api('/api/reportes/resumen'+q),api('/api/tickets'+q)]);
        $('content').innerHTML=`<div class="section-title"><div><h2>Reportes de atención</h2><div class="muted">${esc(COMPANY_CONTEXT.name)}</div></div><div class="toolbar"><button id="downloadGeneralReport">Descargar reporte general CSV</button></div></div><div class="card"><div class="toolbar"><span class="badge">Abiertos: ${summary.totals.open}</span><span class="badge">Cerrados: ${summary.totals.closed}</span><span class="badge">Total: ${summary.totals.total}</span></div></div><div class="reports-grid"><div class="report-chart"><div class="section-title"><h3>Casos por empresa</h3><button id="downloadCompanyChart">Descargar gráfica</button></div>${chartRows(summary.companies,'company_name')}</div><div class="report-chart"><div class="section-title"><h3>Casos por tienda</h3><button id="downloadStoreChart">Descargar gráfica</button></div>${chartRows(summary.stores,'store_name')}</div></div><div class="card ticket-table"><h3>Tickets</h3><table><thead><tr><th>Ticket</th><th>Empresa</th><th>Tienda</th><th>Estado</th><th>Apertura</th><th>Cierre</th><th>Reporte</th></tr></thead><tbody>${tickets.map(t=>`<tr><td>${esc(t.code)}</td><td>${esc(t.company_name)}</td><td>${esc(t.store_name)}</td><td>${esc(t.status)}</td><td>${esc(t.opened_at||'')}</td><td>${esc(t.closed_at||'')}</td><td><button class="ticketReport" data-ticket="${t.id}">Descargar</button></td></tr>`).join('')}</tbody></table></div>`;
        $('downloadGeneralReport').onclick=()=>{location.href='/api/reportes/general.csv'+q};
        $('downloadCompanyChart').onclick=()=>downloadSvgChart('Casos por empresa',summary.companies,'company_name','casos_por_empresa.svg');
        $('downloadStoreChart').onclick=()=>downloadSvgChart('Casos por tienda',summary.stores,'store_name','casos_por_tienda.svg');
        document.querySelectorAll('.ticketReport').forEach(b=>b.onclick=()=>{location.href='/api/tickets/'+b.dataset.ticket+'/reporte.csv'});
    }catch(x){err(x.message)}
}
document.addEventListener('DOMContentLoaded',()=>{if($('navReports'))$('navReports').onclick=reportsView});
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", patch + "\ndocument.addEventListener('DOMContentLoaded'", 1)
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_operations():
    return _html()


@router.get('/dashboard.js')
def dashboard_operations_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
