import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from .config import settings
from .database import Base, SessionLocal, engine
from .models import AuditLog, Company, Store, User
from .auth import hash_password, verify_password
from .routers import auth, companies, company_resources, contacts, conversation_admin, dashboard, dashboard_patch, dashboard_ui, local_bridge, manager_patch, mobile_update, settings as settings_router, whatsapp
from .services.escalation import process_help_escalations

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=settings.allowed_origins != ('*',),
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(company_resources.router)
app.include_router(contacts.router)
app.include_router(conversation_admin.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(manager_patch.router)
app.include_router(dashboard_patch.router)
app.include_router(dashboard_ui.router)
app.include_router(local_bridge.router)
app.include_router(mobile_update.router)
app.include_router(whatsapp.router)

_escalation_thread_started = False


def _public_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} - Phygital Bot</title><style>body{{font-family:system-ui,-apple-system,sans-serif;max-width:850px;margin:40px auto;padding:0 20px;line-height:1.6;color:#1f2937}}h1,h2{{color:#111827}}a{{color:#2563eb}}</style></head><body><h1>{title}</h1>{body}<p><small>Última actualización: 21 de agosto de 2026.</small></p></body></html>''')


@app.get('/privacy', response_class=HTMLResponse)
def privacy_policy():
    return _public_page('Política de privacidad', '<p>Phygital Bot es una herramienta de atención y soporte operada para Grupoedm.</p>')


@app.get('/terms', response_class=HTMLResponse)
def terms_of_service():
    return _public_page('Condiciones del servicio', '<p>Phygital Bot proporciona funciones de atención, clasificación y seguimiento de solicitudes relacionadas con servicios y operaciones autorizadas.</p>')


@app.get('/data-deletion', response_class=HTMLResponse)
def data_deletion():
    return _public_page('Eliminación de datos', '<p>Para solicitar eliminación de datos relacionados con Phygital Bot, contacta al responsable del servicio.</p>')


def _escalation_loop():
    while True:
        time.sleep(60)
        db = SessionLocal()
        try:
            process_help_escalations(db)
        except Exception:
            db.rollback()
        finally:
            db.close()


@app.on_event('startup')
def startup():
    global _escalation_thread_started
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        username = __import__('os').getenv('BOOTSTRAP_ADMIN_USERNAME')
        password = __import__('os').getenv('BOOTSTRAP_ADMIN_PASSWORD')
        if username and password:
            admin = db.query(User).filter(User.username == username).first()
            if not admin:
                admin = User(username=username, password_hash=hash_password(password), role='admin', is_active=True)
                db.add(admin)
                db.commit()
            else:
                changed = False
                if not verify_password(password, admin.password_hash):
                    admin.password_hash = hash_password(password); changed = True
                if admin.role != 'admin':
                    admin.role = 'admin'; changed = True
                if not admin.is_active:
                    admin.is_active = True; changed = True
                if changed:
                    db.commit()
            other_admins = db.query(User).filter(User.username != username, User.role == 'admin').all()
            if other_admins:
                for row in other_admins:
                    row.role = 'operador'
                db.commit()
            # The primary administrator is intentionally invisible in activity.
            db.query(AuditLog).filter(AuditLog.username == username).delete(synchronize_session=False)
            db.commit()

        if not db.query(Company).first():
            company = Company(company_key='empresa_demo', name='Empresa Demo Phygital', decision_tree={'nodo_raiz':'inicio','nodos':{'inicio':{'mensaje':'Bienvenido. Elige una opción: 1) Soporte 2) Información','opciones':[{'comando':'1','respuesta':'Cuéntame brevemente tu problema.','siguiente':'soporte'},{'comando':'2','respuesta':'¿Qué información necesitas?','siguiente':'informacion'}]},'soporte':{'mensaje':'Describe el problema y un operador podrá darle seguimiento.','opciones':[]},'informacion':{'mensaje':'Escribe tu consulta.','opciones':[]}}})
            db.add(company); db.flush(); db.add(Store(company_id=company.id, name='Principal')); db.commit()
        changed = False
        for company in db.query(Company).all():
            if not company.stores:
                db.add(Store(company_id=company.id, name='Principal')); changed = True
        if changed: db.commit()
    finally:
        db.close()
    if settings.environment.lower() == 'production' and not _escalation_thread_started:
        _escalation_thread_started = True
        threading.Thread(target=_escalation_loop, name='support-escalations', daemon=True).start()


@app.get('/health')
def health():
    return {'status': 'ok', 'environment': settings.environment, 'primary_transport': 'android_notification'}


@app.get('/')
def root():
    return {'name': settings.app_name, 'status': 'running', 'health': '/health', 'dashboard': '/dashboard', 'docs': '/docs', 'local_bridge': '/api/local-bridge/inbound', 'legacy_whatsapp_webhook': '/webhooks/whatsapp', 'mobile_update': '/api/mobile/update', 'privacy': '/privacy', 'terms': '/terms', 'data_deletion': '/data-deletion'}
