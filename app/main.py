from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import Base, SessionLocal, engine
from .models import Company, User
from .auth import hash_password
from .routers import auth, companies, contacts, dashboard, dashboard_ui, whatsapp

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
app.include_router(contacts.router)
app.include_router(dashboard.router)
app.include_router(dashboard_ui.router)
app.include_router(whatsapp.router)


@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).first():
            username = __import__('os').getenv('BOOTSTRAP_ADMIN_USERNAME')
            password = __import__('os').getenv('BOOTSTRAP_ADMIN_PASSWORD')
            if username and password:
                db.add(User(username=username, password_hash=hash_password(password), role='admin'))
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
