from django.apps import AppConfig


class WellnessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wellness'
    verbose_name = 'Wellness Education System'

    def ready(self):
        """Initialize wellness app signals and content delivery systems"""
