"""
Django app configuration for People Onboarding module.
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PeopleOnboardingConfig(AppConfig):
    """Configuration for the People Onboarding application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.people_onboarding'
    verbose_name = _('People Onboarding')

    def ready(self):
        """
        Initialize the app when Django starts.
        Import signal handlers and perform app setup.
        """
        # Import signal handlers
        try:
            import apps.people_onboarding.signals  # noqa: F401
        except ImportError:
            pass

        # Register Celery tasks
        try:
            import apps.people_onboarding.tasks  # noqa: F401
        except ImportError:
            pass