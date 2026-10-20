import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_csv(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, '').split(',') if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', 'Phygital WhatsApp Bot Backend')
    environment: str = os.getenv('ENVIRONMENT', 'development')
    jwt_secret: str = os.getenv('JWT_SECRET', 'change-me-in-production')
    jwt_algorithm: str = 'HS256'
    access_token_minutes: int = int(os.getenv('ACCESS_TOKEN_MINUTES', '43200'))
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///./phygital.db')
    whatsapp_verify_token: str = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
    whatsapp_access_token: str = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    whatsapp_app_secret: str = os.getenv('WHATSAPP_APP_SECRET', '')
    whatsapp_phone_number_id: str = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    whatsapp_api_version: str = os.getenv('WHATSAPP_API_VERSION', 'v23.0')
    whatsapp_send_enabled: bool = _env_bool('WHATSAPP_SEND_ENABLED', False)
    whatsapp_test_mode: bool = _env_bool('WHATSAPP_TEST_MODE', True)
    whatsapp_allowed_numbers: tuple[str, ...] = _env_csv('WHATSAPP_ALLOWED_NUMBERS')
    smtp_host: str = os.getenv('SMTP_HOST', '')
    smtp_port: int = int(os.getenv('SMTP_PORT', '587'))
    smtp_username: str = os.getenv('SMTP_USERNAME', '')
    smtp_password: str = os.getenv('SMTP_PASSWORD', '')
    smtp_from_email: str = os.getenv('SMTP_FROM_EMAIL', '')
    smtp_from_name: str = os.getenv('SMTP_FROM_NAME', 'Phygital Bot')
    smtp_use_tls: bool = _env_bool('SMTP_USE_TLS', True)
    smtp_use_ssl: bool = _env_bool('SMTP_USE_SSL', False)
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-5.6-luna')
    ai_learning_enabled: bool = _env_bool('AI_LEARNING_ENABLED', False)
    # AI_PROVIDER: auto | openai | ollama | retrieval
    # - auto: uses OpenAI when a key exists, otherwise Ollama when configured,
    #   otherwise safe retrieval-only mode.
    # - ollama: self-hosted/local generative model; no OpenAI API key required.
    ai_provider: str = os.getenv('AI_PROVIDER', 'auto').strip().lower()
    ai_local_base_url: str = os.getenv('AI_LOCAL_BASE_URL', '').rstrip('/')
    ai_local_model: str = os.getenv('AI_LOCAL_MODEL', 'qwen2.5:7b-instruct')
    ai_local_timeout_seconds: int = int(os.getenv('AI_LOCAL_TIMEOUT_SECONDS', '60'))
    ai_retrieval_limit: int = int(os.getenv('AI_RETRIEVAL_LIMIT', '12'))
    allowed_origins: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv('ALLOWED_ORIGINS', '*').split(',') if x.strip()
    ) or ('*',)


settings = Settings()
