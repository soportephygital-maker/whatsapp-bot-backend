# Phygital WhatsApp Bot Backend

Backend FastAPI multiempresa con autenticación JWT, persistencia SQL y webhook para WhatsApp Cloud API.

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Por defecto usa SQLite para desarrollo. En Render configura `DATABASE_URL` con PostgreSQL.

## Variables de entorno

- `DATABASE_URL`
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_API_VERSION`
- `WHATSAPP_SEND_ENABLED`
- `WHATSAPP_ALLOWED_NUMBERS`
- `ALLOWED_ORIGINS`

## Activación segura de WhatsApp

El envío está bloqueado por defecto:

```text
WHATSAPP_SEND_ENABLED=false
WHATSAPP_ALLOWED_NUMBERS=
```

Para una prueba controlada, agrega únicamente los números autorizados en formato internacional y activa el envío:

```text
WHATSAPP_SEND_ENABLED=true
WHATSAPP_ALLOWED_NUMBERS=5215512345678,5215587654321
```

Mientras exista una lista blanca, cualquier otro destinatario será bloqueado aunque el webhook reciba mensajes correctamente. No uses `*` en producción salvo que se haya aprobado explícitamente habilitar respuestas para todos los clientes.

En producción `WHATSAPP_APP_SECRET` es obligatorio para aceptar webhooks firmados por Meta. Los mensajes entrantes con `phone_number_id` desconocido son ignorados y auditados. Los `provider_message_id` son únicos para evitar procesar dos veces un mismo mensaje.

## Rutas principales

- `GET /health`
- `POST /api/auth/login`
- `POST /api/auth/crear-usuario`
- `GET /api/empresas/listar`
- `POST /api/empresas/crear`
- `GET /api/empresas/{company_key}/arbol`
- `PUT /api/empresas/{company_key}/arbol`
- `GET /api/stats`
- `GET /api/conversaciones`
- `GET|POST /webhooks/whatsapp`

## Pruebas

```bash
pip install pytest
pytest -q
```

GitHub Actions ejecuta las pruebas automáticamente en cada push a la rama de trabajo y en pull requests.

## Seguridad

No guardes contraseñas, tokens de Meta ni secretos JWT en GitHub. Configúralos como variables privadas en Render.
