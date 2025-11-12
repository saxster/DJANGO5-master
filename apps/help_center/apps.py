"""Django app configuration for Help Center."""

from django.apps import AppConfig


class HelpCenterConfig(AppConfig):
    """Configuration for Help Center application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.help_center'
    verbose_name = 'Help Center'

    def ready(self):
        """Import signal handlers when app is ready."""
        import apps.help_center.signals  # noqa: F401
