"""
Security Intelligence Django App Configuration.
"""

from django.apps import AppConfig


class SecurityIntelligenceConfig(AppConfig):
    """Security Intelligence app configuration."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.noc.security_intelligence'
    label = 'noc_security_intelligence'
    verbose_name = 'NOC Security Intelligence'

    def ready(self):
        """Import signal handlers when app is ready."""
        import apps.noc.security_intelligence.signals