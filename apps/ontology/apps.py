"""
Django app configuration for the ontology system.
"""

from django.apps import AppConfig


class OntologyConfig(AppConfig):
    """Configuration for the ontology app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ontology"
    verbose_name = "Ontology System"

    def ready(self):
        """
        Perform app initialization tasks.

        This method is called when Django starts and the app is ready.
        """
        # Import signal handlers and other initialization code
        # Import models to register them with the ontology system
        try:
            from apps.ontology import signals  # noqa: F401
        except ImportError:
            pass
