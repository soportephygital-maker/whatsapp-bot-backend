import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', 'Phygital WhatsApp Bot Backend')
    environment: str = os.getenv('ENVIRONMENT', 'development')
    jwt_secret: str = os.getenv('JWT_SECRET', 'change-me-in-production')
    jwt_algorithm: str = 'HS256'
    access_token_minutes: int = int(os.getenv('ACCESS_TOKEN_MINUTES', '720'))
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///./phygital.db')
    whatsapp_verify_token: str = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
    whatsapp_access_token: str = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    whatsapp_app_secret: str = os.getenv('WHATSAPP_APP_SECRET', '')
    whatsapp_phone_number_id: str = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    whatsapp_api_version: str = os.getenv('WHATSAPP_API_VERSION', 'v23.0')
    allowed_origins: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv('ALLOWED_ORIGINS', '*').split(',') if x.strip()
    ) or ('*',)

settings = Settings()
