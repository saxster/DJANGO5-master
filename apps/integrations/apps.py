"""Integrations app configuration."""

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integrations'
    verbose_name = 'External Integrations'

    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.integrations.signals  # noqa: F401
        except ImportError:
            pass
