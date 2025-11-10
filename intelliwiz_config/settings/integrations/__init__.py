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

# ============================================================================
# CELERY CONFIGURATION (Task queues, broker)
# ============================================================================

from ..celery_config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_SERIALIZER,
    CELERY_RESULT_SERIALIZER,
    CELERY_ACCEPT_CONTENT,
    CELERY_TASK_REJECT_ON_WORKER_LOST,
    CELERY_TASK_ACKS_LATE,
    CELERY_WORKER_PREFETCH_MULTIPLIER,
    CELERY_WORKER_CONCURRENCY,
    CELERY_TASK_ALWAYS_EAGER,
    CELERY_TASK_EAGER_PROPAGATES,
    CELERY_WORKER_MAX_TASKS_PER_CHILD,
    CELERY_TASK_SEND_SENT_EVENT,
    CELERY_WORKER_SEND_TASK_EVENTS,
    CELERY_BROKER_TRANSPORT_OPTIONS,
    CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS,
    CELERY_TASK_QUEUES,
    CELERY_TASK_ROUTES,
    CELERY_TASK_DEFAULT_RETRY_DELAY,
    CELERY_TASK_MAX_RETRIES,
    CELERY_TASK_RETRY_BACKOFF,
    CELERY_TASK_RETRY_BACKOFF_MAX,
    CELERY_TASK_RETRY_JITTER,
    CELERY_TASK_TRACK_STARTED,
    CELERY_TASK_TIME_LIMIT,
    CELERY_TASK_SOFT_TIME_LIMIT,
    CELERY_RESULT_EXPIRES,
)

# ============================================================================
# AWS INTEGRATIONS (Email, S3 Storage)
# ============================================================================

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

import environ
from ..redis_optimized import get_optimized_caches_config, get_channel_layers_config

env = environ.Env()
_django_environment = env('DJANGO_ENVIRONMENT', default='development')
CACHES = get_optimized_caches_config(_django_environment)
CHANNEL_LAYERS = get_channel_layers_config(_django_environment)

__all__ = [
    # Celery
    'CELERY_BROKER_URL',
    'CELERY_RESULT_BACKEND',
    'CELERY_TASK_SERIALIZER',
    'CELERY_RESULT_SERIALIZER',
    'CELERY_ACCEPT_CONTENT',
    'CELERY_TASK_REJECT_ON_WORKER_LOST',
    'CELERY_TASK_ACKS_LATE',
    'CELERY_WORKER_PREFETCH_MULTIPLIER',
    'CELERY_WORKER_CONCURRENCY',
    'CELERY_TASK_ALWAYS_EAGER',
    'CELERY_TASK_EAGER_PROPAGATES',
    'CELERY_WORKER_MAX_TASKS_PER_CHILD',
    'CELERY_TASK_SEND_SENT_EVENT',
    'CELERY_WORKER_SEND_TASK_EVENTS',
    'CELERY_BROKER_TRANSPORT_OPTIONS',
    'CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS',
    'CELERY_TASK_QUEUES',
    'CELERY_TASK_ROUTES',
    'CELERY_TASK_DEFAULT_RETRY_DELAY',
    'CELERY_TASK_MAX_RETRIES',
    'CELERY_TASK_RETRY_BACKOFF',
    'CELERY_TASK_RETRY_BACKOFF_MAX',
    'CELERY_TASK_RETRY_JITTER',
    'CELERY_TASK_TRACK_STARTED',
    'CELERY_TASK_TIME_LIMIT',
    'CELERY_TASK_SOFT_TIME_LIMIT',
    'CELERY_RESULT_EXPIRES',
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
    # Redis caches/websockets
    'CACHES',
    'CHANNEL_LAYERS',
]

# ============================================================================
# ENVIRONMENT-SPECIFIC INTEGRATION SETTINGS (Helper Functions)
# ============================================================================

def get_development_integrations():
    """Development-specific integration settings with optimized Redis."""
    from ..redis_optimized import get_optimized_caches_config, get_channel_layers_config, get_celery_redis_config

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
    from ..redis_optimized import get_optimized_caches_config, get_channel_layers_config, get_celery_redis_config

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
