"""
Production-specific Django settings.
Security-first configuration with performance optimizations.
"""

import os
from .base import *
from .logging import setup_logging
from .security import get_production_security_settings
from .integrations import get_production_integrations
from .rest_api import REST_FRAMEWORK, SIMPLE_JWT, API_VERSION_CONFIG, GRAPHQL_VERSION_CONFIG, SPECTACULAR_SETTINGS

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
from apps.core.validation import validate_secret_key, validate_encryption_key, validate_admin_password

try:
    SECRET_KEY = validate_secret_key("SECRET_KEY", env("SECRET_KEY"))
    ENCRYPT_KEY = validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY"))
    SUPERADMIN_PASSWORD = validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD"))
    print("✅ All secrets validated successfully in production environment")
except Exception as e:
    import sys
    print(f"\n🚨 CRITICAL SECURITY ERROR: {e}")
    if hasattr(e, 'remediation') and e.remediation:
        print(f"🔧 REMEDIATION: {e.remediation}")
    print("\n❌ Production startup aborted due to invalid secrets.")
    print("Fix the above issues and restart the application.")
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

# Database configuration with SSL
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "USER": env("DBUSER"), "NAME": env("DBNAME"), "PASSWORD": env("DBPASS"),
        "HOST": env("DBHOST"), "PORT": "5432", "CONN_MAX_AGE": 300,
        "OPTIONS": {"sslmode": "require"},
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

print(f"[PROD SETTINGS] Production settings loaded - DEBUG: {DEBUG}, SSL: {SECURE_SSL_REDIRECT}")