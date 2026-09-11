from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from . import dashboard_image_gallery_patch, image_evidence_patch
from .dashboard_ai_training_interpretation_patch import _html as base_html, _js as base_js

router = APIRouter(tags=['dashboard-ui-email-milestone'])
router.include_router(dashboard_image_gallery_patch.router)
router.include_router(image_evidence_patch.router)
UI_VERSION = '2026.09.04-83'


def _html() -> str:
    return dashboard_image_gallery_patch._html()


def _js() -> str:
    return dashboard_image_gallery_patch._js()


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_email_milestone():
    return _html()


@router.get('/dashboard.js')
def dashboard_email_milestone_js():
    return Response(_js(), media_type='application/javascript', headers={'Cache-Control':'public, max-age=31536000, immutable'})
