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
- `ALLOWED_ORIGINS`

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

## Seguridad

No guardes contraseñas, tokens de Meta ni secretos JWT en GitHub. Configúralos como variables privadas en Render.
