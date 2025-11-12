from django.apps import AppConfig


class ReportGenerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.report_generation'
    verbose_name = 'Intelligent Report Generation'

    def ready(self):
        """Initialize app signals and services."""
        pass
