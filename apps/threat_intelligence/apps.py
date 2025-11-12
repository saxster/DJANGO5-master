from django.apps import AppConfig


class ThreatIntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.threat_intelligence'
    verbose_name = 'Threat Intelligence'

    def ready(self):
        import apps.threat_intelligence.tasks  # noqa: Register Celery tasks
