from django.apps import AppConfig


class SiteOnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site_onboarding'
    verbose_name = 'Site Onboarding'

    def ready(self):
        """Import signals when app is ready"""
        pass
