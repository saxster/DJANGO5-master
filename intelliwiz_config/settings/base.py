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
    'apps.core', 'apps.peoples', 'apps.onboarding', 'apps.onboarding_api', 'apps.tenants',
    'apps.attendance', 'apps.activity', 'apps.schedhuler', 'apps.reminder', 'apps.reports',
    'apps.service', 'apps.y_helpdesk', 'apps.work_order_management', 'apps.mqtt', 'apps.face_recognition',
    'apps.journal', 'apps.wellness', 'apps.streamlab', 'apps.issue_tracker', 'apps.ai_testing',
]

# Base middleware configuration
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.error_handling.CorrelationIDMiddleware",
    "apps.core.middleware.logging_sanitization.LogSanitizationMiddleware",
    "apps.core.middleware.api_deprecation.APIDeprecationMiddleware",
    "apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware",
    "apps.core.middleware.graphql_rate_limiting.GraphQLRateLimitingMiddleware",
    "apps.core.middleware.path_based_rate_limiting.RateLimitMonitoringMiddleware",
    "apps.core.sql_security.SQLInjectionProtectionMiddleware",
    "apps.core.xss_protection.XSSProtectionMiddleware",
    "apps.core.middleware.graphql_csrf_protection.GraphQLCSRFProtectionMiddleware",
    "apps.core.middleware.graphql_csrf_protection.GraphQLSecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.onboarding.middlewares.TimezoneMiddleware",
    "apps.core.middleware.csp_nonce.CSPNonceMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.onboarding_api.middleware.OnboardingAPIMiddleware",
    "apps.onboarding_api.middleware.OnboardingAuditMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'apps.core.xss_protection.CSRFHeaderMiddleware',
    "apps.core.error_handling.GlobalExceptionMiddleware",
]

ROOT_URLCONF = "intelliwiz_config.urls"

# Template configuration
JINJA_TEMPLATES = os.path.join(BASE_DIR, "frontend/templates")
CONTEXT_PROCESSORS = [
    "apps.peoples.context_processors.app_settings", "django.template.context_processors.debug",
    "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages", "django.template.context_processors.media",
]

TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
     "OPTIONS": {"context_processors": CONTEXT_PROCESSORS}},
    {"BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": [JINJA_TEMPLATES], "APP_DIRS": True,
     "OPTIONS": {"extensions": ["jinja2.ext.loopcontrols"], "autoescape": False, "auto_reload": True,
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
USE_L10N = False
USE_TZ = True
TIME_ZONE = "UTC"
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
        "apps.service.middleware.graphql_auth.GraphQLAuthenticationMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLTenantValidationMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLMutationChainingProtectionMiddleware",
        "apps.service.middleware.graphql_auth.GraphQLIntrospectionControlMiddleware",
    ]
}
GRAPHQL_JWT = {"JWT_VERIFY_EXPIRATION": False, "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=2), "JWT_LONG_RUNNING_REFRESH_TOKEN": True}

# GraphQL Security Configuration (CVSS 7.2 vulnerability fix - comprehensive)
GRAPHQL_PATHS = ['/api/graphql/', '/graphql/', '/graphql']
ENABLE_GRAPHQL_RATE_LIMITING = True
GRAPHQL_RATE_LIMIT_MAX = 100
GRAPHQL_RATE_LIMIT_WINDOW = 300  # 5 minutes
GRAPHQL_MAX_QUERY_DEPTH = 10
GRAPHQL_MAX_QUERY_COMPLEXITY = 1000
GRAPHQL_MAX_MUTATIONS_PER_REQUEST = 5
GRAPHQL_STRICT_ORIGIN_VALIDATION = False
GRAPHQL_CSRF_HEADER_NAMES = ['HTTP_X_CSRFTOKEN', 'HTTP_X_CSRF_TOKEN']
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = True
GRAPHQL_SECURITY_LOGGING = {
    "ENABLE_REQUEST_LOGGING": True,
    "ENABLE_MUTATION_LOGGING": True,
    "ENABLE_FIELD_ACCESS_LOGGING": True,
    "ENABLE_OBJECT_ACCESS_LOGGING": True,
}

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
REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
PERMISSIONS_POLICY = {"geolocation": "()", "camera": "()", "microphone": "()", "payment": "()", "usb": "()"}

# Session and security
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 2 * 60 * 60  # 2 hours (Rule #10: Session Security Standards)
SESSION_SAVE_EVERY_REQUEST = True  # Security first (Rule #10)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
WHITENOISE_USE_FINDERS = True
CACHE_TTL = 60 * 1

# Select2 configuration
SELECT2_JS = ""
SELECT2_CSS = ""
SELECT2_I18N_PATH = "assets/plugins/custom/select2-4.x/js/i18n"