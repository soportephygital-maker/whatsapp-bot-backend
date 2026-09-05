from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .operations_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-report-downloads'])
UI_VERSION = '2026.09.02-49'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-37', '2026.08.28-36', '2026.08.28-35'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
async function downloadAuthenticatedText(url,filename){
    try{
        const text=await api(url);
        const blob=new Blob([text],{type:'text/csv;charset=utf-8'});
        const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
    }catch(x){err(x.message)}
}
reportsView=async function(){
    LIVE_VIEW='reports';LIVE_CHAT_ID=null;hideSimulator();err('');
    try{
        const id=currentCompanyId();const q=id?'?company_id='+encodeURIComponent(id):'';
        const [summary,tickets]=await Promise.all([api('/api/reportes/resumen'+q),api('/api/tickets'+q)]);
        $('content').innerHTML=`<div class="section-title"><div><h2>Reportes de atención</h2><div class="muted">${esc(COMPANY_CONTEXT.name)}</div></div><div class="toolbar"><button id="downloadGeneralReport">Descargar reporte general CSV</button></div></div><div class="card"><div class="toolbar"><span class="badge">Abiertos: ${summary.totals.open}</span><span class="badge">Cerrados: ${summary.totals.closed}</span><span class="badge">Total: ${summary.totals.total}</span></div></div><div class="reports-grid"><div class="report-chart"><div class="section-title"><h3>Casos por empresa</h3><button id="downloadCompanyChart">Descargar gráfica</button></div>${chartRows(summary.companies,'company_name')}</div><div class="report-chart"><div class="section-title"><h3>Casos por tienda</h3><button id="downloadStoreChart">Descargar gráfica</button></div>${chartRows(summary.stores,'store_name')}</div></div><div class="card ticket-table"><h3>Tickets</h3><table><thead><tr><th>Ticket</th><th>Empresa</th><th>Tienda</th><th>Estado</th><th>Apertura</th><th>Cierre</th><th>Reporte</th></tr></thead><tbody>${tickets.map(t=>`<tr><td>${esc(t.code)}</td><td>${esc(t.company_name)}</td><td>${esc(t.store_name)}</td><td>${esc(t.status)}</td><td>${esc(t.opened_at||'')}</td><td>${esc(t.closed_at||'')}</td><td><button class="ticketReport" data-ticket="${t.id}" data-code="${esc(t.code)}">Descargar</button></td></tr>`).join('')}</tbody></table></div>`;
        $('downloadGeneralReport').onclick=()=>downloadAuthenticatedText('/api/reportes/general.csv'+q,'reporte_general_phygital.csv');
        $('downloadCompanyChart').onclick=()=>downloadSvgChart('Casos por empresa',summary.companies,'company_name','casos_por_empresa.svg');
        $('downloadStoreChart').onclick=()=>downloadSvgChart('Casos por tienda',summary.stores,'store_name','casos_por_tienda.svg');
        document.querySelectorAll('.ticketReport').forEach(b=>b.onclick=()=>downloadAuthenticatedText('/api/tickets/'+b.dataset.ticket+'/reporte.csv',(b.dataset.code||'ticket')+'.csv'));
    }catch(x){err(x.message)}
};

/* Restaurar borrado de conversaciones sin reescribir las vistas actuales. */
async function forgetConversationFromUi(id){
    if(!confirm('¿Eliminar esta conversación definitivamente? También se eliminarán sus mensajes y solicitudes relacionadas.'))return;
    try{
        await api('/api/conversaciones/'+id+'/olvidar',{method:'DELETE'});
        if(typeof invalidateUiCache==='function'){
            invalidateUiCache('/api/conversaciones');
            invalidateUiCache('/api/tickets');
        }
        err('Conversación eliminada.');
        if(typeof conv==='function')await conv(typeof currentCompanyId==='function'?currentCompanyId():null);
    }catch(x){err(x.message)}
}
function installConversationDeleteButtons(){
    const host=$('content');if(!host)return;
    host.querySelectorAll('[data-conv]').forEach(row=>{
        const id=Number(row.dataset.conv);if(!id||row.querySelector('.delete-conversation'))return;
        const b=document.createElement('button');b.className='delete-conversation danger';b.textContent='Eliminar conversación';b.style.width='auto';
        b.onclick=e=>{e.stopPropagation();forgetConversationFromUi(id)};
        const toolbar=row.querySelector('.toolbar');if(toolbar)toolbar.appendChild(b);else row.appendChild(b);
    });
    if(typeof LIVE_CHAT_ID!=='undefined'&&LIVE_CHAT_ID&&!host.querySelector('#deleteCurrentConversation')){
        const back=host.querySelector('#backChats');if(back){
            const b=document.createElement('button');b.id='deleteCurrentConversation';b.className='danger';b.textContent='Eliminar conversación';b.style.width='auto';b.style.marginLeft='8px';
            b.onclick=()=>forgetConversationFromUi(Number(LIVE_CHAT_ID));back.insertAdjacentElement('afterend',b);
        }
    }
}
let DELETE_BUTTON_TIMER=null;
function scheduleConversationDeleteButtons(){clearTimeout(DELETE_BUTTON_TIMER);DELETE_BUTTON_TIMER=setTimeout(installConversationDeleteButtons,40)}
document.addEventListener('DOMContentLoaded',()=>{
    const host=$('content');if(host)new MutationObserver(scheduleConversationDeleteButtons).observe(host,{childList:true,subtree:true});
    scheduleConversationDeleteButtons();
});
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", patch + "\ndocument.addEventListener('DOMContentLoaded'", 1)
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_report_downloads():
    return _html()


@router.get('/dashboard.js')
def dashboard_report_downloads_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'public, max-age=31536000, immutable'})
