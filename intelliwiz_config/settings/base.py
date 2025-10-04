"""
Base Django settings for intelliwiz_config project.
Contains common settings shared across all environments.
"""

from pathlib import Path
import os
from datetime import timedelta
from django.contrib.messages import constants as message_constants

# Build paths inside the project like this: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "django.contrib.gis",
    # Third-party apps
    "graphene_django", "graphene_gis", "django_email_verification", "import_export",
    "django_extensions", "django_select2", "django_filters", "rest_framework", "rest_framework_simplejwt",
    "drf_spectacular", "drf_spectacular_sidecar",
    "graphql_jwt.refresh_token.apps.RefreshTokenConfig", "django_celery_beat",
    "django_celery_results", "corsheaders", "channels", "daphne", "django_cleanup.apps.CleanupConfig",
    # Local apps
    'apps.core', 'apps.peoples', 'apps.onboarding', 'apps.onboarding_api', 'apps.people_onboarding', 'apps.tenants',
    'apps.attendance', 'apps.activity', 'apps.schedhuler', 'apps.reminder', 'apps.reports',
    'apps.service', 'apps.y_helpdesk', 'apps.work_order_management', 'apps.mqtt', 'apps.face_recognition',
    'apps.voice_recognition', 'apps.journal', 'apps.wellness', 'apps.streamlab', 'apps.issue_tracker',
    'apps.ai_testing', 'apps.search', 'apps.api', 'apps.noc', 'apps.helpbot', 'monitoring',
]

# ============================================================================
# MIDDLEWARE CONFIGURATION (CRITICAL: Single Source of Truth)
# ============================================================================
# Import canonical middleware stack from middleware.py to prevent configuration drift.
# DO NOT define MIDDLEWARE inline here - always import from .middleware module.
# Environment-specific modifications should be done in development.py/production.py.
# ============================================================================

from .middleware import MIDDLEWARE

ROOT_URLCONF = "intelliwiz_config.urls"

# Template configuration
JINJA_TEMPLATES = os.path.join(BASE_DIR, "frontend/templates")
CONTEXT_PROCESSORS = [
    "apps.peoples.context_processors.app_settings", "django.template.context_processors.debug",
    "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages", "django.template.context_processors.media",
    "apps.helpbot.context_processors.helpbot_context",
]

TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
     "OPTIONS": {"context_processors": CONTEXT_PROCESSORS}},
    {"BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": [JINJA_TEMPLATES], "APP_DIRS": True,
     "OPTIONS": {"extensions": ["jinja2.ext.loopcontrols"], "autoescape": True, "auto_reload": True,
                 "undefined": "jinja2.StrictUndefined", "environment": "intelliwiz_config.jinja.env.JinjaEnvironment",
                 "context_processors": CONTEXT_PROCESSORS}},
]

WSGI_APPLICATION = "intelliwiz_config.wsgi.application"
ASGI_APPLICATION = "intelliwiz_config.asgi.application"

# Password validation (secure settings)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
     'OPTIONS': {'user_attributes': ('username', 'email', 'first_name', 'last_name'), 'max_similarity': 0.7}},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Core Django configuration
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_L10N = True  # Enable localization formatting
USE_TZ = True
TIME_ZONE = "UTC"

# Internationalization and Localization
LANGUAGES = [
    ('en', 'English'),
    ('hi', 'हिन्दी'),  # Hindi
    ('te', 'తెలుగు'),  # Telugu
    ('ta', 'தமிழ்'),   # Tamil
    ('kn', 'ಕನ್ನಡ'),   # Kannada
    ('mr', 'मराठी'),   # Marathi
    ('gu', 'ગુજરાતી'), # Gujarati
    ('bn', 'বাংলা'),   # Bengali
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
    BASE_DIR / 'apps' / 'core' / 'locale',
    BASE_DIR / 'apps' / 'peoples' / 'locale',
    BASE_DIR / 'apps' / 'attendance' / 'locale',
    BASE_DIR / 'apps' / 'activity' / 'locale',
    BASE_DIR / 'apps' / 'schedhuler' / 'locale',
    BASE_DIR / 'apps' / 'onboarding' / 'locale',
    BASE_DIR / 'apps' / 'reports' / 'locale',
    BASE_DIR / 'apps' / 'y_helpdesk' / 'locale',
    BASE_DIR / 'apps' / 'work_order_management' / 'locale',
]

# ============================================================================
# COOKIE SECURITY CONFIGURATION
# ============================================================================
# Import all cookie security settings from centralized security module.
# This includes: CSRF, Session, and Language cookie configurations.
# Environment-specific overrides are in development.py/production.py.
# ============================================================================

from .security.headers import (
    # CSRF Cookie Security
    CSRF_COOKIE_SECURE,
    CSRF_COOKIE_HTTPONLY,
    CSRF_COOKIE_SAMESITE,

    # Session Cookie Security
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,

    # Language Cookie Security
    LANGUAGE_COOKIE_NAME,
    LANGUAGE_COOKIE_AGE,
    LANGUAGE_COOKIE_DOMAIN,
    LANGUAGE_COOKIE_PATH,
    LANGUAGE_COOKIE_SECURE,
    LANGUAGE_COOKIE_HTTPONLY,
    LANGUAGE_COOKIE_SAMESITE,
    LANGUAGE_SESSION_KEY,
)
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "frontend/static")]
STATICFILES_FINDERS = ["django.contrib.staticfiles.finders.FileSystemFinder", "django.contrib.staticfiles.finders.AppDirectoriesFinder"]
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication configuration
AUTH_USER_MODEL = "peoples.People"
AUTHENTICATION_BACKENDS = ["graphql_jwt.backends.JSONWebTokenBackend", "django.contrib.auth.backends.ModelBackend"]

# Custom message tags for Bootstrap
MESSAGE_TAGS = {message_constants.DEBUG: "alert-info", message_constants.INFO: "alert-info",
               message_constants.SUCCESS: "alert-success", message_constants.WARNING: "alert-warning", message_constants.ERROR: "alert-danger"}

# Database and routing
DATABASE_ROUTERS = ["apps.tenants.middlewares.TenantDbRouter"]

# GraphQL configuration
GRAPHENE = {
    "ATOMIC_MUTATIONS": True,
    "SCHEMA": "apps.service.schema.schema",
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
        "apps.service.middleware.token_validation.RefreshTokenValidationMiddleware",  # Token blacklist validation
        "apps.service.middleware.graphql_auth.GraphQLAuthenticationMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLTenantValidationMiddleware",
        # PERFORMANCE: DataLoader middleware for N+1 query prevention (50%+ query reduction)
        # CRITICAL: Must come after authentication but before business logic
        "apps.api.graphql.dataloaders.DataLoaderMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLMutationChainingProtectionMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLIntrospectionControlMiddleware",
    ]
}

# ============================================================================
# GRAPHQL SECURITY CONFIGURATION (CVSS 8.1 vulnerability fix)
# ============================================================================
# All GraphQL settings are centralized in security/graphql.py for single source of truth.
# This prevents configuration drift and maintains compliance with Rule #6 (settings < 200 lines).
#
# IMPORTANT: Do NOT define GraphQL settings here - import from security module only.
# Any GraphQL setting changes must be made in security/graphql.py.
# ============================================================================

from .security.graphql import (
    # Endpoint configuration
    GRAPHQL_PATHS,

    # Rate limiting
    ENABLE_GRAPHQL_RATE_LIMITING,
    GRAPHQL_RATE_LIMIT_WINDOW,
    GRAPHQL_RATE_LIMIT_MAX,

    # Query complexity limits (DoS prevention)
    GRAPHQL_MAX_QUERY_DEPTH,
    GRAPHQL_MAX_QUERY_COMPLEXITY,
    GRAPHQL_MAX_MUTATIONS_PER_REQUEST,
    GRAPHQL_ENABLE_COMPLEXITY_VALIDATION,
    GRAPHQL_ENABLE_VALIDATION_CACHE,
    GRAPHQL_VALIDATION_CACHE_TTL,

    # Introspection control
    GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION,

    # CSRF protection
    GRAPHQL_CSRF_HEADER_NAMES,

    # Origin validation
    GRAPHQL_ALLOWED_ORIGINS,
    GRAPHQL_STRICT_ORIGIN_VALIDATION,
    GRAPHQL_ORIGIN_VALIDATION,

    # Security logging
    GRAPHQL_SECURITY_LOGGING,

    # JWT authentication
    GRAPHQL_JWT,
)

# Validation: Ensure GraphQL settings loaded correctly
assert GRAPHQL_PATHS, "GraphQL settings not loaded - check security/graphql.py import"

# ============================================================================
# WEBSOCKET CONFIGURATION
# ============================================================================
# WebSocket settings are centralized in websocket.py for clean separation
# This includes JWT authentication, throttling, origin validation, and token binding
# ============================================================================

from .websocket import (
    # Authentication
    WEBSOCKET_JWT_AUTH_ENABLED,
    WEBSOCKET_JWT_COOKIE_NAME,
    WEBSOCKET_JWT_CACHE_TIMEOUT,

    # Throttling
    WEBSOCKET_THROTTLE_LIMITS,
    WEBSOCKET_CONNECTION_TIMEOUT,

    # Heartbeat & Presence
    WEBSOCKET_HEARTBEAT_INTERVAL,
    WEBSOCKET_PRESENCE_TIMEOUT,
    WEBSOCKET_AUTO_RECONNECT_ENABLED,
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS,
    WEBSOCKET_RECONNECT_BASE_DELAY,

    # Origin Validation
    WEBSOCKET_ORIGIN_VALIDATION_ENABLED,
    WEBSOCKET_ALLOWED_ORIGINS,

    # Token Binding
    WEBSOCKET_TOKEN_BINDING_ENABLED,
    WEBSOCKET_TOKEN_BINDING_STRICT,

    # Logging
    WEBSOCKET_LOG_AUTH_ATTEMPTS,
    WEBSOCKET_LOG_AUTH_FAILURES,
    WEBSOCKET_STREAM_TESTBENCH_ENABLED,
)

# Tool configurations
SHELL_PLUS_PRINT_SQL = True
GRAPH_MODELS = {"all_applications": True, "group_models": True}
IMPORT_EXPORT_USE_TRANSACTIONS = True
TAGGIT_CASE_INSENSITIVE = True
LOGIN_URL = "login"
SITE_ID = 1
TEST_RUNNER = "apps.core.test_runner.TenantAwareTestRunner"

# DateTime formats
DATETIME_INPUT_FORMATS = ["%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M"]
DATE_INPUT_FORMATS = ["%d-%b-%Y", "%d/%b/%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z"]

# Admin and basic settings
ADMINS = [("wed_dev", "satyam.warghat@youtility.in"), ("wed_dev", "pankaj.pal@youtility.in"),
          ("wed_dev", "manohar.lagishetty@youtility.in"), ("business_manger", "namrata.shahid@youtility.in"), ("business_manager", "ashish.mhashilkar@youtility.in")]
# Import security headers from centralized module (prevents duplication)
from .security.headers import (
    REFERRER_POLICY,
    X_FRAME_OPTIONS,
    PERMISSIONS_POLICY,
)

# Session and security configuration
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 2 * 60 * 60  # 2 hours (Rule #10: Session Security Standards)
SESSION_SAVE_EVERY_REQUEST = True  # Security first (Rule #10)

# Note: SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE, CSRF_COOKIE_HTTPONLY, CSRF_COOKIE_SAMESITE
# are imported from security/headers.py above (lines 114-134)
WHITENOISE_USE_FINDERS = True
CACHE_TTL = 60 * 1

# Select2 configuration
SELECT2_JS = ""
SELECT2_CSS = ""
SELECT2_I18N_PATH = "assets/plugins/custom/select2-4.x/js/i18n"

# ============================================================================
# HELPBOT CONFIGURATION
# ============================================================================

# HelpBot core settings
HELPBOT_ENABLED = True
HELPBOT_AUTO_INDEX_ON_STARTUP = False  # Set to True for auto-indexing on startup
HELPBOT_VOICE_ENABLED = True  # Enable voice interactions
HELPBOT_MAX_MESSAGE_LENGTH = 2000  # Maximum message length in characters
HELPBOT_SESSION_TIMEOUT_MINUTES = 60  # Session timeout in minutes
HELPBOT_MAX_CONTEXT_MESSAGES = 10  # Max messages to include in conversation context
HELPBOT_CACHE_TIMEOUT = 3600  # Cache timeout in seconds (1 hour)
HELPBOT_ANALYTICS_CACHE_TIMEOUT = 1800  # Analytics cache timeout (30 minutes)

# HelpBot knowledge base settings
HELPBOT_KNOWLEDGE_AUTO_UPDATE = True  # Auto-update knowledge base from docs
HELPBOT_MAX_KNOWLEDGE_RESULTS = 10  # Maximum search results to return
HELPBOT_KNOWLEDGE_EFFECTIVENESS_THRESHOLD = 0.3  # Min effectiveness to show results

# HelpBot supported languages (integrates with existing localization)
HELPBOT_LANGUAGES = ['en', 'hi', 'es', 'fr']  # Add more as needed

# HelpBot integration with existing AI services
HELPBOT_TXTAI_INTEGRATION = True  # Enable txtai semantic search integration
HELPBOT_LLM_INTEGRATION = True  # Enable LLM service integration
HELPBOT_VOICE_INTEGRATION = True  # Enable voice service integration

# HelpBot performance settings
HELPBOT_ANALYTICS_BATCH_SIZE = 100  # Batch size for analytics processing
HELPBOT_CONTEXT_TIMEOUT_MINUTES = 30  # Context tracking timeout
HELPBOT_MAX_JOURNEY_LENGTH = 20  # Maximum user journey entries to track

# HelpBot UI settings
HELPBOT_WIDGET_POSITION = 'bottom-right'  # Widget position on page
HELPBOT_WIDGET_THEME = 'modern'  # UI theme (modern, classic, minimal)
HELPBOT_SHOW_TYPING_INDICATOR = True  # Show typing indicator during AI response
HELPBOT_ENABLE_QUICK_SUGGESTIONS = True  # Show quick suggestion buttons