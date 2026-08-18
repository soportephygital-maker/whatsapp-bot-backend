import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import Base, SessionLocal, engine
from .models import Company, User
from .auth import hash_password, verify_password
from .routers import auth, companies, company_resources, contacts, dashboard, dashboard_patch, dashboard_ui, whatsapp
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
app.include_router(dashboard.router)
app.include_router(dashboard_patch.router)
app.include_router(dashboard_ui.router)
app.include_router(whatsapp.router)

_escalation_thread_started = False


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
                    admin.password_hash = hash_password(password)
                    changed = True
                if admin.role != 'admin':
                    admin.role = 'admin'
                    changed = True
                if not admin.is_active:
                    admin.is_active = True
                    changed = True
                if changed:
                    db.commit()

            other_admins = db.query(User).filter(User.username != username, User.role == 'admin').all()
            if other_admins:
                for row in other_admins:
                    row.role = 'operador'
                db.commit()

        if not db.query(Company).first():
            db.add(Company(company_key='empresa_demo', name='Empresa Demo Phygital', decision_tree={
                'nodo_raiz': 'inicio',
                'nodos': {
                    'inicio': {
                        'mensaje': 'Bienvenido. Elige una opción: 1) Soporte 2) Información',
                        'opciones': [
                            {'comando': '1', 'respuesta': 'Cuéntame brevemente tu problema.', 'siguiente': 'soporte'},
                            {'comando': '2', 'respuesta': '¿Qué información necesitas?', 'siguiente': 'informacion'},
                        ],
                    },
                    'soporte': {'mensaje': 'Describe el problema y un operador podrá darle seguimiento.', 'opciones': []},
                    'informacion': {'mensaje': 'Escribe tu consulta.', 'opciones': []},
                },
            }))
            db.commit()
    finally:
        db.close()

    if settings.environment.lower() == 'production' and not _escalation_thread_started:
        _escalation_thread_started = True
        threading.Thread(target=_escalation_loop, name='support-escalations', daemon=True).start()


@app.get('/health')
def health():
    return {'status': 'ok', 'environment': settings.environment}


@app.get('/')
def root():
    return {
        'name': settings.app_name,
        'status': 'running',
        'health': '/health',
        'dashboard': '/dashboard',
        'docs': '/docs',
        'whatsapp_webhook': '/webhooks/whatsapp',
    }
