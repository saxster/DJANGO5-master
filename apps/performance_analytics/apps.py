"""
Performance Analytics App Configuration
"""

from django.apps import AppConfig


class PerformanceAnalyticsConfig(AppConfig):
    """Performance Analytics application configuration."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.performance_analytics'
    verbose_name = 'Performance Analytics'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.performance_analytics.signals
        except ImportError:
            pass
