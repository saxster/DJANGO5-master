from django.apps import AppConfig


class OnboardingApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.onboarding_api'
    verbose_name = 'Conversational Onboarding API'

    def ready(self):
        # Import any signal handlers or startup code here
        pass