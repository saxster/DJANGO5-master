"""
Network Operations Center (NOC) Application Configuration.

This Django app provides centralized multi-site monitoring with drill-down capabilities,
real-time alerting, incident management, and operational workflows for enterprise
facility management.

Key Features:
- Multi-tenant, RBAC-aware operations dashboard
- Real-time alert correlation and de-duplication
- Automated escalation workflows
- Comprehensive metric aggregation
- Maintenance window management
- Audit-compliant logging
"""

from django.apps import AppConfig


class NocConfig(AppConfig):
    """
    Django app configuration for Network Operations Center module.

    This app integrates with existing infrastructure:
    - Multi-tenant architecture (TenantAwareModel)
    - RBAC via UserCapabilityService
    - Real-time updates via Channels/WebSockets
    - Background processing via PostgreSQL Task Queue
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.noc'
    verbose_name = 'Network Operations Center'

    def ready(self):
        """
        Import signal handlers when Django starts.

        Signals trigger alert creation for:
        - Ticket SLA breaches and escalations
        - Missing attendance events
        - Device offline status changes
        """
        try:
            import apps.noc.signals
        except ImportError:
            pass