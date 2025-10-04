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
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, GRAPHQL_VERSION_CONFIG, SPECTACULAR_SETTINGS

logger = logging.getLogger(__name__)

# Environment configuration
import environ
env = environ.Env()
ENV_FILE = ".env.prod.secure"
ENVPATH = os.path.join(BASE_DIR.parent, "intelliwiz_config/envs")
environ.Env.read_env(os.path.join(ENVPATH, ENV_FILE), overwrite=True)

# Security configuration
DEBUG = False
ALLOWED_HOSTS = ["django5.youtility.in", "127.0.0.1"]

if DEBUG:
    raise ValueError("DEBUG must be False in production environments")

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
    print(f"\n🚨 CRITICAL: Invalid secret configuration detected")
    print(f"🔐 Correlation ID: {correlation_id}")
    print(f"📋 Review secure logs: /var/log/youtility4/security.log")
    print(f"🚨 Production startup aborted for security\n")
    sys.exit(1)
except Exception as e:
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
    print(f"\n🚨 CRITICAL: Startup error")
    print(f"🔐 Correlation ID: {correlation_id}")
    print(f"📋 Contact system administrator\n")
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
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "USER": env("DBUSER"), "NAME": env("DBNAME"), "PASSWORD": env("DBPASS"),
        "HOST": env("DBHOST"), "PORT": "5432",
        # Production-optimized connection pooling
        "CONN_MAX_AGE": 3600,  # 1 hour - longer for production stability
        "CONN_HEALTH_CHECKS": True,  # Enable connection health checks
        "OPTIONS": {
            "sslmode": "require",
            "MAX_CONNS": 50,  # Higher limit for production
            "MIN_CONNS": 5,   # Maintain minimum connections
            "application_name": "youtility_prod",  # For connection tracking
            "connect_timeout": 10,  # Connection timeout
            "tcp_keepalives_idle": 600,
            "tcp_keepalives_interval": 30,
            "tcp_keepalives_count": 3,
        },
    }
}

# Channel layers for production
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": ["redis://127.0.0.1:6379/2"], "capacity": 50000, "expiry": 120, "group_expiry": 86400},
    },
}

# CORS configuration (strict for production)
CORS_ALLOWED_ORIGINS = ["https://django5.youtility.in"]
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://\w+\.youtility\.in$"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["accept", "accept-encoding", "authorization", "content-type", "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with"]
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]
CORS_PREFLIGHT_MAX_AGE = 86400

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

# ============================================================================
# GRAPHQL PRODUCTION SECURITY HARDENING
# ============================================================================
# Production environment enforces strict GraphQL security settings to prevent
# DoS attacks, unauthorized access, and data leakage.
# ============================================================================

# Strict rate limiting for production
GRAPHQL_RATE_LIMIT_MAX = 50  # Lower limit than base (50 vs 100)
GRAPHQL_RATE_LIMIT_WINDOW = 300  # 5 minute window

# MANDATORY: Disable introspection in production (security best practice)
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = True
if not GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION:
    raise ValueError("GraphQL introspection MUST be disabled in production for security")

# MANDATORY: Strict origin validation
GRAPHQL_STRICT_ORIGIN_VALIDATION = True
GRAPHQL_ALLOWED_ORIGINS = [
    'https://django5.youtility.in',
    'https://app.youtility.in',
]

# Comprehensive origin validation configuration (overrides base settings)
GRAPHQL_ORIGIN_VALIDATION = {
    'allowed_origins': GRAPHQL_ALLOWED_ORIGINS,
    'allowed_patterns': [
        r'^https://.*\.youtility\.in$',  # Allow all youtility.in subdomains
    ],
    'allowed_subdomains': ['youtility.in'],  # Allow *.youtility.in
    'blocked_origins': [],  # Blacklist specific origins if needed
    'strict_mode': True,  # CRITICAL: Reject requests without valid origin
    'validate_referer': True,  # Validate Referer header consistency
    'validate_host': True,  # Validate Host header consistency
    'allow_localhost_dev': False,  # PRODUCTION: Never allow localhost
    'geographic_validation': False,  # Can enable with GeoIP if needed
    'allowed_countries': [],  # Restrict by country if geo validation enabled
    'dynamic_allowlist': True,  # Cache validated origins for performance
    'suspicious_patterns': [
        r'.*\.onion$',  # Block Tor
        r'.*\.bit$',    # Block Namecoin
        r'\d+\.\d+\.\d+\.\d+',  # Block raw IPs
        r'.*localhost.*',  # Block localhost variants
        r'.*127\.0\.0\..*',  # Block loopback
    ]
}

# Conservative complexity limits for production
GRAPHQL_MAX_QUERY_DEPTH = 8  # Stricter than base (8 vs 10)
GRAPHQL_MAX_QUERY_COMPLEXITY = 800  # Stricter than base (800 vs 1000)
GRAPHQL_MAX_MUTATIONS_PER_REQUEST = 3  # Stricter than base (3 vs 5)

# Stricter JWT timeouts for production security
GRAPHQL_JWT = {
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": timedelta(hours=2),  # Production: 2 hours (stricter than dev 8 hours)
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=2),
    "JWT_LONG_RUNNING_REFRESH_TOKEN": True
}

# Enable all security logging in production
GRAPHQL_SECURITY_LOGGING['LOG_FAILED_CSRF_ATTEMPTS'] = True
GRAPHQL_SECURITY_LOGGING['ENABLE_MUTATION_LOGGING'] = True
GRAPHQL_SECURITY_LOGGING['ENABLE_RATE_LIMIT_LOGGING'] = True

# Validation: Ensure critical production security settings
assert GRAPHQL_STRICT_ORIGIN_VALIDATION, "Production MUST enforce strict origin validation"
assert GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION, "Production MUST disable GraphQL introspection"
assert GRAPHQL_RATE_LIMIT_MAX <= 100, "Production rate limit suspiciously high"
assert GRAPHQL_ORIGIN_VALIDATION['strict_mode'], "Production MUST have strict_mode enabled in GRAPHQL_ORIGIN_VALIDATION"
assert not GRAPHQL_ORIGIN_VALIDATION['allow_localhost_dev'], "Production MUST NOT allow localhost in origin validation"
assert GRAPHQL_ORIGIN_VALIDATION['validate_referer'], "Production MUST validate Referer header"
assert GRAPHQL_ORIGIN_VALIDATION['validate_host'], "Production MUST validate Host header"

logger.info(f"✅ Production GraphQL security hardening applied")
logger.info(f"   - Rate limit: {GRAPHQL_RATE_LIMIT_MAX} requests per {GRAPHQL_RATE_LIMIT_WINDOW}s")
logger.info(f"   - Introspection: {'Disabled' if GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION else 'ENABLED (SECURITY RISK!)'}")
logger.info(f"   - Origin validation: {'Strict' if GRAPHQL_STRICT_ORIGIN_VALIDATION else 'Relaxed (SECURITY RISK!)'}")

# Template performance optimization (disable auto-reload in production)
from copy import deepcopy
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
ENABLE_ONBOARDING_KB = env.bool('ENABLE_ONBOARDING_KB', default=False)
ENABLE_ONBOARDING_SSE = env.bool('ENABLE_ONBOARDING_SSE', default=False)

# Production API settings
ENABLE_API_AUTH = True
API_AUTH_PATHS = ["/api/", "/graphql/"]
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
    "/api/", "/api/v1/", "/graphql/", "/api/graphql/",
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