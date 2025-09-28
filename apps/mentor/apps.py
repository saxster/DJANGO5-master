import os
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class MentorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mentor'
    verbose_name = 'AI Mentor System'

    def ready(self):
        # Ensure mentor is only enabled in development/test environments
        if not self._is_dev_environment():
            raise ImproperlyConfigured(
                "AI Mentor system should only be enabled in development/test environments. "
                "Set MENTOR_ENABLED=1 and DEBUG=True to use this app."
            )

        # Import signal handlers
        from . import signals

    def _is_dev_environment(self):
        """Check if we're in a development environment where mentor should run."""
        from django.conf import settings

        mentor_enabled = os.environ.get('MENTOR_ENABLED') == '1'
        debug_mode = getattr(settings, 'DEBUG', False)

        return mentor_enabled and debug_mode