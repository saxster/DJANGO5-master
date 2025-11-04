from django.apps import AppConfig


class CoreOnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core_onboarding'
    verbose_name = 'Core Onboarding Platform'

    def ready(self):
        """Import signals and initialize shared services"""
        pass
