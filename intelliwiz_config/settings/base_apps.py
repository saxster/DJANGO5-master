"""
INSTALLED_APPS Configuration - Centralized

Single source of truth for all Django applications.
Organized by category:
- WebSocket support
- Admin interface
- Django core
- Third-party apps
- Local applications

DO NOT modify INSTALLED_APPS inline in other settings files.
Always import from this module.
"""

# ============================================================================
# INSTALLED_APPS - Complete List (Single Source of Truth)
# ============================================================================

INSTALLED_APPS = [
    # ========================================================================
    # WebSocket Support (must be before staticfiles)
    # ========================================================================
    "daphne",
    "channels",

    # ========================================================================
    # Modern Admin Interface (must precede admin app config)
    # ========================================================================
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",

    # ========================================================================
    # Django Core Applications
    # ========================================================================
    "apps.core.admin.apps.IntelliWizAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",

    # ========================================================================
    # Third-Party Applications
    # ========================================================================
    "django_email_verification",
    "import_export",
    "django_extensions",
    "django_select2",
    "django_filters",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "django_celery_beat",
    "django_celery_results",
    "corsheaders",
    "django_cleanup.apps.CleanupConfig",

    # Multi-Factor Authentication (MFA) Support
    "django_otp",
    "django_otp.plugins.otp_totp",

    # ========================================================================
    # Local Applications
    # ========================================================================
    "apps.core",
    "apps.ontology",
    "apps.peoples",
    "apps.people_onboarding",
    "apps.tenants",
    "apps.core_onboarding",
    "apps.client_onboarding",
    "apps.site_onboarding",
    "apps.attendance",
    "apps.activity",
    "apps.scheduler",
    "apps.reminder",
    "apps.reports",
    "apps.service",
    "apps.y_helpdesk",
    "apps.work_order_management",
    "apps.mqtt",
    "apps.face_recognition",
    "apps.voice_recognition",
    "apps.journal",
    "apps.wellness",
    "apps.streamlab",
    "apps.issue_tracker",
    "apps.ai_testing",
    "apps.search",
    "apps.api",
    "apps.noc",
    "apps.ml_training",
    "apps.helpbot",
    "apps.help_center",
    "monitoring",
]

__all__ = ['INSTALLED_APPS']
