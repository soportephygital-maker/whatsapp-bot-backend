from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .operations_dashboard_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-tree-zoom'])
UI_VERSION = '2026.08.28-38'


def _html() -> str:
    html = base_html()
    for old in ('2026.08.28-37', '2026.08.28-36', '2026.08.28-35'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    html = html.replace(
        '</style></head>',
        '''<style>
#decisionFlowCard{position:relative;overflow:hidden!important}
#decisionFlowCard .section-title{position:relative;z-index:5}
#decisionFlow{position:relative;overflow:auto!important;max-width:100%;min-height:420px;padding:24px!important;background:rgba(2,8,18,.28);border-radius:14px;scrollbar-width:thin}
#decisionFlow .live-tree{transform-origin:top center;will-change:transform;transition:transform .16s ease}
.tree-view-toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.tree-view-toolbar button{width:auto;min-width:42px}.tree-zoom-label{font-size:12px;min-width:52px;text-align:center;color:#9fc6e4}
#decisionFlowCard.tree-fullscreen{position:fixed!important;inset:12px!important;z-index:5000!important;margin:0!important;background:#06101d!important;border:1px solid rgba(76,182,255,.55)!important;display:flex!important;flex-direction:column!important;padding:16px!important;max-width:none!important;width:auto!important;height:auto!important}
#decisionFlowCard.tree-fullscreen #decisionFlow{flex:1!important;min-height:0!important;max-height:none!important;background:#030913!important}
#decisionFlowCard.tree-fullscreen .live-tree-wrap{height:100%!important}
body.tree-fullscreen-open{overflow:hidden!important}
.tree-pan-hint{font-size:11px;color:#7fa5c4;margin-top:5px}.tree-fit-warning{font-size:11px;color:#ffca7a;margin-top:5px}
@media(max-width:800px){#decisionFlow{min-height:360px;padding:12px!important}.tree-view-toolbar{width:100%}.tree-view-toolbar button{flex:1}}
</style></head>''',
    )
    return html


def _js() -> str:
    js = base_js()
    patch = r'''
let TREE_ZOOM=1;
let TREE_USER_ZOOM=false;

function treeCanvas(){return $('decisionFlow')}
function treeContent(){return treeCanvas()?.querySelector('.live-tree')||null}
function treeZoomLabel(){return $('treeZoomLabel')}
function applyTreeZoom(value,remember=true){
    const tree=treeContent(),host=treeCanvas();if(!tree||!host)return;
    TREE_ZOOM=Math.max(.18,Math.min(1.8,Number(value)||1));
    if(remember)TREE_USER_ZOOM=true;
    tree.style.transform=`scale(${TREE_ZOOM})`;
    const naturalH=Number(tree.dataset.naturalHeight||tree.scrollHeight||0);
    tree.style.marginBottom=`${Math.max(0,naturalH*TREE_ZOOM-naturalH)}px`;
    if(treeZoomLabel())treeZoomLabel().textContent=Math.round(TREE_ZOOM*100)+'%';
}
function fitDecisionTree(force=false){
    const host=treeCanvas(),tree=treeContent();if(!host||!tree)return;
    tree.style.transform='none';tree.style.marginBottom='0';
    const width=Math.max(tree.scrollWidth,tree.getBoundingClientRect().width,1);
    const available=Math.max(host.clientWidth-40,280);
    const scale=Math.min(1,available/width);
    tree.dataset.naturalHeight=String(tree.scrollHeight||tree.getBoundingClientRect().height||0);
    if(force||!TREE_USER_ZOOM)applyTreeZoom(Math.max(.22,scale),false);
}
function treeZoomIn(){applyTreeZoom(TREE_ZOOM+.1)}
function treeZoomOut(){applyTreeZoom(TREE_ZOOM-.1)}
function treeZoomReset(){TREE_USER_ZOOM=false;fitDecisionTree(true)}
function toggleTreeFullscreen(){
    const card=$('decisionFlowCard');if(!card)return;
    const full=!card.classList.contains('tree-fullscreen');
    card.classList.toggle('tree-fullscreen',full);document.body.classList.toggle('tree-fullscreen-open',full);
    const b=$('treeFullscreenBtn');if(b)b.textContent=full?'Salir de pantalla completa':'Pantalla completa';
    setTimeout(()=>{TREE_USER_ZOOM=false;fitDecisionTree(true)},80);
}
function ensureTreeControls(){
    const card=$('decisionFlowCard');if(!card||$('treeViewToolbar'))return;
    const title=card.querySelector('.section-title');if(!title)return;
    const existing=title.querySelector('.flow-toolbar');if(existing)existing.remove();
    title.insertAdjacentHTML('beforeend',`<div id="treeViewToolbar" class="tree-view-toolbar"><button id="treeZoomOut" title="Alejar">−</button><span id="treeZoomLabel" class="tree-zoom-label">100%</span><button id="treeZoomIn" title="Acercar">+</button><button id="treeFitBtn">Ajustar</button><button id="treeFullscreenBtn">Pantalla completa</button></div>`);
    $('treeZoomOut').onclick=treeZoomOut;$('treeZoomIn').onclick=treeZoomIn;$('treeFitBtn').onclick=treeZoomReset;$('treeFullscreenBtn').onclick=toggleTreeFullscreen;
    const sub=card.querySelector('.muted');if(sub)sub.insertAdjacentHTML('afterend','<div class="tree-pan-hint">Usa Ajustar para ver el árbol completo. Puedes desplazarte horizontalmente y hacer clic en cualquier nodo para editarlo.</div>');
    const host=treeCanvas();if(host){host.addEventListener('wheel',e=>{if(!e.ctrlKey)return;e.preventDefault();applyTreeZoom(TREE_ZOOM+(e.deltaY<0?.08:-.08))},{passive:false});}
}
const _renderDecisionFlowZoom=renderDecisionFlow;
renderDecisionFlow=function(){
    _renderDecisionFlowZoom();ensureTreeControls();
    requestAnimationFrame(()=>requestAnimationFrame(()=>{TREE_USER_ZOOM=false;fitDecisionTree(true)}));
};
window.addEventListener('resize',()=>{clearTimeout(window.__treeResizeTimer);window.__treeResizeTimer=setTimeout(()=>{if(!TREE_USER_ZOOM)fitDecisionTree(true)},120)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('decisionFlowCard')?.classList.contains('tree-fullscreen'))toggleTreeFullscreen()});
'''
    js = js.replace("document.addEventListener('DOMContentLoaded'", patch + "\ndocument.addEventListener('DOMContentLoaded'")
    return js


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_tree_zoom():
    return _html()


@router.get('/dashboard.js')
def dashboard_tree_zoom_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control': 'no-store'})
