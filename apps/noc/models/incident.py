"""
NOC Incident Model.

Thin wrapper linking alerts to tickets/work orders for incident management.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.db.models import Count, Prefetch
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.core.models import BaseModel
from ..constants import INCIDENT_STATES

__all__ = ['NOCIncident', 'OptimizedIncidentManager']


class OptimizedIncidentManager(TenantAwareManager):
    """Manager with optimized querysets for common operations."""
    
    def with_full_details(self):
        """All related data for detail views."""
        from apps.noc.models import NOCAlertEvent
        return self.select_related(
            'assigned_to', 'client', 'site', 'created_by', 'ticket', 'work_order'
        ).prefetch_related(
            Prefetch('alerts', 
                queryset=NOCAlertEvent.objects.select_related('device', 'reported_by', 'bu')
            )
        )
    
    def with_counts(self):
        """Annotated counts for list views."""
        return self.annotate(
            alert_count=Count('alerts', distinct=True)
        )
    
    def for_export(self):
        """Minimal data for CSV export with counts."""
        return self.select_related(
            'assigned_to', 'client', 'site'
        ).annotate(
            alert_count=Count('alerts', distinct=True)
        )
    
    def active_incidents(self):
        """Active incidents with optimized queries."""
        return self.with_counts().filter(
            state__in=['NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'IN_PROGRESS']
        )


class NOCIncident(TenantAwareModel, BaseModel):
    """
    Incident wrapping one or more related alerts.

    Provides optional linkage to existing ticket/work order systems
    for incident tracking and resolution workflows.

    State Machine:
    NEW → ACKNOWLEDGED → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
    """

    STATE_CHOICES = INCIDENT_STATES

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        verbose_name=_("Client")
    )
    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='noc_incidents',
        verbose_name=_("Site")
    )

    title = models.CharField(
        max_length=255,
        verbose_name=_("Incident Title")
    )
    description = models.TextField(
        verbose_name=_("Incident Description")
    )
    severity = models.CharField(
        max_length=20,
        choices=[
            ('CRITICAL', 'Critical'),
            ('HIGH', 'High'),
            ('MEDIUM', 'Medium'),
            ('LOW', 'Low'),
            ('INFO', 'Informational'),
        ],
        default='MEDIUM',
        verbose_name=_("Severity")
    )
    metadata = models.JSONField(
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Enrichment context and additional metadata")
    )

    alerts = models.ManyToManyField(
        'noc.NOCAlertEvent',
        related_name='incidents',
        verbose_name=_("Alerts"),
        help_text=_("Alerts grouped into this incident")
    )

    ticket = models.ForeignKey(
        'y_helpdesk.Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Linked Ticket")
    )
    work_order = models.ForeignKey(
        'work_order_management.Wom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Linked Work Order")
    )

    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default='NEW',
        verbose_name=_("State")
    )
    assigned_to = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Assigned To")
    )
    priority = models.CharField(
        max_length=20,
        verbose_name=_("Priority")
    )

    sla_target = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("SLA Target Time")
    )
    resolution_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Resolution Notes")
    )
    runbook_link = models.URLField(
        null=True,
        blank=True,
        verbose_name=_("Runbook Link"),
        help_text=_("Link to resolution runbook or wiki")
    )

    time_to_ack = models.DurationField(null=True, blank=True)
    time_to_assign = models.DurationField(null=True, blank=True)
    time_to_resolve = models.DurationField(null=True, blank=True)

    objects = OptimizedIncidentManager()

    class Meta:
        db_table = 'noc_incident'
        verbose_name = _("NOC Incident")
        verbose_name_plural = _("NOC Incidents")
        indexes = [
            models.Index(fields=['tenant', 'state', '-cdtz'], name='noc_incident_tenant_state'),
            models.Index(fields=['client', 'state'], name='noc_incident_client_state'),
        ]
        ordering = ['-cdtz']

    def __str__(self) -> str:
        alert_count = self.alerts.count() if self.pk else 0
        return f"Incident #{self.id}: {alert_count} alerts ({self.state})"
