"""
NOC Metric Snapshot Model.

Stores time-windowed aggregated metrics for NOC dashboard drill-down capabilities.
Follows .claude/rules.md Rule #7 (models <150 lines) and Rule #12 (query optimization).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['NOCMetricSnapshot']


class NOCMetricSnapshot(TenantAwareModel, BaseModel):
    """
    Time-windowed metric snapshot for NOC dashboard.

    Provides multi-dimensional aggregation support:
    - Client-level rollup
    - Business unit drill-down
    - Officer in charge filtering
    - Geographic aggregation (city, state)
    - Group-based filtering

    Metrics Categories:
    - Tickets: open, overdue, priority distribution
    - Work Orders: pending, overdue, status mix
    - Attendance: present, missing, late, expected
    - Devices: offline, alerts, total count
    - Geofences: breach events count
    - Sync Health: health score percentage
    - Security: anomaly count
    """

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        verbose_name=_("Client"),
        help_text=_("Root client business unit")
    )
    bu = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='noc_metrics',
        verbose_name=_("Business Unit"),
        help_text=_("Specific business unit for drill-down")
    )
    oic = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Officer in Charge"),
        help_text=_("Site officer in charge for filtering")
    )
    city = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("City")
    )
    state = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("State")
    )
    pgroup = models.ForeignKey(
        'peoples.Pgroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("People Group")
    )

    window_start = models.DateTimeField(
        db_index=True,
        verbose_name=_("Window Start Time")
    )
    window_end = models.DateTimeField(
        db_index=True,
        verbose_name=_("Window End Time")
    )
    computed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Computed Timestamp")
    )

    tickets_open = models.IntegerField(default=0, verbose_name=_("Open Tickets"))
    tickets_overdue = models.IntegerField(default=0, verbose_name=_("Overdue Tickets"))
    tickets_by_priority = models.JSONField(
        default=dict,
        verbose_name=_("Tickets by Priority"),
        help_text=_("Distribution: {'LOW': 5, 'MEDIUM': 10, 'HIGH': 3}")
    )

    work_orders_pending = models.IntegerField(default=0, verbose_name=_("Pending Work Orders"))
    work_orders_overdue = models.IntegerField(default=0, verbose_name=_("Overdue Work Orders"))
    work_orders_status_mix = models.JSONField(
        default=dict,
        verbose_name=_("Work Order Status Mix")
    )

    attendance_present = models.IntegerField(default=0, verbose_name=_("Present Count"))
    attendance_missing = models.IntegerField(default=0, verbose_name=_("Missing Count"))
    attendance_late = models.IntegerField(default=0, verbose_name=_("Late Count"))
    attendance_expected = models.IntegerField(default=0, verbose_name=_("Expected Count"))

    device_health_offline = models.IntegerField(default=0, verbose_name=_("Offline Devices"))
    device_health_alerts = models.IntegerField(default=0, verbose_name=_("Device Alerts"))
    device_health_total = models.IntegerField(default=0, verbose_name=_("Total Devices"))

    geofence_events_count = models.IntegerField(default=0, verbose_name=_("Geofence Events"))
    sync_health_score = models.FloatField(default=100.0, verbose_name=_("Sync Health Score"))
    security_anomalies = models.IntegerField(default=0, verbose_name=_("Security Anomalies"))

    class Meta:
        db_table = 'noc_metric_snapshot'
        verbose_name = _("NOC Metric Snapshot")
        verbose_name_plural = _("NOC Metric Snapshots")
        indexes = [
            models.Index(fields=['tenant', 'client', 'window_end'], name='noc_metric_tenant_client'),
            models.Index(fields=['tenant', 'window_end'], name='noc_metric_tenant_time'),
            models.Index(fields=['city', 'window_end'], name='noc_metric_city_time'),
            models.Index(fields=['state', 'window_end'], name='noc_metric_state_time'),
            models.Index(fields=['oic', 'window_end'], name='noc_metric_oic_time'),
        ]
        ordering = ['-window_end']

    def __str__(self) -> str:
        return f"Metrics: {self.client.buname} @ {self.window_end}"

    def is_stale(self, threshold_minutes=10) -> bool:
        """Check if this snapshot is older than threshold minutes."""
        from datetime import timedelta
        age = timezone.now() - self.computed_at
        return age > timedelta(minutes=threshold_minutes)