from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import AuditLog, Company, GlobalSetting, User
from ..services.company_routing import normalize
from ..services.coppel_tree import coppel_decision_tree

router = APIRouter(prefix='/api/empresas', tags=['coppel-support'])
COPPEL_TEMPLATE_MARKER = 'coppel_support_tree_v1_applied'


def _looks_like_coppel(company: Company) -> bool:
    text = normalize(f'{company.company_key} {company.name}')
    return 'coppel' in text


def ensure_coppel_template(db: Session) -> bool:
    marker = db.get(GlobalSetting, COPPEL_TEMPLATE_MARKER)
    if marker and isinstance(marker.value, dict) and marker.value.get('applied'):
        return False
    changed = False
    applied_ids = []
    for company in db.query(Company).all():
        if not _looks_like_coppel(company):
            continue
        company.decision_tree = coppel_decision_tree()
        applied_ids.append(company.id)
        changed = True
    if changed:
        if marker:
            marker.value = {'applied': True, 'company_ids': applied_ids, 'version': 1}
            marker.updated_by = 'system'
        else:
            db.add(GlobalSetting(key=COPPEL_TEMPLATE_MARKER, value={'applied': True, 'company_ids': applied_ids, 'version': 1}, updated_by='system'))
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
    db.add(AuditLog(username=admin.username, action='aplicar_plantilla_coppel', entity='company', entity_id=company_key, details={'template': 'coppel_support_v1'}))
    db.commit()
    return {'status': 'ok', 'structure': company.decision_tree}
