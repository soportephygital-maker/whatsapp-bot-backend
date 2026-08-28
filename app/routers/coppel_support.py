from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import AuditLog, Company, GlobalSetting, User
from ..services.company_routing import normalize
from ..services.coppel_tree import coppel_decision_tree

router = APIRouter(prefix='/api/empresas', tags=['coppel-support'])
COPPEL_TEMPLATE_MARKER = 'coppel_support_tree_v2_applied'
COPPEL_TEMPLATE_VERSION = 2


def _looks_like_coppel(company: Company) -> bool:
    text = normalize(f'{company.company_key} {company.name}')
    return 'coppel' in text


def ensure_coppel_template(db: Session) -> bool:
    """Apply the current Coppel support tree once to every detected Coppel company.

    The marker stores company ids already upgraded to this template version. This
    lets a Coppel company created later receive the template on the next deploy
    without overwriting companies already edited after the template was applied.
    """
    marker = db.get(GlobalSetting, COPPEL_TEMPLATE_MARKER)
    marker_value = marker.value if marker and isinstance(marker.value, dict) else {}
    applied_ids = {int(value) for value in marker_value.get('company_ids', []) if str(value).isdigit()}
    changed = False

    for company in db.query(Company).all():
        if not _looks_like_coppel(company) or company.id in applied_ids:
            continue
        company.decision_tree = coppel_decision_tree()
        applied_ids.add(company.id)
        changed = True
        db.add(AuditLog(
            action='aplicar_plantilla_coppel_automatica',
            entity='company',
            entity_id=str(company.id),
            details={'company_key': company.company_key, 'template': 'coppel_support_v2'},
        ))

    if changed or not marker:
        value = {
            'applied': bool(applied_ids),
            'company_ids': sorted(applied_ids),
            'version': COPPEL_TEMPLATE_VERSION,
        }
        if marker:
            marker.value = value
            marker.updated_by = 'system'
        else:
            db.add(GlobalSetting(key=COPPEL_TEMPLATE_MARKER, value=value, updated_by='system'))
        db.commit()
    return changed


@router.post('/{company_key}/plantilla-coppel-v1')
def apply_coppel_template(
    company_key: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.company_key == company_key).first()
    if not company:
        raise HTTPException(status_code=404, detail='Empresa no encontrada')
    company.decision_tree = coppel_decision_tree()
    db.add(AuditLog(username=admin.username, action='aplicar_plantilla_coppel', entity='company', entity_id=company_key, details={'template': 'coppel_support_v2'}))
    db.commit()
    return {'status': 'ok', 'structure': company.decision_tree}
