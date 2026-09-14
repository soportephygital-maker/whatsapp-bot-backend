from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..services import case_report_runtime_patch  # noqa: F401 - applies report contact sanitization at startup
from . import dashboard_image_gallery_patch, image_evidence_listo_patch, image_evidence_patch

router = APIRouter(tags=['dashboard-ui-email-milestone'])
# IMPORTANT: do not include dashboard_image_gallery_patch.router here.
# That router defines its own /dashboard and /dashboard.js (UI 87). If it is
# included before the routes below, FastAPI resolves the legacy UI first.
# We still reuse dashboard_image_gallery_patch._html()/_js() as the content base.
router.include_router(image_evidence_listo_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-95'


def _html() -> str:
    html = dashboard_image_gallery_patch._html()
    for old in (
        '2026.09.04-83', '2026.09.04-84', '2026.09.04-85',
        '2026.09.04-86', '2026.09.04-87', '2026.09.04-88',
        '2026.09.04-89', '2026.09.04-90', '2026.09.04-91',
        '2026.09.04-92', '2026.09.04-93', '2026.09.04-94',
    ):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


def _js() -> str:
    return dashboard_image_gallery_patch._js()


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return HTMLResponse(
        _html(),
        headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'},
    )


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(
        _js(),
        media_type='application/javascript',
        headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'},
    )
