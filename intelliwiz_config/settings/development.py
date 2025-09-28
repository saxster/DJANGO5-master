"""
Development-specific Django settings.
"""

import os
from django.core.management.utils import get_random_secret_key
from .base import *
from .logging import setup_logging
from .security import get_development_security_settings
from .integrations import get_development_integrations
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, GRAPHQL_VERSION_CONFIG, SPECTACULAR_SETTINGS

# Environment imports
import environ
env = environ.Env()

# Environment configuration
ENV_FILE = ".env.dev.secure"
ENVPATH = os.path.join(BASE_DIR.parent, "intelliwiz_config/envs")
environ.Env.read_env(os.path.join(ENVPATH, ENV_FILE), overwrite=True)

# Debug configuration
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1:8005", "127.0.0.1", "localhost", "192.168.1.243"]

# Development-specific apps and middleware
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE.insert(2, "debug_toolbar.middleware.DebugToolbarMiddleware")
MIDDLEWARE.append("apps.core.middleware.query_performance_monitoring.QueryPerformanceMonitoringMiddleware")

# Add AI Mentor system in development with explicit enablement
if os.environ.get('MENTOR_ENABLED') == '1':
    INSTALLED_APPS.extend(["apps.mentor", "apps.mentor_api"])
    print("🤖 AI Mentor system enabled - Development mode only")

# Environment variables with security validation
# CRITICAL: Apply Rule 4 validation - Secure Secret Management
from apps.core.validation import validate_secret_key, validate_encryption_key, validate_admin_password

try:
    SECRET_KEY = validate_secret_key("SECRET_KEY", env("SECRET_KEY", default=get_random_secret_key()))
    ENCRYPT_KEY = validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY"))
    SUPERADMIN_PASSWORD = validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD"))
    print("✅ All secrets validated successfully in development environment")
except Exception as e:
    import sys
    print(f"\n🚨 CRITICAL SECURITY ERROR: {e}")
    if hasattr(e, 'remediation') and e.remediation:
        print(f"🔧 REMEDIATION: {e.remediation}")
    print("\n❌ Application startup aborted due to invalid secrets.")
    print("Fix the above issues and restart the application.")
    sys.exit(1)

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_FROM_ADDRESS = env("EMAIL_FROM_ADDRESS", default="dev@youtility.in")
DEFAULT_FROM_EMAIL = EMAIL_FROM_ADDRESS

# Database configuration
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "USER": env("DBUSER"), "NAME": env("DBNAME"), "PASSWORD": env("DBPASS"),
        "HOST": env("DBHOST"), "PORT": "5432", "CONN_MAX_AGE": 0,
    }
}

# Cache configuration for development
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"}, "KEY_PREFIX": "youtility4_dev",
    },
    "select2": {
        "BACKEND": "apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache",
        "LOCATION": "", "OPTIONS": {"MAX_ENTRIES": 1000, "CULL_FREQUENCY": 3},
        "TIMEOUT": 300, "KEY_PREFIX": "select2_mv_dev",
    },
}

# Channel layers for WebSocket
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": ["redis://127.0.0.1:6379/2"], "capacity": 1000, "expiry": 60, "group_expiry": 3600},
    },
}

# Static and media files for development
STATIC_ROOT = env("STATIC_ROOT")
MEDIA_ROOT = env("MEDIA_ROOT")
MEDIA_URL = "/youtility4_media/"
WHITENOISE_AUTOREFRESH = True

# Security settings for development (less restrictive)
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# Email verification configuration
EMAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_SUBJECT = "Confirm your email"
EMAIL_MAIL_HTML = "email.html"
EMAIL_MAIL_PLAIN = "mail_body.txt"
EMAIL_MAIL_PAGE_TEMPLATE = "email_verify.html"
EMAIL_PAGE_DOMAIN = env("EMAIL_PAGE_DOMAIN", default="localhost:8000")
EMAIL_MULTI_USER = True
CUSTOM_SALT = env("CUSTOM_SALT", default="django-email-verification-salt-dev")

# Setup development logging
setup_logging('development')

# Development-specific feature flags
ENABLE_CONVERSATIONAL_ONBOARDING = True
ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER = True
ENABLE_ONBOARDING_KB = True
ENABLE_ONBOARDING_SSE = True

# Development personalization settings
ONBOARDING_LEARNING_HOLDBACK_PCT = 0.0  # No holdback in dev
EXPERIMENT_MIN_SAMPLE_SIZE = 5
BANDIT_EPSILON = 0.3  # More exploration

# Enable all feature flags for development
PERSONALIZATION_FEATURE_FLAGS = {
    'enable_preference_learning': True, 'enable_cost_optimization': True,
    'enable_experiment_assignments': True, 'enable_smart_caching': True,
    'enable_adaptive_budgeting': True, 'enable_provider_routing': True,
    'enable_hot_path_precompute': True, 'enable_streaming_responses': True,
    'enable_anomaly_detection': True, 'enable_audit_logging': True
}

# Apply development security settings
dev_security = get_development_security_settings()
for key, value in dev_security.items():
    locals()[key] = value

# Apply development integration settings
dev_integrations = get_development_integrations()
for key, value in dev_integrations.items():
    locals()[key] = value

print(f"[DEV SETTINGS] Development settings loaded from {ENV_FILE}")
print(f"[DEV SETTINGS] Debug mode: {DEBUG}")
print(f"[DEV SETTINGS] Database: {DATABASES['default']['NAME']}@{DATABASES['default']['HOST']}")