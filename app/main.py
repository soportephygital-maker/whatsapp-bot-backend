import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from .config import settings
from .database import Base, SessionLocal, engine
from .models import Company, Store
from .routers import access_control, auth, case_event_policy_patch, case_management_patch, companies, company_delete_safe, company_resources, contacts, conversation_admin, conversation_visibility_patch, coppel_support, dashboard, dashboard_ai_neural_patch, dashboard_fullscreen_support_patch, dashboard_patch, dashboard_permission_visibility_patch, dashboard_role_redesign_patch, dashboard_ui, flow_simulator_dashboard_patch, global_entry, global_entry_dashboard_patch, global_entry_sequence_patch, iqos_support, local_bridge, login_recovery_dashboard_patch, manager_patch, mobile_update, operations_dashboard_patch, report_download_dashboard_patch, routing_dashboard_patch, settings as settings_router, super_admin, support_email_bridge, support_tickets, ticketed_case_close, ticketed_local_bridge, tree_editor_patch, tree_zoom_dashboard_patch, whatsapp
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
app.include_router(super_admin.router)
app.include_router(access_control.router)
app.include_router(company_delete_safe.router)
app.include_router(iqos_support.router)
app.include_router(coppel_support.router)
# Case management is registered before the legacy ticket router so the enhanced
# seguimiento endpoint owns status-change email notifications.
app.include_router(case_management_patch.router)
app.include_router(support_tickets.router)
app.include_router(support_email_bridge.router)
app.include_router(companies.router)
app.include_router(company_resources.router)
app.include_router(contacts.router)
app.include_router(ticketed_case_close.router)
app.include_router(conversation_admin.router)
app.include_router(conversation_visibility_patch.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(global_entry.router)
# The Super Admin AI layer owns /dashboard and /dashboard.js while wrapping all
# prior role/permission-aware dashboard behavior.
app.include_router(dashboard_ai_neural_patch.router)
app.include_router(dashboard_permission_visibility_patch.router)
app.include_router(dashboard_role_redesign_patch.router)
app.include_router(dashboard_fullscreen_support_patch.router)
app.include_router(login_recovery_dashboard_patch.router)
app.include_router(tree_zoom_dashboard_patch.router)
app.include_router(report_download_dashboard_patch.router)
app.include_router(operations_dashboard_patch.router)
app.include_router(flow_simulator_dashboard_patch.router)
app.include_router(global_entry_dashboard_patch.router)
app.include_router(routing_dashboard_patch.router)
app.include_router(tree_editor_patch.router)
app.include_router(manager_patch.router)
app.include_router(dashboard_patch.router)
app.include_router(dashboard_ui.router)
# This wrapper owns /api/local-bridge/inbound so the first unidentified contact
# always receives the greeting; the unmatched-company message is only used after
# the greeting has already been sent and the next client response is still unclear.
app.include_router(global_entry_sequence_patch.router)
app.include_router(ticketed_local_bridge.router)
app.include_router(local_bridge.router)
app.include_router(mobile_update.router)
app.include_router(whatsapp.router)

_escalation_thread_started = False


def _public_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - Phygital Bot</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;max-width:850px;margin:40px auto;padding:0 20px;line-height:1.6;color:#1f2937}}h1,h2{{color:#111827}}a{{color:#2563eb}}</style></head>
<body><h1>{title}</h1>{body}<p><small>Última actualización: 21 de agosto de 2026.</small></p></body></html>''')


@app.get('/privacy', response_class=HTMLResponse)
def privacy_policy():
    return _public_page('Política de privacidad', '''
<p>Phygital Bot es una herramienta de atención y soporte operada para Grupoedm. Esta política explica el tratamiento de información cuando una persona interactúa con el servicio mediante WhatsApp, el panel web o la aplicación móvil asociada.</p>
<h2>Información que podemos tratar</h2>
<p>Podemos tratar el nombre mostrado por WhatsApp, el contenido visible en las notificaciones autorizadas por el usuario del dispositivo, identificadores técnicos locales, la empresa o tienda asociada a la conversación, solicitudes de soporte y datos necesarios para dar seguimiento al caso. Para usuarios internos también podemos tratar identificadores de sesión, rol y registros de actividad administrativa.</p>
<h2>Finalidades</h2>
<p>Usamos la información para recibir y enrutar solicitudes, responder consultas mediante las acciones de respuesta disponibles en Android, escalar casos a personal de soporte, mantener historial operativo, proteger el servicio y mejorar su funcionamiento.</p>
<h2>Proveedores y transferencias</h2>
<p>El servicio utiliza infraestructura de alojamiento necesaria para operar el backend. El acceso a notificaciones de WhatsApp se concede explícitamente desde Android y puede revocarse en cualquier momento. No vendemos datos personales.</p>
<h2>Conservación y seguridad</h2>
<p>La información se conserva únicamente durante el tiempo necesario para fines operativos, de soporte, seguridad y cumplimiento aplicable. Aplicamos controles de acceso y medidas técnicas razonables para protegerla.</p>
<h2>Derechos y contacto</h2>
<p>Para solicitar acceso, corrección o eliminación de información relacionada con Phygital Bot, escribe a <a href="mailto:bernabe.lopez@grupoedm.com.mx">bernabe.lopez@grupoedm.com.mx</a>.</p>
''')


@app.get('/terms', response_class=HTMLResponse)
def terms_of_service():
    return _public_page('Condiciones del servicio', '''
<p>Phygital Bot proporciona funciones de atención, clasificación y seguimiento de solicitudes relacionadas con servicios y operaciones de Grupoedm y sus proyectos autorizados.</p>
<p>La integración local de Android depende de que el propietario del dispositivo conceda acceso a notificaciones. Las respuestas automáticas solo pueden enviarse cuando WhatsApp publica una acción de respuesta compatible en la notificación.</p>
<p>El servicio puede modificarse o suspenderse temporalmente por mantenimiento o por cambios de Android o WhatsApp.</p>
<p>Para consultas sobre estas condiciones, escribe a <a href="mailto:bernabe.lopez@grupoedm.com.mx">bernabe.lopez@grupoedm.com.mx</a>.</p>
''')


@app.get('/data-deletion', response_class=HTMLResponse)
def data_deletion():
    return _public_page('Eliminación de datos', '''
<p>Si deseas solicitar la eliminación de datos asociados a una interacción con Phygital Bot, envía un correo a <a href="mailto:bernabe.lopez@grupoedm.com.mx">bernabe.lopez@grupoedm.com.mx</a> con el asunto <strong>Solicitud de eliminación de datos - Phygital Bot</strong>.</p>
<p>Incluye el identificador relacionado con la solicitud y una descripción breve de los datos que deseas eliminar. Podemos solicitar una verificación razonable de identidad antes de ejecutar la eliminación para evitar solicitudes fraudulentas.</p>
<p>Una vez verificada la solicitud, eliminaremos o anonimizaremos los datos que correspondan, salvo aquellos que deban conservarse por obligaciones legales, seguridad o prevención de fraude.</p>
''')


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
        super_admin._ensure_core_users(db)

        if not db.query(Company).first():
            company = Company(company_key='empresa_demo', name='Empresa Demo Phygital', decision_tree={
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
            })
            db.add(company)
            db.flush()
            db.add(Store(company_id=company.id, name='Principal'))
            db.commit()

        changed = False
        for company in db.query(Company).all():
            if not company.stores:
                db.add(Store(company_id=company.id, name='Principal'))
                changed = True
        if changed:
            db.commit()

        iqos_support.ensure_iqos_template(db)
        coppel_support.ensure_coppel_template(db)
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
    return {
        'name': settings.app_name,
        'status': 'running',
        'health': '/health',
        'dashboard': '/dashboard',
        'primary_transport': 'android_notification',
        'webhook': '/webhook',
    }
