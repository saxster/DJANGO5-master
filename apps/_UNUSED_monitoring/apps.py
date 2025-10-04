"""
Monitoring App Configuration
"""

from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.monitoring'
    verbose_name = 'Operational Monitoring'

    def ready(self):
        """Initialize monitoring system components"""
        import apps.monitoring.signals

        # Initialize monitoring engines on startup
        from apps.monitoring.services.monitoring_service import MonitoringService
        MonitoringService.initialize()