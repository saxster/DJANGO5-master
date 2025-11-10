from django.apps import AppConfig


class SecurityIntelligenceLegacyConfig(AppConfig):
    """
    Provides the old ``security_intelligence`` app label for backward
    compatibility while reusing the real models and signals from
    ``apps.noc.security_intelligence``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.security_intelligence"
    label = "security_intelligence"
    verbose_name = "Security Intelligence (Legacy)"

    def ready(self):
        # Import the modern signals so behavior stays consistent.
        try:
            import apps.noc.security_intelligence.signals  # noqa: F401
        except ImportError:
            pass
