from django.apps import AppConfig


class OnboardingLegacyConfig(AppConfig):
    """Minimal legacy app to keep old migrations/imports working."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.onboarding'
    label = 'onboarding'
    verbose_name = 'Onboarding (Legacy Compatibility)'
