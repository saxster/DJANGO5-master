"""
Development-specific Django settings.
"""

import os
from django.core.management.utils import get_random_secret_key
from .base import *
from .logging import setup_logging
from .security import get_development_security_settings
from .integrations import get_development_integrations
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, SPECTACULAR_SETTINGS

# Environment imports
import environ
env = environ.Env()

# Environment configuration
ENV_FILE = ".env.dev.secure"
ENVPATH = os.path.join(BASE_DIR, "intelliwiz_config/envs")
environ.Env.read_env(os.path.join(ENVPATH, ENV_FILE), overwrite=True)

# Debug configuration
DEBUG = True

# SECURITY FIX (2025-10-11): Import refactored security configs with DEBUG override
# This ensures Django's DEBUG setting is the single source of truth for security decisions
from .security.hosts import get_allowed_hosts
from .security.cors import get_cors_allowed_origins

# Override with Django DEBUG setting (NOT env var)
ALLOWED_HOSTS = get_allowed_hosts(is_debug=DEBUG)
CORS_ALLOWED_ORIGINS = get_cors_allowed_origins(is_debug=DEBUG)

# Validation: Ensure security settings are properly configured
assert isinstance(ALLOWED_HOSTS, list), "ALLOWED_HOSTS must be a list"
assert len(ALLOWED_HOSTS) > 0, "ALLOWED_HOSTS cannot be empty in development"
assert isinstance(CORS_ALLOWED_ORIGINS, list), "CORS_ALLOWED_ORIGINS must be a list"
assert len(CORS_ALLOWED_ORIGINS) > 0, "CORS_ALLOWED_ORIGINS cannot be empty in development"

# Development-specific apps and middleware
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE.insert(2, "debug_toolbar.middleware.DebugToolbarMiddleware")
MIDDLEWARE.append("apps.core.middleware.query_performance_monitoring.QueryPerformanceMonitoringMiddleware")

# Environment variables with security validation
# CRITICAL: Apply Rule 4 validation - Secure Secret Management
# NOTE: Import from validation.py (not validation_pydantic package)
import sys
sys.path.insert(0, os.path.join(BASE_DIR, 'apps/core'))
from validation import (
    validate_secret_key,
    validate_encryption_key,
    validate_admin_password,
    SecretValidationLogger,
    SecretValidationError
)
sys.path.pop(0)
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
    import sys
    sys.stderr.write(f"\n🚨 CRITICAL: Secret validation failed (correlation_id: {correlation_id})\n")
    sys.stderr.write("📋 Check logs for details: /tmp/youtility4_logs/django_dev.log\n")
    sys.stderr.write("🔧 Review environment file: intelliwiz_config/envs/.env.dev.secure\n")
    sys.stderr.write("📖 Documentation: docs/security/secret-validation-logging.md\n\n")
    sys.exit(1)
except SETTINGS_EXCEPTIONS as e:
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
            "application_name": "youtility_dev",  # For connection tracking
            "connect_timeout": 10,  # Connection timeout in seconds
        },
    }
}

# OPTIMIZED Redis Configuration - Connection Pool & Performance Enhancements
from .redis import OPTIMIZED_CACHES, OPTIMIZED_CHANNEL_LAYERS, REDIS_PERFORMANCE_SETTINGS
# Settings-specific exceptions
SETTINGS_EXCEPTIONS = (ValueError, TypeError, AttributeError, KeyError, ImportError, OSError, IOError)

# Cache configuration with optimized connection pooling
CACHES = OPTIMIZED_CACHES

# Channel layers for WebSocket with Redis optimization
CHANNEL_LAYERS = OPTIMIZED_CHANNEL_LAYERS

# Redis performance monitoring settings
REDIS_MONITORING_ENABLED = True
REDIS_PERFORMANCE_LOGGING = True

# Development-specific Redis settings
# Note: DJANGO_ENVIRONMENT is now set in intelliwiz_config/settings/__init__.py
# before imports to ensure correct environment detection during module initialization

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

# Reduce environ logging verbosity (suppress DEBUG logs during startup)
logging.getLogger('environ.environ').setLevel(logging.INFO)

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
