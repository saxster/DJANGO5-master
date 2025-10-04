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
from apps.core.validation import (
    validate_secret_key,
    validate_encryption_key,
    validate_admin_password,
    SecretValidationLogger,
    SecretValidationError
)
import logging

# Use dedicated secret validation logger
secret_logger = logging.getLogger("security.secret_validation")

try:
    SECRET_KEY = validate_secret_key("SECRET_KEY", env("SECRET_KEY", default=get_random_secret_key()))
    ENCRYPT_KEY = validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY"))
    SUPERADMIN_PASSWORD = validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD"))
    # Secure logging: no sensitive details in console output
    secret_logger.info("All secrets validated successfully", extra={'environment': 'development', 'status': 'startup_success'})
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
        f"Application startup aborted due to invalid secret configuration",
        extra={'correlation_id': correlation_id, 'environment': 'development'}
    )

    # Console output for developer (generic guidance only, NO secret details)
    print(f"\n🚨 CRITICAL: Secret validation failed (correlation_id: {correlation_id})")
    print("📋 Check logs for details: /tmp/youtility4_logs/django_dev.log")
    print("🔧 Review environment file: intelliwiz_config/envs/.env.dev.secure")
    print("📖 Documentation: docs/security/secret-validation-logging.md\n")
    sys.exit(1)
except Exception as e:
    import sys
    import uuid
    correlation_id = str(uuid.uuid4())

    # Log unexpected error
    secret_logger.critical(
        f"Unexpected error during secret validation: {type(e).__name__}",
        extra={'correlation_id': correlation_id, 'error_type': type(e).__name__},
        exc_info=True
    )

    print(f"\n🚨 CRITICAL: Unexpected startup error (correlation_id: {correlation_id})")
    print("📋 Check logs for details: /tmp/youtility4_logs/django_dev.log\n")
    sys.exit(1)

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_FROM_ADDRESS = env("EMAIL_FROM_ADDRESS", default="dev@youtility.in")
DEFAULT_FROM_EMAIL = EMAIL_FROM_ADDRESS

# Database configuration with connection pooling optimization
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "USER": env("DBUSER"), "NAME": env("DBNAME"), "PASSWORD": env("DBPASS"),
        "HOST": env("DBHOST"), "PORT": "5432",
        # Enable connection pooling for better performance
        "CONN_MAX_AGE": 600,  # 10 minutes - optimal for development
        "CONN_HEALTH_CHECKS": True,  # Enable connection health checks
        "OPTIONS": {
            "MAX_CONNS": 20,  # Maximum connections per process
            "MIN_CONNS": 2,   # Minimum connections to maintain
            "application_name": "youtility_dev",  # For connection tracking
        },
    }
}

# OPTIMIZED Redis Configuration - Connection Pool & Performance Enhancements
from .redis_optimized import OPTIMIZED_CACHES, OPTIMIZED_CHANNEL_LAYERS, REDIS_PERFORMANCE_SETTINGS

# Cache configuration with optimized connection pooling
CACHES = OPTIMIZED_CACHES

# Channel layers for WebSocket with Redis optimization
CHANNEL_LAYERS = OPTIMIZED_CHANNEL_LAYERS

# Redis performance monitoring settings
REDIS_MONITORING_ENABLED = True
REDIS_PERFORMANCE_LOGGING = True

# Development-specific Redis settings
os.environ.setdefault('DJANGO_ENVIRONMENT', 'development')

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

# ============================================================================
# GRAPHQL DEVELOPMENT OVERRIDES
# ============================================================================
# Development environment uses relaxed GraphQL settings for easier testing
# and debugging. Production uses strict security settings.
# ============================================================================

# More relaxed rate limiting for development
GRAPHQL_RATE_LIMIT_MAX = 1000  # 10x higher than production
GRAPHQL_RATE_LIMIT_WINDOW = 300  # Same 5 minute window

# Allow GraphQL introspection in development (useful for GraphiQL)
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = False

# Relaxed origin validation for local testing
GRAPHQL_STRICT_ORIGIN_VALIDATION = False
GRAPHQL_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Higher complexity limits for development testing
GRAPHQL_MAX_QUERY_DEPTH = 15  # Deeper nesting allowed
GRAPHQL_MAX_QUERY_COMPLEXITY = 2000  # Higher complexity allowed
GRAPHQL_MAX_MUTATIONS_PER_REQUEST = 10  # More mutations per batch

# Enhanced logging in development
GRAPHQL_SECURITY_LOGGING['ENABLE_FIELD_ACCESS_LOGGING'] = True
GRAPHQL_SECURITY_LOGGING['ENABLE_OBJECT_ACCESS_LOGGING'] = True

print(f"[DEV SETTINGS] Development settings loaded from {ENV_FILE}")
print(f"[DEV SETTINGS] Debug mode: {DEBUG}")
print(f"[DEV SETTINGS] Database: {DATABASES['default']['NAME']}@{DATABASES['default']['HOST']}")
print(f"[DEV SETTINGS] GraphQL Rate Limit: {GRAPHQL_RATE_LIMIT_MAX} requests per {GRAPHQL_RATE_LIMIT_WINDOW}s")
print(f"[DEV SETTINGS] GraphQL Introspection: {'Enabled' if not GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION else 'Disabled'}")