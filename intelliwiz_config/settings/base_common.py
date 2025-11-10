"""
Common Django Settings - Shared Across All Environments

Contains core Django configuration that applies universally:
- Path configuration (BASE_DIR)
- Placeholder SECRET_KEY (overridden in environment-specific settings)
- Internationalization settings
- DateTime formats
- Authentication configuration
- Session settings
- Message tags and logging
"""

from pathlib import Path
import os
from datetime import timedelta
from django.contrib.messages import constants as message_constants
from django.core.management.utils import get_random_secret_key
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# CRITICAL: Placeholder SECRET_KEY (overridden in development.py/production.py)
# Some apps access settings.SECRET_KEY during import, so we need this placeholder
SECRET_KEY = os.environ.get('SECRET_KEY', get_random_secret_key())

# Root URL configuration
ROOT_URLCONF = "intelliwiz_config.urls"

# WSGI and ASGI application
WSGI_APPLICATION = "intelliwiz_config.wsgi.application"
ASGI_APPLICATION = "intelliwiz_config.asgi.application"

# ============================================================================
# INTERNATIONALIZATION & LOCALIZATION
# ============================================================================

LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"

LANGUAGES = [
    ('en', 'English'),
    ('hi', 'हिन्दी'),
    ('te', 'తెలుగు'),
    ('ta', 'தமிழ்'),
    ('kn', 'ಕನ್ನಡ'),
    ('mr', 'मराठी'),
    ('gu', 'ગુજરાતી'),
    ('bn', 'বাংলা'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
    BASE_DIR / 'apps' / 'core' / 'locale',
    BASE_DIR / 'apps' / 'peoples' / 'locale',
    BASE_DIR / 'apps' / 'attendance' / 'locale',
    BASE_DIR / 'apps' / 'activity' / 'locale',
    BASE_DIR / 'apps' / 'scheduler' / 'locale',
    BASE_DIR / 'apps' / 'client_onboarding' / 'locale',
    BASE_DIR / 'apps' / 'site_onboarding' / 'locale',
    BASE_DIR / 'apps' / 'core_onboarding' / 'locale',
    BASE_DIR / 'apps' / 'reports' / 'locale',
    BASE_DIR / 'apps' / 'y_helpdesk' / 'locale',
    BASE_DIR / 'apps' / 'work_order_management' / 'locale',
]

# ============================================================================
# DATETIME CONFIGURATION
# ============================================================================

DATETIME_INPUT_FORMATS = ["%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M"]
DATE_INPUT_FORMATS = ["%d-%b-%Y", "%d/%b/%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z"]

# ============================================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

AUTH_USER_MODEL = "peoples.People"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
     'OPTIONS': {'user_attributes': ('username', 'email', 'first_name', 'last_name'), 'max_similarity': 0.7}},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================================
# SESSION & SECURITY COOKIE CONFIGURATION
# ============================================================================

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 2 * SECONDS_IN_HOUR  # 2 hours
SESSION_SAVE_EVERY_REQUEST = True

# Import cookie security settings from centralized security module
from .security.headers import (
    CSRF_COOKIE_SECURE,
    CSRF_COOKIE_HTTPONLY,
    CSRF_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    LANGUAGE_COOKIE_NAME,
    LANGUAGE_COOKIE_AGE,
    LANGUAGE_COOKIE_DOMAIN,
    LANGUAGE_COOKIE_PATH,
    LANGUAGE_COOKIE_SECURE,
    LANGUAGE_COOKIE_HTTPONLY,
    LANGUAGE_COOKIE_SAMESITE,
    LANGUAGE_SESSION_KEY,
    REFERRER_POLICY,
    X_FRAME_OPTIONS,
    PERMISSIONS_POLICY,
)

# ============================================================================
# TEMPLATE CONFIGURATION
# ============================================================================

JINJA_TEMPLATES = os.path.join(BASE_DIR, "frontend/templates")
CONTEXT_PROCESSORS = [
    "apps.peoples.context_processors.app_settings",
    "django.template.context_processors.debug",
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "django.template.context_processors.media",
    "apps.helpbot.context_processors.helpbot_context",
]

TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates",
     "DIRS": [os.path.join(BASE_DIR, "templates")],
     "APP_DIRS": True,
     "OPTIONS": {"context_processors": CONTEXT_PROCESSORS}},
    {"BACKEND": "django.template.backends.jinja2.Jinja2",
     "DIRS": [JINJA_TEMPLATES],
     "APP_DIRS": True,
     "OPTIONS": {"extensions": ["jinja2.ext.loopcontrols"],
                 "autoescape": True,
                 "auto_reload": True,
                 "environment": "intelliwiz_config.jinja.env.JinjaEnvironment",
                 "context_processors": CONTEXT_PROCESSORS}},
]

# ============================================================================
# STATIC & MEDIA FILES
# ============================================================================

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "frontend/static")]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder"
]
MEDIA_URL = "/media/"

# ============================================================================
# DATABASE & ORM CONFIGURATION
# ============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASE_ROUTERS = ["apps.tenants.middlewares.TenantDbRouter"]

# GeoDjango configuration (PostGIS support)
from .geodjango import (
    GDAL_LIBRARY_PATH,
    GEOS_LIBRARY_PATH,
)

# ============================================================================
# ADMIN & MESSAGES
# ============================================================================

ADMINS = [
    ("wed_dev", "satyam.warghat@youtility.in"),
    ("wed_dev", "pankaj.pal@youtility.in"),
    ("wed_dev", "manohar.lagishetty@youtility.in"),
    ("business_manger", "namrata.shahid@youtility.in"),
    ("business_manager", "ashish.mhashilkar@youtility.in"),
]

MESSAGE_TAGS = {
    message_constants.DEBUG: "alert-info",
    message_constants.INFO: "alert-info",
    message_constants.SUCCESS: "alert-success",
    message_constants.WARNING: "alert-warning",
    message_constants.ERROR: "alert-danger"
}

LOGIN_URL = "login"
SITE_ID = 1
TEST_RUNNER = "apps.core.test_runner.TenantAwareTestRunner"

# Agent communication defaults (per-tenant tone overrides)
AGENT_TONE_PROFILE_OVERRIDES = {}

# ============================================================================
# DEVELOPER TOOLS
# ============================================================================

SHELL_PLUS_PRINT_SQL = True
GRAPH_MODELS = {"all_applications": True, "group_models": True}
IMPORT_EXPORT_USE_TRANSACTIONS = True
TAGGIT_CASE_INSENSITIVE = True

# ============================================================================
# SELECT2 CONFIGURATION
# ============================================================================

SELECT2_JS = ""
SELECT2_CSS = ""
SELECT2_I18N_PATH = "assets/plugins/custom/select2-4.x/js/i18n"

# ============================================================================
# CACHING
# ============================================================================

WHITENOISE_USE_FINDERS = True
CACHE_TTL = 60 * 1

# ============================================================================
# API MIGRATION FLAGS
# ============================================================================

from .api_migration_flags import API_MIGRATION_FEATURE_FLAGS

# Feature flags
ENABLE_ACTIVITY_STREAMING = os.environ.get('ENABLE_ACTIVITY_STREAMING', 'true').lower() not in {'false', '0', 'no'}

__all__ = [
    'BASE_DIR',
    'SECRET_KEY',
    'ROOT_URLCONF',
    'WSGI_APPLICATION',
    'ASGI_APPLICATION',
    'AUTH_USER_MODEL',
    'LANGUAGE_CODE',
    'USE_I18N',
    'USE_TZ',
    'TIME_ZONE',
    'LANGUAGES',
    'LOCALE_PATHS',
    'DATETIME_INPUT_FORMATS',
    'DATE_INPUT_FORMATS',
    'AUTHENTICATION_BACKENDS',
    'AUTH_PASSWORD_VALIDATORS',
    'SESSION_ENGINE',
    'SESSION_EXPIRE_AT_BROWSER_CLOSE',
    'SESSION_COOKIE_AGE',
    'SESSION_SAVE_EVERY_REQUEST',
    'TEMPLATES',
    'STATIC_URL',
    'STATICFILES_DIRS',
    'STATICFILES_FINDERS',
    'MEDIA_URL',
    'DEFAULT_AUTO_FIELD',
    'DATABASE_ROUTERS',
    'ADMINS',
    'MESSAGE_TAGS',
    'LOGIN_URL',
    'SITE_ID',
    'TEST_RUNNER',
]
