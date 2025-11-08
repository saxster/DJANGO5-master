"""Dashboard app configuration."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dashboard'
    verbose_name = 'Real-Time Dashboard'

    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.dashboard.signals  # noqa: F401
        except ImportError:
            pass
