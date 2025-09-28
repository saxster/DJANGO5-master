from django.apps import AppConfig


class JournalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.journal'
    verbose_name = 'Journal & Wellness System'

    def ready(self):
        """Initialize journal app signals and background tasks"""
