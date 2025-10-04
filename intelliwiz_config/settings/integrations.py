"""
Third-party integrations and external services configuration.
Celery, Redis, MQTT, Email, Notifications, and other external integrations.
"""

import os
import json
import environ

env = environ.Env()

# CELERY CONFIGURATION - OPTIMIZED MULTI-QUEUE ARCHITECTURE

# Import optimized Redis configuration for Celery
from .redis_optimized import get_celery_redis_config

# Get optimized Celery Redis URLs with authentication and connection pooling
_celery_redis_config = get_celery_redis_config(env('DJANGO_ENVIRONMENT', default='production'))

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=_celery_redis_config['broker_url'])
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=_celery_redis_config['result_backend'])

# Security: Use JSON serialization to prevent code injection
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True

# PERFORMANCE OPTIMIZATION
CELERY_WORKER_PREFETCH_MULTIPLIER = 4  # 4x throughput improvement
CELERY_WORKER_CONCURRENCY = 8          # Scale based on CPU cores
CELERY_TASK_ALWAYS_EAGER = False       # Ensure async execution
CELERY_TASK_EAGER_PROPAGATES = False   # Production setting
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Restart workers periodically
CELERY_TASK_SEND_SENT_EVENT = True     # Enable monitoring
CELERY_WORKER_SEND_TASK_EVENTS = True  # Enable task events

# REDIS BROKER OPTIMIZATION
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,           # 1 hour visibility
    'fanout_prefix': True,                # Enable fanout optimization
    'fanout_patterns': True,              # Enable pattern matching
    'priority_steps': list(range(10)),    # Enable task priorities 0-9
    'sep': ':',                           # Key separator
    'queue_order_strategy': 'priority',   # Priority-based queue ordering
}

# RESULT BACKEND OPTIMIZATION
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'retry_policy': {
        'timeout': 5.0,
        'max_retries': 10,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    }
}

# QUEUE DEFINITIONS WITH PRIORITIES
from kombu import Queue, Exchange

CELERY_TASK_QUEUES = (
    # CRITICAL PRIORITY - Safety & Security (Priority 9-10)
    Queue('critical',
          Exchange('critical', type='direct'),
          routing_key='critical',
          queue_arguments={'x-max-priority': 10}),

    # HIGH PRIORITY - User-facing operations (Priority 8)
    Queue('high_priority',
          Exchange('high_priority', type='direct'),
          routing_key='high_priority',
          queue_arguments={'x-max-priority': 8}),

    # EMAIL QUEUE - Dedicated email processing (Priority 7)
    Queue('email',
          Exchange('email', type='direct'),
          routing_key='email',
          queue_arguments={'x-max-priority': 7}),

    # REPORTS QUEUE - Background analytics (Priority 6)
    Queue('reports',
          Exchange('reports', type='direct'),
          routing_key='reports',
          queue_arguments={'x-max-priority': 6}),

    # EXTERNAL API - With circuit breaker protection (Priority 5)
    Queue('external_api',
          Exchange('external_api', type='direct'),
          routing_key='external_api',
          queue_arguments={'x-max-priority': 5}),

    # MAINTENANCE - Lowest priority cleanup (Priority 3)
    Queue('maintenance',
          Exchange('maintenance', type='direct'),
          routing_key='maintenance',
          queue_arguments={'x-max-priority': 3}),

    # DEFAULT - General tasks (Priority 5)
    Queue('default',
          Exchange('default', type='direct'),
          routing_key='default',
          queue_arguments={'x-max-priority': 5}),
)

# ENHANCED TASK ROUTING - BUSINESS DOMAIN SEPARATION
CELERY_TASK_ROUTES = {
    # CRITICAL PRIORITY - Safety & Security (Queue: critical, Priority: 9-10)
    'background_tasks.journal_wellness_tasks.process_crisis_intervention_alert': {
        'queue': 'critical', 'priority': 10
    },
    'background_tasks.journal_wellness_tasks.monitor_crisis_patterns': {
        'queue': 'critical', 'priority': 9
    },
    'apps.noc.security_intelligence.tasks.*': {
        'queue': 'critical', 'priority': 9
    },
    'background_tasks.noc_tasks.escalate_security_alert': {
        'queue': 'critical', 'priority': 9
    },

    # HIGH PRIORITY - User-facing operations (Queue: high_priority, Priority: 8)
    'apps.face_recognition.integrations.process_biometric_verification': {
        'queue': 'high_priority', 'priority': 8
    },
    'background_tasks.tasks.send_ticket_email': {
        'queue': 'high_priority', 'priority': 8
    },
    'background_tasks.tasks.alert_sendmail': {
        'queue': 'high_priority', 'priority': 8
    },
    'apps.y_helpdesk.*escalate*': {
        'queue': 'high_priority', 'priority': 8
    },

    # EMAIL QUEUE - Dedicated email processing (Queue: email, Priority: 7)
    'background_tasks.tasks.send_*_email*': {'queue': 'email', 'priority': 7},
    'background_tasks.journal_wellness_tasks.notify_support_team': {'queue': 'email', 'priority': 7},
    'send_reminder_email': {'queue': 'email', 'priority': 7},
    'send_generated_report_on_mail': {'queue': 'email', 'priority': 7},

    # REPORTS QUEUE - Background analytics (Queue: reports, Priority: 6)
    'background_tasks.tasks.create_*_report*': {'queue': 'reports', 'priority': 6},
    'background_tasks.journal_wellness_tasks.update_user_analytics': {
        'queue': 'reports', 'priority': 6
    },
    'background_tasks.personalization_tasks.*': {'queue': 'reports', 'priority': 6},
    'create_scheduled_reports': {'queue': 'reports', 'priority': 6},

    # EXTERNAL API - With circuit breaker protection (Queue: external_api, Priority: 5)
    'background_tasks.tasks.publish_mqtt': {'queue': 'external_api', 'priority': 5},
    'background_tasks.onboarding_tasks.*api*': {'queue': 'external_api', 'priority': 5},
    'apps.journal.mqtt_integration.*': {'queue': 'external_api', 'priority': 5},

    # MAINTENANCE - Lowest priority cleanup (Queue: maintenance, Priority: 3)
    'background_tasks.tasks.auto_close_jobs': {'queue': 'maintenance', 'priority': 3},
    'background_tasks.tasks.cache_warming_scheduled': {'queue': 'maintenance', 'priority': 3},
    'background_tasks.tasks.cleanup_*': {'queue': 'maintenance', 'priority': 3},
    'background_tasks.tasks.move_media_to_cloud_storage': {'queue': 'maintenance', 'priority': 2},
    'create_ppm_job': {'queue': 'maintenance', 'priority': 4},
    'create_job': {'queue': 'maintenance', 'priority': 4},

    # DEFAULT - General tasks (Queue: default, Priority: 5)
    'background_tasks.tasks.process_graphql_mutation_async': {'queue': 'default', 'priority': 5},
    'background_tasks.tasks.*': {'queue': 'default', 'priority': 5},
    'ticket_escalation': {'queue': 'default', 'priority': 6},  # Higher priority for escalations
}

# RETRY CONFIGURATION
CELERY_TASK_DEFAULT_RETRY_DELAY = 60        # 1 minute default
CELERY_TASK_MAX_RETRIES = 3                 # Maximum retry attempts
CELERY_TASK_RETRY_BACKOFF = True            # Exponential backoff
CELERY_TASK_RETRY_BACKOFF_MAX = 600         # 10 minutes max delay
CELERY_TASK_RETRY_JITTER = True             # Add randomness to prevent thundering herd

# MONITORING AND RELIABILITY
CELERY_TASK_TRACK_STARTED = True            # Track task start events
CELERY_TASK_TIME_LIMIT = 3600               # 1 hour hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 1800          # 30 minutes soft limit
CELERY_RESULT_EXPIRES = 3600                # Results expire after 1 hour

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

# OPTIMIZED REDIS CACHE CONFIGURATION
# Integrates advanced connection pooling, security, and performance enhancements

from .redis_optimized import get_optimized_caches_config, get_channel_layers_config

# Default cache configuration (will be overridden by environment-specific settings)
CACHES = get_optimized_caches_config('production')  # Default to production settings

# CHANNEL LAYERS - WebSocket support with optimized Redis connection pooling
CHANNEL_LAYERS = get_channel_layers_config('production')  # Default to production settings

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
    """Development-specific integration settings with optimized Redis."""
    from .redis_optimized import get_optimized_caches_config, get_channel_layers_config, get_celery_redis_config

    celery_config = get_celery_redis_config('development')

    return {
        'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend',
        'CELERY_TASK_ALWAYS_EAGER': env.bool("CELERY_TASK_ALWAYS_EAGER", default=True),
        'CELERY_TASK_EAGER_PROPAGATES': True,
        # Optimized Redis configurations for development
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
        # Optimized Redis configurations for production
        'CACHES': get_optimized_caches_config('production'),
        'CHANNEL_LAYERS': get_channel_layers_config('production'),
        'CELERY_BROKER_URL': celery_config['broker_url'],
        'CELERY_RESULT_BACKEND': celery_config['result_backend'],
        # Production-specific Redis performance settings
        'REDIS_CONNECTION_POOL_MAX_CONNECTIONS': 100,
        'REDIS_HEALTH_CHECK_ENABLED': True,
        'REDIS_MONITORING_ENABLED': True,
    }

# Cache configurations moved to environment-specific modules for better organization