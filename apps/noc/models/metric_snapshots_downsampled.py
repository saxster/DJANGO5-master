"""
NOC Downsampled Metric Models.

Multi-resolution time-series storage for 2-year analytics with 90% storage reduction.
Implements Prometheus-style downsampling strategy:
- 5-minute resolution: 7 days retention (NOCMetricSnapshot)
- 1-hour resolution: 90 days retention (NOCMetricSnapshot1Hour)
- 1-day resolution: 2 years retention (NOCMetricSnapshot1Day)

Follows .claude/rules.md Rule #7 (models <150 lines) and Rule #12 (query optimization).

@ontology(
    domain="noc",
    purpose="Time-series metric downsampling for long-term analytics and storage efficiency",
    retention_strategy={
        "5min": "7 days",
        "1hour": "90 days",
        "1day": "2 years"
    },
    storage_reduction="90%",
    tags=["noc", "metrics", "time-series", "downsampling", "analytics"]
)
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['NOCMetricSnapshot1Hour', 'NOCMetricSnapshot1Day']


class NOCMetricSnapshot1Hour(TenantAwareModel, BaseModel):
    """
    Hourly aggregated NOC metrics (90-day retention).

    Aggregates 12 5-minute snapshots into 1-hour windows.
    Stores avg, min, max, sum variants of each metric for comprehensive analysis.

    Storage: ~2,160 records per client (90 days × 24 hours)
    vs ~25,920 5-min records (90 days × 12 per hour × 24 hours)
    = 91.7% storage reduction
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
        related_name='noc_metrics_1hour',
        verbose_name=_("Business Unit")
    )
    oic = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Officer in Charge")
    )

    window_start = models.DateTimeField(db_index=True, verbose_name=_("Window Start"))
    window_end = models.DateTimeField(db_index=True, verbose_name=_("Window End"))
    computed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Computed At"))

    # Tickets - aggregated metrics
    tickets_open_avg = models.FloatField(default=0.0, verbose_name=_("Tickets Open (Avg)"))
    tickets_open_min = models.IntegerField(default=0, verbose_name=_("Tickets Open (Min)"))
    tickets_open_max = models.IntegerField(default=0, verbose_name=_("Tickets Open (Max)"))
    tickets_open_sum = models.IntegerField(default=0, verbose_name=_("Tickets Open (Sum)"))

    tickets_overdue_avg = models.FloatField(default=0.0, verbose_name=_("Tickets Overdue (Avg)"))
    tickets_overdue_min = models.IntegerField(default=0, verbose_name=_("Tickets Overdue (Min)"))
    tickets_overdue_max = models.IntegerField(default=0, verbose_name=_("Tickets Overdue (Max)"))
    tickets_overdue_sum = models.IntegerField(default=0, verbose_name=_("Tickets Overdue (Sum)"))

    # Work Orders - aggregated metrics
    work_orders_pending_avg = models.FloatField(default=0.0, verbose_name=_("Work Orders Pending (Avg)"))
    work_orders_pending_min = models.IntegerField(default=0, verbose_name=_("Work Orders Pending (Min)"))
    work_orders_pending_max = models.IntegerField(default=0, verbose_name=_("Work Orders Pending (Max)"))
    work_orders_pending_sum = models.IntegerField(default=0, verbose_name=_("Work Orders Pending (Sum)"))

    work_orders_overdue_avg = models.FloatField(default=0.0, verbose_name=_("Work Orders Overdue (Avg)"))
    work_orders_overdue_min = models.IntegerField(default=0, verbose_name=_("Work Orders Overdue (Min)"))
    work_orders_overdue_max = models.IntegerField(default=0, verbose_name=_("Work Orders Overdue (Max)"))
    work_orders_overdue_sum = models.IntegerField(default=0, verbose_name=_("Work Orders Overdue (Sum)"))

    # Attendance - aggregated metrics
    attendance_present_avg = models.FloatField(default=0.0, verbose_name=_("Present (Avg)"))
    attendance_present_min = models.IntegerField(default=0, verbose_name=_("Present (Min)"))
    attendance_present_max = models.IntegerField(default=0, verbose_name=_("Present (Max)"))
    attendance_present_sum = models.IntegerField(default=0, verbose_name=_("Present (Sum)"))

    attendance_missing_avg = models.FloatField(default=0.0, verbose_name=_("Missing (Avg)"))
    attendance_missing_min = models.IntegerField(default=0, verbose_name=_("Missing (Min)"))
    attendance_missing_max = models.IntegerField(default=0, verbose_name=_("Missing (Max)"))
    attendance_missing_sum = models.IntegerField(default=0, verbose_name=_("Missing (Sum)"))

    # Device Health - aggregated metrics
    device_health_offline_avg = models.FloatField(default=0.0, verbose_name=_("Offline Devices (Avg)"))
    device_health_offline_min = models.IntegerField(default=0, verbose_name=_("Offline Devices (Min)"))
    device_health_offline_max = models.IntegerField(default=0, verbose_name=_("Offline Devices (Max)"))

    sync_health_score_avg = models.FloatField(default=100.0, verbose_name=_("Sync Health Score (Avg)"))
    sync_health_score_min = models.FloatField(default=100.0, verbose_name=_("Sync Health Score (Min)"))

    # Security - aggregated metrics
    security_anomalies_avg = models.FloatField(default=0.0, verbose_name=_("Anomalies (Avg)"))
    security_anomalies_max = models.IntegerField(default=0, verbose_name=_("Anomalies (Max)"))
    security_anomalies_sum = models.IntegerField(default=0, verbose_name=_("Anomalies (Sum)"))

    class Meta:
        db_table = 'noc_metric_snapshot_1hour'
        verbose_name = _("NOC Metric Snapshot (1 Hour)")
        verbose_name_plural = _("NOC Metric Snapshots (1 Hour)")
        indexes = [
            models.Index(fields=['tenant', 'client', 'window_start'], name='noc_1h_tenant_client'),
            models.Index(fields=['tenant', 'window_start'], name='noc_1h_tenant_time'),
            models.Index(fields=['computed_at'], name='noc_1h_computed'),
        ]
        ordering = ['-window_start']

    def __str__(self) -> str:
        return f"1H Metrics: {self.client.buname} @ {self.window_start}"


class NOCMetricSnapshot1Day(TenantAwareModel, BaseModel):
    """
    Daily aggregated NOC metrics (2-year retention).

    Aggregates 24 1-hour snapshots into daily summaries.
    Enables long-term trend analysis and historical comparisons.

    Storage: ~730 records per client (2 years × 365 days)
    vs ~105,120 5-min records (2 years × 365 × 12 per hour × 24 hours)
    = 99.3% storage reduction
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
        related_name='noc_metrics_1day',
        verbose_name=_("Business Unit")
    )

    date = models.DateField(db_index=True, verbose_name=_("Date"))
    computed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Computed At"))

    # Tickets - daily aggregated metrics
    tickets_open_avg = models.FloatField(default=0.0, verbose_name=_("Tickets Open (Daily Avg)"))
    tickets_open_min = models.IntegerField(default=0, verbose_name=_("Tickets Open (Daily Min)"))
    tickets_open_max = models.IntegerField(default=0, verbose_name=_("Tickets Open (Daily Max)"))

    tickets_overdue_avg = models.FloatField(default=0.0, verbose_name=_("Tickets Overdue (Daily Avg)"))
    tickets_overdue_min = models.IntegerField(default=0, verbose_name=_("Tickets Overdue (Daily Min)"))
    tickets_overdue_max = models.IntegerField(default=0, verbose_name=_("Tickets Overdue (Daily Max)"))

    # Work Orders - daily aggregated metrics
    work_orders_pending_avg = models.FloatField(default=0.0, verbose_name=_("Work Orders Pending (Daily Avg)"))
    work_orders_pending_min = models.IntegerField(default=0, verbose_name=_("Work Orders Pending (Daily Min)"))
    work_orders_pending_max = models.IntegerField(default=0, verbose_name=_("Work Orders Pending (Daily Max)"))

    work_orders_overdue_avg = models.FloatField(default=0.0, verbose_name=_("Work Orders Overdue (Daily Avg)"))
    work_orders_overdue_min = models.IntegerField(default=0, verbose_name=_("Work Orders Overdue (Daily Min)"))
    work_orders_overdue_max = models.IntegerField(default=0, verbose_name=_("Work Orders Overdue (Daily Max)"))

    # Attendance - daily aggregated metrics
    attendance_present_avg = models.FloatField(default=0.0, verbose_name=_("Present (Daily Avg)"))
    attendance_present_min = models.IntegerField(default=0, verbose_name=_("Present (Daily Min)"))
    attendance_present_max = models.IntegerField(default=0, verbose_name=_("Present (Daily Max)"))

    attendance_missing_avg = models.FloatField(default=0.0, verbose_name=_("Missing (Daily Avg)"))
    attendance_missing_min = models.IntegerField(default=0, verbose_name=_("Missing (Daily Min)"))
    attendance_missing_max = models.IntegerField(default=0, verbose_name=_("Missing (Daily Max)"))

    # Device Health - daily aggregated metrics
    device_health_offline_avg = models.FloatField(default=0.0, verbose_name=_("Offline Devices (Daily Avg)"))
    device_health_offline_min = models.IntegerField(default=0, verbose_name=_("Offline Devices (Daily Min)"))
    device_health_offline_max = models.IntegerField(default=0, verbose_name=_("Offline Devices (Daily Max)"))

    sync_health_score_avg = models.FloatField(default=100.0, verbose_name=_("Sync Health Score (Daily Avg)"))
    sync_health_score_min = models.FloatField(default=100.0, verbose_name=_("Sync Health Score (Daily Min)"))

    # Security - daily aggregated metrics
    security_anomalies_avg = models.FloatField(default=0.0, verbose_name=_("Anomalies (Daily Avg)"))
    security_anomalies_max = models.IntegerField(default=0, verbose_name=_("Anomalies (Daily Max)"))
    security_anomalies_sum = models.IntegerField(default=0, verbose_name=_("Anomalies (Daily Sum)"))

    class Meta:
        db_table = 'noc_metric_snapshot_1day'
        verbose_name = _("NOC Metric Snapshot (1 Day)")
        verbose_name_plural = _("NOC Metric Snapshots (1 Day)")
        indexes = [
            models.Index(fields=['tenant', 'client', 'date'], name='noc_1d_tenant_client'),
            models.Index(fields=['tenant', 'date'], name='noc_1d_tenant_date'),
            models.Index(fields=['computed_at'], name='noc_1d_computed'),
        ]
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'client', 'date'],
                name='unique_daily_snapshot_per_client'
            )
        ]

    def __str__(self) -> str:
        return f"Daily Metrics: {self.client.buname} @ {self.date}"
