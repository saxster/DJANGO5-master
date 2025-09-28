"""
Third-party integrations and external services configuration.
Celery, Redis, MQTT, Email, Notifications, and other external integrations.
"""

import os
import json
import environ

env = environ.Env()

# CELERY CONFIGURATION

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='django-db')

# Security: Use JSON serialization to prevent code injection
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Celery Queue Configuration
CELERY_TASK_ROUTES = {
    'background_tasks.tasks.process_graphql_mutation_async': {'queue': 'django5_queue'},
    'background_tasks.tasks.*': {'queue': 'django5_queue'},
}

# EMAIL CONFIGURATION

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "email-smtp.us-east-1.amazonaws.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("AWS_SES_SMTP_USER")
EMAIL_HOST_PASSWORD = env("AWS_SES_SMTP_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_FROM_ADDRESS = DEFAULT_FROM_EMAIL

# Email Verification Configuration
EMAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_SUBJECT = "Confirm your email"
EMAIL_MAIL_HTML = "email.html"
EMAIL_MAIL_PLAIN = "mail_body.txt"
EMAIL_MAIL_PAGE_TEMPLATE = "email_verify.html"
EMAIL_PAGE_DOMAIN = env("EMAIL_PAGE_DOMAIN")
EMAIL_MULTI_USER = True
CUSTOM_SALT = env("CUSTOM_SALT", default="django-email-verification-salt")

# Email verification callbacks moved to apps.peoples.utils.email_callbacks for better organization
from apps.peoples.utils import verified_callback
EMAIL_VERIFIED_CALLBACK = verified_callback
EMAIL_MAIL_CALLBACK = verified_callback

# CACHE CONFIGURATION

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "youtility4",
    },
    "select2": {
        "BACKEND": "apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache",
        "LOCATION": "",
        "OPTIONS": {"MAX_ENTRIES": 10000, "CULL_FREQUENCY": 3},
        "TIMEOUT": 900,
        "KEY_PREFIX": "select2_mv",
    },
}

# CHANNEL LAYERS - WebSocket support with Redis
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["redis://127.0.0.1:6379/2"],
            "capacity": 10000, "expiry": 60, "group_expiry": 86400,
        },
    },
}

# POSTGRESQL TASK QUEUE CONFIGURATION
POSTGRESQL_TASK_QUEUE = {
    "DEFAULT_QUEUE": "default", "MAX_RETRIES": 3, "RETRY_DELAY": 60,
    "WORKER_CONCURRENCY": 4, "HEARTBEAT_INTERVAL": 30, "CLEANUP_INTERVAL": 86400,
    "QUEUES": ["default", "high_priority", "email", "reports", "mqtt", "maintenance"],
}

# MQTT CONFIGURATION

MQTT_CONFIG = {
    "BROKER_ADDRESS": env("MQTT_BROKER_ADDRESS"),
    "broker_port": env.int("MQTT_BROKER_PORT"),
    "broker_userNAME": env("MQTT_BROKER_USERNAME"),
    "broker_password": env("MQTT_BROKER_PASSWORD"),
}

# CLIENT DOMAINS CONFIGURATION

_DEFAULT_CLIENT_DOMAINS = {
    "R_REDMINE": "redmine.youtility.in", "R_TOURTRAX": "redmine.youtility.in",
    "R_SUKHI": "redmine.youtility.in", "R_CAPGEMINI": "redmine.youtility.in",
    "D_SUKHI": "demo.youtility.in", "D_CAPGEMINI": "demo.youtility.in",
    "SUKHI": "sg.youtility.in", "D_TOURTRAX": "demo.youtility.in",
    "WTC": "intelliwiz2.youtility.in", "R_YTPLD": "redmine.youtility.in",
}

CLIENT_DOMAINS = _DEFAULT_CLIENT_DOMAINS.copy()

# Load CLIENT_DOMAINS from environment
client_domains_json = env('CLIENT_DOMAINS_JSON', default='{}')
try:
    client_domains_override = json.loads(client_domains_json)
    if isinstance(client_domains_override, dict):
        CLIENT_DOMAINS.update(client_domains_override)
except (json.JSONDecodeError, TypeError):
    pass

# Individual domain overrides
for client_key in list(_DEFAULT_CLIENT_DOMAINS.keys()):
    env_key = f'CLIENT_DOMAIN_{client_key}'
    domain_override = env(env_key, default=None)
    if domain_override:
        CLIENT_DOMAINS[client_key] = domain_override

# NOTIFICATION SERVICE CONFIGURATION

ENABLE_WEBHOOK_NOTIFICATIONS = env.bool('ENABLE_WEBHOOK_NOTIFICATIONS', default=False)

NOTIFICATION_PROVIDERS = {
    'slack': {'type': 'slack', 'webhook_url': env('SLACK_WEBHOOK_URL', default=''),
              'channel': env('SLACK_CHANNEL', default='#onboarding-alerts'),
              'username': env('SLACK_USERNAME', default='IntelliWiz AI'),
              'timeout_seconds': env.int('SLACK_TIMEOUT', default=10)},
    'discord': {'type': 'discord', 'webhook_url': env('DISCORD_WEBHOOK_URL', default=''),
                'username': env('DISCORD_USERNAME', default='IntelliWiz AI'),
                'timeout_seconds': env.int('DISCORD_TIMEOUT', default=10)},
    'email': {'type': 'email', 'recipients': env.list('NOTIFICATION_EMAIL_RECIPIENTS', default=[]),
              'from_email': env('NOTIFICATION_FROM_EMAIL', default=DEFAULT_FROM_EMAIL),
              'template_dir': 'onboarding/notifications/'},
    'webhook_alerts': {'type': 'webhook', 'webhook_url': env('CUSTOM_WEBHOOK_URL', default=''),
                       'secret': env('CUSTOM_WEBHOOK_SECRET', default=''),
                       'auth_header': env('CUSTOM_WEBHOOK_AUTH', default=''),
                       'timeout_seconds': env.int('CUSTOM_WEBHOOK_TIMEOUT', default=10),
                       'headers': {'User-Agent': 'IntelliWiz-Notifications/1.0'}}
}

NOTIFICATION_ROUTING = {
    'approval_pending': env.list('NOTIFICATION_APPROVAL_PENDING_PROVIDERS', default=['slack', 'email']),
    'approval_granted': env.list('NOTIFICATION_APPROVAL_GRANTED_PROVIDERS', default=['slack']),
    'approval_rejected': env.list('NOTIFICATION_APPROVAL_REJECTED_PROVIDERS', default=['slack', 'email']),
    'escalation_created': env.list('NOTIFICATION_ESCALATION_PROVIDERS', default=['slack', 'discord', 'email']),
    'changeset_applied': env.list('NOTIFICATION_CHANGESET_APPLIED_PROVIDERS', default=['slack']),
    'changeset_rollback': env.list('NOTIFICATION_CHANGESET_ROLLBACK_PROVIDERS', default=['slack', 'email']),
    'system_error': env.list('NOTIFICATION_SYSTEM_ERROR_PROVIDERS', default=['email', 'webhook_alerts'])
}

# FILE STORAGE AND BUCKETS

BUCKET = env("BUCKET", default="prod-attachment-sukhi-group")
TEMP_REPORTS_GENERATED = env("TEMP_REPORTS_GENERATED")
ONDEMAND_REPORTS_GENERATED = env("ONDEMAND_REPORTS_GENERATED")
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10485760)

# EXTERNAL API KEYS

GOOGLE_MAP_SECRET_KEY = env("GOOGLE_MAP_SECRET_KEY")
BULK_IMPORT_GOOGLE_DRIVE_API_KEY = env("BULK_IMPORT_GOOGLE_DRIVE_API_KEY")

# ENVIRONMENT-SPECIFIC INTEGRATION SETTINGS

def get_development_integrations():
    """Development-specific integration settings."""
    return {
        'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend',
        'CELERY_TASK_ALWAYS_EAGER': env.bool("CELERY_TASK_ALWAYS_EAGER", default=True),
        'CELERY_TASK_EAGER_PROPAGATES': True
    }

def get_production_integrations():
    """Production-specific integration settings."""
    return {
        'CELERY_TASK_ALWAYS_EAGER': False,
        'CACHES': {
            **CACHES,
            'default': {**CACHES['default'], 'KEY_PREFIX': 'youtility4_prod', 'TIMEOUT': 900},
            'select2': {**CACHES['select2'], 'KEY_PREFIX': 'select2_mv_prod', 'TIMEOUT': 3600}
        }
    }

# Cache configurations moved to environment-specific modules for better organization