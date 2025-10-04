"""
Installed Apps Configuration

Centralized INSTALLED_APPS configuration.
Extracted from base.py for Rule #6 compliance.

Organization:
1. Django core apps
2. Third-party dependencies
3. Project core apps
4. Business domain apps
5. Integration apps
6. Testing and monitoring apps

Author: Claude Code
Date: 2025-10-01
"""

# Application definition
INSTALLED_APPS = [
    # ========================================================================
    # Django Core Apps
    # ========================================================================
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",  # PostGIS support

    # ========================================================================
    # Third-Party Apps
    # ========================================================================
    # GraphQL
    "graphene_django",
    "graphene_gis",
    "graphql_jwt.refresh_token.apps.RefreshTokenConfig",

    # Admin and Forms
    "import_export",
    "django_extensions",
    "django_select2",
    "django_filters",

    # REST Framework
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "drf_spectacular_sidecar",

    # Background Tasks
    "django_celery_beat",
    "django_celery_results",

    # WebSockets and Real-time
    "channels",
    "daphne",

    # Utilities
    "django_email_verification",
    "corsheaders",
    "django_cleanup.apps.CleanupConfig",  # Automatic file cleanup

    # ========================================================================
    # Project Core Apps (Infrastructure)
    # ========================================================================
    'apps.core',           # Core utilities, middleware, security
    'apps.peoples',        # Authentication and user management
    'apps.tenants',        # Multi-tenancy support
    'apps.onboarding',     # Onboarding workflows
    'apps.onboarding_api', # Onboarding API layer
    'apps.people_onboarding',  # People-specific onboarding

    # ========================================================================
    # Business Domain Apps
    # ========================================================================
    # Operations
    'apps.attendance',     # Employee attendance tracking
    'apps.activity',       # Task and activity management
    'apps.schedhuler',     # Scheduling and calendar
    'apps.reminder',       # Reminder system

    # Work Management
    'apps.work_order_management',  # Work orders
    'apps.y_helpdesk',            # Help desk and tickets

    # Reporting and Analytics
    'apps.reports',        # Reporting engine

    # ========================================================================
    # Integration Apps
    # ========================================================================
    'apps.service',        # GraphQL service layer
    'apps.api',            # REST API layer
    'apps.mqtt',           # IoT device communication
    'apps.face_recognition',   # Biometric authentication
    'apps.voice_recognition',  # Voice biometric

    # ========================================================================
    # Wellness and AI Features
    # ========================================================================
    'apps.journal',        # Journal and wellness tracking
    'apps.wellness',       # Wellness programs

    # ========================================================================
    # Testing and Monitoring Apps
    # ========================================================================
    'apps.streamlab',      # Stream testing infrastructure
    'apps.issue_tracker',  # Issue knowledge base
    'apps.ai_testing',     # AI-powered testing
    'apps.search',         # Search functionality
    'apps.noc',            # Network Operations Center
    'apps.helpbot',        # AI helpbot

    # System Monitoring
    'monitoring',          # System monitoring and metrics
]

# Custom user model
AUTH_USER_MODEL = 'peoples.People'

__all__ = [
    'INSTALLED_APPS',
    'AUTH_USER_MODEL',
]
