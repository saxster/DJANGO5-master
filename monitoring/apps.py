"""
Monitoring app configuration.
"""

from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'
    verbose_name = 'Production Monitoring'
    
    def ready(self):
        """Initialize monitoring when app is ready"""
        # Import signal handlers
        from . import signals