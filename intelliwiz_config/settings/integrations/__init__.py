"""
Integrations Package - All Third-Party Service Configurations

Exports all external service configurations:
- AWS (SES email, S3 storage)
- GCP (Cloud Storage, Gemini LLM, Google APIs)
- Third-party services (Twilio, LLM providers, MQTT, notifications)

Usage in other settings:
    from .integrations import (
        EMAIL_HOST, EMAIL_PORT,  # AWS
        GCS_BUCKET_NAME,  # GCP
        TWILIO_ACCOUNT_SID,  # Third-party
    )
"""

# Import and re-export AWS configurations
from .aws import (
    EMAIL_BACKEND,
    EMAIL_HOST,
    EMAIL_PORT,
    EMAIL_USE_TLS,
    EMAIL_HOST_USER,
    EMAIL_HOST_PASSWORD,
    DEFAULT_FROM_EMAIL,
    EMAIL_FROM_ADDRESS,
    EMAIL_TOKEN_LIFE,
    EMAIL_MAIL_TOKEN_LIFE,
    EMAIL_MAIL_SUBJECT,
    EMAIL_MAIL_HTML,
    EMAIL_MAIL_PLAIN,
    EMAIL_MAIL_PAGE_TEMPLATE,
    EMAIL_PAGE_DOMAIN,
    EMAIL_MULTI_USER,
    CUSTOM_SALT,
    EMAIL_VERIFIED_CALLBACK,
    EMAIL_MAIL_CALLBACK,
    BUCKET,
    TEMP_REPORTS_GENERATED,
    ONDEMAND_REPORTS_GENERATED,
    DATA_UPLOAD_MAX_MEMORY_SIZE,
)

# Import and re-export GCP configurations
from .gcp import (
    GCS_BUCKET_NAME,
    GCS_PROJECT_ID,
    GCS_CREDENTIALS_PATH,
    GCS_ENABLED,
    GOOGLE_MAP_SECRET_KEY,
    BULK_IMPORT_GOOGLE_DRIVE_API_KEY,
    GOOGLE_API_KEY,
    GEMINI_MODEL_MAKER,
    GEMINI_MODEL_CHECKER,
)

# Import and re-export third-party configurations
from .third_party import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    LLM_PROVIDERS_ENABLED,
    LLM_DEFAULT_FALLBACK_CHAIN,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
    MQTT_CONFIG,
    CLIENT_DOMAINS,
    ENABLE_WEBHOOK_NOTIFICATIONS,
    NOTIFICATION_PROVIDERS,
    NOTIFICATION_ROUTING,
)

__all__ = [
    # AWS
    'EMAIL_BACKEND',
    'EMAIL_HOST',
    'EMAIL_PORT',
    'EMAIL_USE_TLS',
    'EMAIL_HOST_USER',
    'EMAIL_HOST_PASSWORD',
    'DEFAULT_FROM_EMAIL',
    'EMAIL_FROM_ADDRESS',
    'EMAIL_TOKEN_LIFE',
    'EMAIL_MAIL_TOKEN_LIFE',
    'EMAIL_MAIL_SUBJECT',
    'EMAIL_MAIL_HTML',
    'EMAIL_MAIL_PLAIN',
    'EMAIL_MAIL_PAGE_TEMPLATE',
    'EMAIL_PAGE_DOMAIN',
    'EMAIL_MULTI_USER',
    'CUSTOM_SALT',
    'EMAIL_VERIFIED_CALLBACK',
    'EMAIL_MAIL_CALLBACK',
    'BUCKET',
    'TEMP_REPORTS_GENERATED',
    'ONDEMAND_REPORTS_GENERATED',
    'DATA_UPLOAD_MAX_MEMORY_SIZE',
    # GCP
    'GCS_BUCKET_NAME',
    'GCS_PROJECT_ID',
    'GCS_CREDENTIALS_PATH',
    'GCS_ENABLED',
    'GOOGLE_MAP_SECRET_KEY',
    'BULK_IMPORT_GOOGLE_DRIVE_API_KEY',
    'GOOGLE_API_KEY',
    'GEMINI_MODEL_MAKER',
    'GEMINI_MODEL_CHECKER',
    # Third-party
    'ANTHROPIC_API_KEY',
    'OPENAI_API_KEY',
    'LLM_PROVIDERS_ENABLED',
    'LLM_DEFAULT_FALLBACK_CHAIN',
    'TWILIO_ACCOUNT_SID',
    'TWILIO_AUTH_TOKEN',
    'TWILIO_FROM_NUMBER',
    'MQTT_CONFIG',
    'CLIENT_DOMAINS',
    'ENABLE_WEBHOOK_NOTIFICATIONS',
    'NOTIFICATION_PROVIDERS',
    'NOTIFICATION_ROUTING',
]

# ============================================================================
# ENVIRONMENT-SPECIFIC INTEGRATION SETTINGS (Helper Functions)
# ============================================================================

def get_development_integrations():
    """Development-specific integration settings with optimized Redis."""
    from .redis_optimized import get_optimized_caches_config, get_channel_layers_config, get_celery_redis_config

    celery_config = get_celery_redis_config('development')

    return {
        'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend',
        'CELERY_TASK_ALWAYS_EAGER': True,
        'CELERY_TASK_EAGER_PROPAGATES': True,
        'CACHES': get_optimized_caches_config('development'),
        'CHANNEL_LAYERS': get_channel_layers_config('development'),
        'CELERY_BROKER_URL': celery_config['broker_url'],
        'CELERY_RESULT_BACKEND': celery_config['result_backend'],
    }


def get_production_integrations():
    """Production-specific integration settings with optimized Redis."""
    from .redis_optimized import get_optimized_caches_config, get_channel_layers_config, get_celery_redis_config

    celery_config = get_celery_redis_config('production')

    return {
        'CELERY_TASK_ALWAYS_EAGER': False,
        'CACHES': get_optimized_caches_config('production'),
        'CHANNEL_LAYERS': get_channel_layers_config('production'),
        'CELERY_BROKER_URL': celery_config['broker_url'],
        'CELERY_RESULT_BACKEND': celery_config['result_backend'],
        'REDIS_CONNECTION_POOL_MAX_CONNECTIONS': 100,
        'REDIS_HEALTH_CHECK_ENABLED': True,
        'REDIS_MONITORING_ENABLED': True,
    }
