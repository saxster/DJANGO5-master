"""Django app configuration for Help Center."""

from django.apps import AppConfig


class HelpCenterConfig(AppConfig):
    """Configuration for Help Center application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.help_center'
    verbose_name = 'Help Center'

    def ready(self):
        """Import signal handlers and register ontology components."""
        import apps.help_center.signals  # noqa: F401

        # Import services to trigger ontology registration
        try:
            from apps.help_center.services import (  # noqa: F401
                ai_assistant_service,
                search_service,
                knowledge_service,
                analytics_service,
                ticket_integration_service,
            )
        except (ImportError, RuntimeError):
            # Services may not be importable in all contexts (e.g., during migrations)
            pass
