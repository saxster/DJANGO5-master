"""
Production-specific Django settings.
Security-first configuration with performance optimizations.
"""

import os
import logging
from .base import *
from .logging import setup_logging
from .security import get_production_security_settings
from .integrations import get_production_integrations
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, SPECTACULAR_SETTINGS
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger(__name__)

# Environment configuration
import environ
env = environ.Env()
ENV_FILE = ".env.prod.secure"
# SECURITY FIX: Use BASE_DIR instead of BASE_DIR.parent (correct path to envs directory)
ENVPATH = os.path.join(BASE_DIR, "intelliwiz_config/envs")
environ.Env.read_env(os.path.join(ENVPATH, ENV_FILE), overwrite=True)

# Security configuration
DEBUG = False

if DEBUG:
    raise ValueError("DEBUG must be False in production environments")

# SECURITY FIX (2025-10-11): Import refactored security configs with DEBUG override
# This ensures Django's DEBUG setting is the single source of truth for security decisions
from .security.hosts import get_allowed_hosts
from .security.cors import get_cors_allowed_origins

# Override with Django DEBUG setting (NOT env var) - CRITICAL for production security
ALLOWED_HOSTS = get_allowed_hosts(is_debug=DEBUG)
CORS_ALLOWED_ORIGINS = get_cors_allowed_origins(is_debug=DEBUG)

# Environment variables with comprehensive security validation
# CRITICAL: Apply Rule 4 validation - Secure Secret Management
from apps.core.validation import (
    validate_secret_key,
    validate_encryption_key,
    validate_admin_password,
    SecretValidationLogger,
    SecretValidationError
)

# Use dedicated secret validation logger (already configured)
secret_logger = logging.getLogger("security.secret_validation")

try:
    SECRET_KEY = validate_secret_key("SECRET_KEY", env("SECRET_KEY"))
    ENCRYPT_KEY = validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY"))
    SUPERADMIN_PASSWORD = validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD"))
    # Secure logging: no sensitive details exposed
    secret_logger.info("All secrets validated successfully", extra={'environment': 'production', 'status': 'startup_success'})
except SecretValidationError as e:
    import sys
    import uuid
    correlation_id = str(uuid.uuid4())

    # Log error securely with correlation ID (NO sensitive details)
    SecretValidationLogger.log_validation_error(
        e.secret_name if hasattr(e, 'secret_name') else 'UNKNOWN',
        'unknown',
        'validation_failed',
        correlation_id
    )

    # User-facing error message (generic, secure)
    secret_logger.critical(
        f"Production startup aborted due to invalid secret configuration",
        extra={'correlation_id': correlation_id, 'environment': 'production'},
        exc_info=False  # Don't log stack traces in production
    )

    # PRODUCTION: Minimal console output (NO sensitive details, NO remediation hints)
    # Logs contain full details for authorized personnel only
    import sys
    sys.stderr.write(f"\n🚨 CRITICAL: Invalid secret configuration detected\n")
    sys.stderr.write(f"🔐 Correlation ID: {correlation_id}\n")
    sys.stderr.write(f"📋 Review secure logs: /var/log/youtility4/security.log\n")
    sys.stderr.write(f"🚨 Production startup aborted for security\n\n")
    sys.exit(1)
except SETTINGS_EXCEPTIONS as e:
    import sys
    import uuid
    correlation_id = str(uuid.uuid4())

    # Log unexpected error with full context
    secret_logger.critical(
        f"Unexpected error during secret validation: {type(e).__name__}",
        extra={'correlation_id': correlation_id, 'error_type': type(e).__name__},
        exc_info=True  # Include stack trace in logs for debugging
    )

    # PRODUCTION: Generic error message only
    import sys
    sys.stderr.write(f"\n🚨 CRITICAL: Startup error\n")
    sys.stderr.write(f"🔐 Correlation ID: {correlation_id}\n")
    sys.stderr.write(f"📋 Contact system administrator\n\n")
    sys.exit(1)

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "email-smtp.us-east-1.amazonaws.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("AWS_SES_SMTP_USER")
EMAIL_HOST_PASSWORD = env("AWS_SES_SMTP_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_FROM_ADDRESS = DEFAULT_FROM_EMAIL

# Database configuration with SSL and optimized connection pooling
# POOLING STRATEGY: Django's CONN_MAX_AGE (inherited from database.py, overridden here for production)
# This is the SINGLE source of truth for connection pooling. No psycopg3 pool config in use.
# See intelliwiz_config/settings/database.py for base configuration and pooling strategy rationale.
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "USER": env("DBUSER"), "NAME": env("DBNAME"), "PASSWORD": env("DBPASS"),
        "HOST": env("DBHOST"), "PORT": "5432",
        # Production-optimized connection pooling via CONN_MAX_AGE
        # Overrides base config value (600s) with 1 hour for production stability
        "CONN_MAX_AGE": SECONDS_IN_HOUR,  # 3600s (1 hour) - production-specific value
        "CONN_HEALTH_CHECKS": True,  # Enable connection health checks
        "OPTIONS": {
            "sslmode": "require",
            "application_name": "youtility_prod",  # For connection tracking
            "connect_timeout": 10,  # Connection timeout in seconds
            "tcp_keepalives_idle": 600,  # TCP keepalive idle time
            "tcp_keepalives_interval": 30,  # TCP keepalive interval
            "tcp_keepalives_count": 3,  # TCP keepalive count
        },
    }
}

# OPTIMIZED Redis Configuration - Connection Pool & Performance Enhancements
from .redis import OPTIMIZED_CACHES, OPTIMIZED_CHANNEL_LAYERS, REDIS_PERFORMANCE_SETTINGS

# Cache configuration with optimized connection pooling
CACHES = OPTIMIZED_CACHES

# Redis performance monitoring settings (production-enabled)
REDIS_MONITORING_ENABLED = True
REDIS_PERFORMANCE_LOGGING = True

# Production-specific Redis settings
os.environ.setdefault('DJANGO_ENVIRONMENT', 'production')

# Channel layers for production (optimized with connection pooling)
CHANNEL_LAYERS = OPTIMIZED_CHANNEL_LAYERS

# CORS configuration - import constants from single source of truth (2025-10-11 remediation)
# Note: CORS_ALLOWED_ORIGINS is set above via get_cors_allowed_origins(is_debug=DEBUG)
# Only import CORS constants here (not CORS_ALLOWED_ORIGINS which is dynamically generated)
from .security.cors import (
    CORS_ALLOWED_ORIGIN_REGEXES,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_HEADERS,
    CORS_EXPOSE_HEADERS,
    CORS_PREFLIGHT_MAX_AGE,
)

# Static and media files
STATIC_ROOT = env("STATIC_ROOT")
MEDIA_ROOT = env("MEDIA_ROOT")
MEDIA_URL = "/youtility4_media/"

# Production security settings
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Language cookie security (production override)
LANGUAGE_COOKIE_SECURE = True  # Protect language preference cookie over HTTPS

# Template performance optimization (disable auto-reload in production)
from copy import deepcopy
# Settings-specific exceptions
SETTINGS_EXCEPTIONS = (ValueError, TypeError, AttributeError, KeyError, ImportError, OSError, IOError)
TEMPLATES = deepcopy(TEMPLATES)
if len(TEMPLATES) > 1:  # Jinja2 template config
    TEMPLATES[1]['OPTIONS']['auto_reload'] = False

# Email verification
EMAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_SUBJECT = "Confirm your email"
EMAIL_MAIL_HTML = "email.html"
EMAIL_MAIL_PLAIN = "mail_body.txt"
EMAIL_MAIL_PAGE_TEMPLATE = "email_verify.html"
EMAIL_PAGE_DOMAIN = env("EMAIL_PAGE_DOMAIN")
EMAIL_MULTI_USER = True
CUSTOM_SALT = env("CUSTOM_SALT", default="django-email-verification-salt")

# Setup production logging
setup_logging('production', '/var/log/youtility4')

# Feature flags (conservative for production)
ENABLE_CONVERSATIONAL_ONBOARDING = env.bool('ENABLE_CONVERSATIONAL_ONBOARDING', default=False)
ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER = env.bool('ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', default=False)
PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING = env.bool(
    'PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING',
    default=False,
)
PEOPLE_ONBOARDING_MAX_DOCUMENT_PAGES = env.int(
    'PEOPLE_ONBOARDING_MAX_DOCUMENT_PAGES',
    default=12,
)
PEOPLE_ONBOARDING_MAX_DOCUMENT_SIZE_MB = env.int(
    'PEOPLE_ONBOARDING_MAX_DOCUMENT_SIZE_MB',
    default=10,
)
PEOPLE_ONBOARDING_OCR_CONFIDENCE_THRESHOLD = env.float(
    'PEOPLE_ONBOARDING_OCR_CONFIDENCE_THRESHOLD',
    default=0.65,
)
ENABLE_ONBOARDING_KB = env.bool('ENABLE_ONBOARDING_KB', default=False)
ENABLE_ONBOARDING_SSE = env.bool('ENABLE_ONBOARDING_SSE', default=False)

# Production API settings
ENABLE_API_AUTH = True
API_AUTH_PATHS = ["/api/"]
API_REQUIRE_SIGNING = env.bool("API_REQUIRE_SIGNING", default=True)

# SECURITY: Disable legacy upload mutation (CVSS 8.1 vulnerability)
# This mutation has known path traversal and filename injection vulnerabilities
# Clients should migrate to secure_file_upload mutation before 2026-06-30
ENABLE_LEGACY_UPLOAD_MUTATION = False  # MUST be False in production

# Rate limiting
ENABLE_RATE_LIMITING = True
RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_PATHS = [
    "/login/", "/accounts/login/", "/auth/login/",
    "/api/", "/api/v1/",
    "/reset-password/", "/password-reset/",
    "/admin/", "/admin/django/",
    "/api/upload/"
]

# Personalization settings (conservative)
ONBOARDING_LEARNING_HOLDBACK_PCT = env.float('ONBOARDING_LEARNING_HOLDBACK_PCT', default=10.0)
ONBOARDING_EXPERIMENT_HOLDBACK_PCT = env.float('ONBOARDING_EXPERIMENT_HOLDBACK_PCT', default=5.0)
EXPERIMENT_MIN_SAMPLE_SIZE = env.int('EXPERIMENT_MIN_SAMPLE_SIZE', default=100)
BANDIT_EPSILON = env.float('BANDIT_EPSILON', default=0.05)

# Feature flags (controlled by environment)
PERSONALIZATION_FEATURE_FLAGS = {
    'enable_preference_learning': env.bool('FF_PREFERENCE_LEARNING', default=True),
    'enable_cost_optimization': env.bool('FF_COST_OPTIMIZATION', default=True),
    'enable_experiment_assignments': env.bool('FF_EXPERIMENT_ASSIGNMENTS', default=True),
    'enable_smart_caching': env.bool('FF_SMART_CACHING', default=True),
    'enable_adaptive_budgeting': env.bool('FF_ADAPTIVE_BUDGETING', default=True),
    'enable_provider_routing': env.bool('FF_PROVIDER_ROUTING', default=True),
    'enable_hot_path_precompute': env.bool('FF_HOT_PATH_PRECOMPUTE', default=False),
    'enable_streaming_responses': env.bool('FF_STREAMING_RESPONSES', default=False),
    'enable_anomaly_detection': env.bool('FF_ANOMALY_DETECTION', default=True),
    'enable_audit_logging': env.bool('FF_AUDIT_LOGGING', default=True)
}

# Production data limits
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10485760)
BUCKET = env("BUCKET", default="prod-attachment-sukhi-group")
TEMP_REPORTS_GENERATED = env("TEMP_REPORTS_GENERATED")
ONDEMAND_REPORTS_GENERATED = env("ONDEMAND_REPORTS_GENERATED")

# Apply production security settings from security module
production_security = get_production_security_settings()
for key, value in production_security.items():
    locals()[key] = value

# Apply production integrations settings
production_integrations = get_production_integrations()
for key, value in production_integrations.items():
    locals()[key] = value

logger.info(f"Production settings loaded - DEBUG: {DEBUG}, SSL: {SECURE_SSL_REDIRECT}")
