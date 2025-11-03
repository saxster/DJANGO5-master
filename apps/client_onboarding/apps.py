from django.apps import AppConfig


class ClientOnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.client_onboarding'
    verbose_name = 'Client Onboarding'

    def ready(self):
        """Import signals when app is ready"""
        pass  # Signals imported here when needed
