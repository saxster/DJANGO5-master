"""
Django app configuration for ML Training platform.
"""

from django.apps import AppConfig


class MlTrainingConfig(AppConfig):
    """Configuration for ML Training app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ml_training'
    verbose_name = 'ML Training Data Platform'

    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.ml_training.signals  # noqa F401
        except ImportError:
            pass