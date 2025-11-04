"""
NOC Maintenance Window Model.

Manages planned maintenance windows for alert suppression.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel

__all__ = ['MaintenanceWindow']


class MaintenanceWindow(TenantAwareModel, BaseModel):
    """
    Planned maintenance window for alert suppression.

    During active maintenance windows, alerts matching the suppression
    rules will be automatically suppressed to reduce alert noise.

    Suppression Strategies:
    - suppress_all: Suppress all alerts for this client/BU
    - suppress_alerts: List of specific alert types to suppress
    """

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Client"),
        help_text=_("Client for maintenance window (null = all clients)")
    )
    bu = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='noc_maintenance_windows',
        verbose_name=_("Business Unit"),
        help_text=_("Specific BU for maintenance (null = all BUs in client)")
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Maintenance Title")
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Description")
    )

    start_time = models.DateTimeField(
        verbose_name=_("Start Time"),
        help_text=_("Maintenance window start time")
    )
    end_time = models.DateTimeField(
        verbose_name=_("End Time"),
        help_text=_("Maintenance window end time")
    )

    suppress_all = models.BooleanField(
        default=False,
        verbose_name=_("Suppress All Alerts"),
        help_text=_("If True, suppress ALL alerts during this window")
    )
    suppress_alerts = models.JSONField(
        default=list,
        verbose_name=_("Suppress Alert Types"),
        help_text=_("List of alert type codes to suppress (e.g., ['DEVICE_OFFLINE', 'SYNC_DEGRADED'])")
    )

    reason = models.TextField(
        verbose_name=_("Reason"),
        help_text=_("Reason for maintenance window")
    )
    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Created By")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Can be deactivated to cancel maintenance")
    )

    class Meta:
        db_table = 'noc_maintenance_window'
        verbose_name = _("NOC Maintenance Window")
        verbose_name_plural = _("NOC Maintenance Windows")
        indexes = [
            models.Index(fields=['start_time', 'end_time'], name='noc_maint_time_range'),
            models.Index(fields=['client', 'start_time'], name='noc_maint_client_start'),
            models.Index(fields=['is_active', 'start_time'], name='noc_maint_active'),
        ]
        ordering = ['-start_time']

    def __str__(self) -> str:
        scope = self.client.buname if self.client else "All Clients"
        return f"Maintenance: {scope} ({self.start_time.strftime('%Y-%m-%d %H:%M')})"

    def is_currently_active(self) -> bool:
        """Check if this maintenance window is currently active."""
        now = timezone.now()
        return self.is_active and self.start_time <= now <= self.end_time

    def should_suppress_alert(self, alert_type: str) -> bool:
        """Check if given alert type should be suppressed during this window."""
        if not self.is_currently_active():
            return False
        if self.suppress_all:
            return True
        return alert_type in self.suppress_alerts