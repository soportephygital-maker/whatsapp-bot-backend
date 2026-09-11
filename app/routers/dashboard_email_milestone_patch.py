from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from . import dashboard_image_gallery_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
router.include_router(dashboard_image_gallery_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-87'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in ('2026.09.04-83', '2026.09.04-84', '2026.09.04-85', '2026.09.04-86'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    return dashboard_image_gallery_patch._js()


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return HTMLResponse(_html(), headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})
