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
        Loads all ontology registrations including code quality patterns.
        """
        # Import signal handlers and other initialization code
        # Import models to register them with the ontology system
        try:
            from apps.ontology import signals  # noqa: F401
        except ImportError:
            pass
        
        # Load all ontology registrations
        try:
            from apps.ontology.registrations.code_quality_patterns import (
                register_code_quality_patterns,
            )
            from apps.ontology.registrations.november_2025_improvements import (
                register_november_2025_improvements,
            )
            
            # Register all patterns on startup
            register_code_quality_patterns()
            register_november_2025_improvements()
        except ImportError as e:
            # Log but don't fail startup
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load ontology registrations: {e}")
