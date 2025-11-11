"""Voice Recognition App Configuration"""

from django.apps import AppConfig


class VoiceRecognitionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voice_recognition'
    verbose_name = 'Voice Recognition'

    def ready(self):
        # Import signal handlers for cache invalidation
        from . import signals  # noqa: F401
