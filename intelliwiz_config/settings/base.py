"""
Base Django settings for intelliwiz_config project.
Contains common settings shared across all environments.
"""

from pathlib import Path
import os
from datetime import timedelta
from django.contrib.messages import constants as message_constants
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ============================================================================
# CRITICAL: Set SECRET_KEY BEFORE INSTALLED_APPS
# ============================================================================
# Some apps (like django_email_verification) access settings.SECRET_KEY during
# import, so we need to set a placeholder here that will be overridden by
# development.py or production.py with validated values.
# ============================================================================
SECRET_KEY = os.environ.get('SECRET_KEY', get_random_secret_key())

# Application definition
INSTALLED_APPS = [
    # WebSocket support (must be before staticfiles)
    "daphne", "channels",
    # Modern admin interface (must precede the admin app config)
    "unfold", "unfold.contrib.filters", "unfold.contrib.forms", "unfold.contrib.inlines",
    # Django core apps
    "apps.core.admin.apps.IntelliWizAdminConfig", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "django.contrib.gis",
    # Third-party apps
    "django_email_verification", "import_export",
    "django_extensions", "django_select2", "django_filters", "rest_framework", "rest_framework_simplejwt",
    "drf_spectacular", "drf_spectacular_sidecar",
    "django_celery_beat",
    "django_celery_results", "corsheaders", "django_cleanup.apps.CleanupConfig",
    # Local apps
    'apps.core', 'apps.ontology', 'apps.peoples', 'apps.people_onboarding', 'apps.tenants',
    'apps.core_onboarding', 'apps.client_onboarding', 'apps.site_onboarding',
    'apps.attendance', 'apps.activity', 'apps.scheduler', 'apps.reminder', 'apps.reports',
    'apps.service', 'apps.y_helpdesk', 'apps.work_order_management', 'apps.mqtt', 'apps.face_recognition',
    'apps.voice_recognition', 'apps.journal', 'apps.wellness', 'apps.streamlab', 'apps.issue_tracker',
    'apps.ai_testing', 'apps.search', 'apps.api', 'apps.noc', 'apps.ml_training', 'apps.helpbot', 'monitoring',
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
    {"BACKEND": "django.template.backends.django.DjangoTemplates",
     "DIRS": [os.path.join(BASE_DIR, "templates")],
     "APP_DIRS": True,
     "OPTIONS": {"context_processors": CONTEXT_PROCESSORS}},
    {"BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": [JINJA_TEMPLATES], "APP_DIRS": True,
     "OPTIONS": {"extensions": ["jinja2.ext.loopcontrols"], "autoescape": True, "auto_reload": True,
                 "environment": "intelliwiz_config.jinja.env.JinjaEnvironment",
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
# DJANGO 5.x: USE_L10N removed (deprecated) - localization is always enabled
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
    BASE_DIR / 'apps' / 'scheduler' / 'locale',
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

# ============================================================================
# GEODJANGO CONFIGURATION (PostGIS Support)
# ============================================================================
# Import GDAL and GEOS library paths for GeoDjango spatial operations.
# Required for django.contrib.gis (enabled in INSTALLED_APPS line 17).
# Libraries must be installed via: brew install gdal geos postgis
# ============================================================================

from .geodjango import (
    GDAL_LIBRARY_PATH,
    GEOS_LIBRARY_PATH,
)

# REST migration feature flags
from .api_migration_flags import API_MIGRATION_FEATURE_FLAGS

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "frontend/static")]
STATICFILES_FINDERS = ["django.contrib.staticfiles.finders.FileSystemFinder", "django.contrib.staticfiles.finders.AppDirectoriesFinder"]
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication configuration
AUTH_USER_MODEL = "peoples.People"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# Custom message tags for Bootstrap
MESSAGE_TAGS = {message_constants.DEBUG: "alert-info", message_constants.INFO: "alert-info",
               message_constants.SUCCESS: "alert-success", message_constants.WARNING: "alert-warning", message_constants.ERROR: "alert-danger"}

# Database and routing
DATABASE_ROUTERS = ["apps.tenants.middlewares.TenantDbRouter"]

# ============================================================================
# KNOWLEDGE BASE SECURITY CONFIGURATION (Sprint 1-2)
# ============================================================================
# All knowledge base settings centralized in security/knowledge.py
# Includes: allowlisted sources, content sanitization, two-person approval
# ============================================================================

from .security.knowledge import (
    # Allowlisted sources
    KB_ALLOWED_SOURCES,

    # Document ingestion limits
    KB_MAX_DOCUMENT_SIZE_BYTES,
    KB_ALLOWED_MIME_TYPES,
    KB_MAX_CHUNKS_PER_DOCUMENT,
    KB_DEFAULT_CHUNK_SIZE,
    KB_DEFAULT_CHUNK_OVERLAP,

    # Content sanitization
    KB_ALLOWED_HTML_TAGS,
    KB_FORBIDDEN_PATTERNS,

    # Review workflow
    KB_REQUIRE_TWO_PERSON_APPROVAL,
    KB_MIN_ACCURACY_SCORE,
    KB_MIN_COMPLETENESS_SCORE,
    KB_MIN_RELEVANCE_SCORE,
    KB_AUTO_REJECT_THRESHOLD,

    # Search configuration
    KB_MAX_SEARCH_RESULTS,
    KB_DEFAULT_SEARCH_MODE,
    KB_AUTHORITY_WEIGHTS,
    KB_FRESHNESS_DECAY_DAYS,

    # Data retention
    KB_INGESTION_JOB_RETENTION_DAYS,
    KB_OLD_VERSION_RETENTION_DAYS,
    KB_REJECTED_DOCUMENT_RETENTION_DAYS,
)

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

# ============================================================================
# NOC INTELLIGENCE SYSTEM CONFIGURATION
# ============================================================================

# NOC Operational Intelligence Settings
NOC_CONFIG = {
    # Telemetry & API
    'TELEMETRY_CACHE_TTL': 60,  # seconds - Cache telemetry data
    'CORRELATION_WINDOW_MINUTES': 15,  # Time window for signal-to-alert correlation

    # Fraud Detection & ML
    'FRAUD_SCORE_TICKET_THRESHOLD': 0.80,  # Auto-create ticket if fraud score >= 80%
    'ML_MODEL_MIN_TRAINING_SAMPLES': 500,  # Minimum labeled samples for model training
    'ML_MODEL_VALIDATION_THRESHOLDS': {
        'precision': 0.85,  # Minimum precision to accept model
        'recall': 0.75,     # Minimum recall to accept model
        'f1': 0.80          # Minimum F1 score to accept model
    },
    'FRAUD_DEDUPLICATION_HOURS': 24,  # Max 1 fraud ticket per person per 24h

    # Audit & Escalation
    'AUDIT_FINDING_TICKET_SEVERITIES': ['CRITICAL', 'HIGH'],  # Auto-escalate these severities
    'TICKET_DEDUPLICATION_HOURS': 4,  # Max 1 ticket per finding type per 4h

    # Baseline Learning & Threshold Tuning
    'BASELINE_FP_THRESHOLD': 0.3,  # High false positive rate threshold (30%)
    'BASELINE_STABLE_SAMPLE_COUNT': 100,  # Sample count for "stable" baseline
    'BASELINE_DEFAULT_THRESHOLD': 3.0,  # Default z-score threshold
    'BASELINE_SENSITIVE_THRESHOLD': 2.5,  # Threshold for stable baselines (more sensitive)
    'BASELINE_CONSERVATIVE_THRESHOLD': 4.0,  # Threshold for high FP rate (less sensitive)

    # WebSocket & Real-Time
    'WEBSOCKET_RATE_LIMIT': 100,  # Max events per minute per tenant
    'WEBSOCKET_BROADCAST_TIMEOUT': 5,  # Seconds before broadcast times out
    'EVENT_LOG_RETENTION_DAYS': 90,  # Keep event logs for 90 days
}

# ============================================================================
# ML CONFIGURATION (PHASE 2)
# ============================================================================
# Machine Learning drift monitoring and auto-retraining configuration
# Feature flags, thresholds, and safeguards for automated ML operations
# ============================================================================

from .ml_config import ML_CONFIG

# ============================================================================
# UNFOLD ADMIN THEME CONFIGURATION
# ============================================================================
# Modern admin interface with organized model grouping and enhanced UX
# Configuration centralized in settings/unfold.py
# ============================================================================

from .unfold import UNFOLD
