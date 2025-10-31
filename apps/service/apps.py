from django.apps import AppConfig


class ServiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.service"

    def ready(self):
        """Initialize service app components on startup."""
        # Placeholder for future startup hooks (intentionally left blank)
        return None
