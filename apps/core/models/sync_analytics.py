"""
Sync Analytics Models for Mobile Offline Sync Monitoring

Tracks comprehensive metrics for sync performance, conflicts, and efficiency.

Following .claude/rules.md:
- Rule #7: Model <150 lines
"""

from django.db import models
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Max, F

from apps.tenants.models import Tenant


class SyncAnalyticsSnapshot(models.Model):
    """
    Time-series snapshot of sync analytics metrics.

    Captures comprehensive sync health metrics at regular intervals
    for trend analysis and performance monitoring.
    """

    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this snapshot was created"
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sync_snapshots',
        help_text="Tenant for multi-tenant filtering"
    )

    total_sync_requests = models.IntegerField(
        default=0,
        help_text="Total sync API calls during period"
    )
    successful_syncs = models.IntegerField(
        default=0,
        help_text="Successfully completed syncs"
    )
    failed_syncs = models.IntegerField(
        default=0,
        help_text="Failed sync attempts"
    )

    avg_sync_duration_ms = models.FloatField(
        default=0.0,
        help_text="Average sync duration in milliseconds"
    )
    p95_sync_duration_ms = models.FloatField(
        default=0.0,
        help_text="95th percentile sync duration"
    )
    avg_items_per_sync = models.FloatField(
        default=0.0,
        help_text="Average items synced per request"
    )

    total_conflicts = models.IntegerField(
        default=0,
        help_text="Total conflicts detected"
    )
    auto_resolved_conflicts = models.IntegerField(
        default=0,
        help_text="Conflicts resolved automatically"
    )
    manual_conflicts = models.IntegerField(
        default=0,
        help_text="Conflicts requiring manual resolution"
    )
    conflict_rate_pct = models.FloatField(
        default=0.0,
        help_text="Conflict rate as percentage"
    )

    total_bytes_synced = models.BigIntegerField(
        default=0,
        help_text="Total payload size in bytes"
    )
    bytes_saved_via_delta = models.BigIntegerField(
        default=0,
        help_text="Bytes saved through delta sync"
    )
    bandwidth_efficiency_pct = models.FloatField(
        default=0.0,
        help_text="Bandwidth efficiency percentage"
    )

    unique_devices = models.IntegerField(
        default=0,
        help_text="Unique device IDs during period"
    )
    unique_users = models.IntegerField(
        default=0,
        help_text="Unique users during period"
    )

    domain_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-domain metrics breakdown"
    )

    class Meta:
        db_table = 'sync_analytics_snapshot'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['tenant', 'timestamp']),
        ]
        verbose_name = 'Sync Analytics Snapshot'
        verbose_name_plural = 'Sync Analytics Snapshots'

    def __str__(self):
        return f"Sync Snapshot {self.timestamp} - {self.total_sync_requests} requests"

    @property
    def success_rate_pct(self) -> float:
        """Calculate success rate percentage."""
        if self.total_sync_requests == 0:
            return 0.0
        return (self.successful_syncs / self.total_sync_requests) * 100

    @classmethod
    def get_latest_for_tenant(cls, tenant_id: int):
        """Get most recent snapshot for tenant."""
        return cls.objects.filter(tenant_id=tenant_id).first()


class SyncDeviceHealth(models.Model):
    """
    Per-device sync health metrics.

    Tracks individual device sync behavior for troubleshooting
    and user-specific performance analysis.
    """

    device_id = models.CharField(
        max_length=255,
        help_text="Unique device identifier"
    )

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='device_health_records',
        help_text="User associated with device"
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='device_health_records'
    )

    last_sync_at = models.DateTimeField(
        help_text="Timestamp of last successful sync"
    )

    total_syncs = models.IntegerField(
        default=0,
        help_text="Lifetime sync count for device"
    )

    failed_syncs_count = models.IntegerField(
        default=0,
        help_text="Lifetime failed sync count"
    )

    avg_sync_duration_ms = models.FloatField(
        default=0.0,
        help_text="Average sync duration for this device"
    )

    conflicts_encountered = models.IntegerField(
        default=0,
        help_text="Total conflicts encountered by device"
    )

    health_score = models.FloatField(
        default=100.0,
        help_text="Sync health score (0-100)"
    )

    network_type = models.CharField(
        max_length=20,
        choices=[
            ('wifi', 'WiFi'),
            ('4g', '4G'),
            ('3g', '3G'),
            ('2g', '2G'),
            ('unknown', 'Unknown'),
        ],
        default='unknown',
        help_text="Last known network type"
    )

    app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mobile app version"
    )

    os_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Device OS version"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sync_device_health'
        unique_together = [('device_id', 'user')]
        ordering = ['-last_sync_at']
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['user', 'tenant']),
            models.Index(fields=['health_score']),
            models.Index(fields=['last_sync_at']),
        ]
        verbose_name = 'Device Sync Health'
        verbose_name_plural = 'Device Sync Health Records'

    def __str__(self):
        return f"{self.device_id} - Health: {self.health_score:.1f}%"

    def update_health_score(self):
        """
        Calculate health score based on sync success rate and recency.

        Factors:
        - Success rate (60% weight)
        - Sync recency (20% weight)
        - Conflict rate (20% weight)
        """
        if self.total_syncs == 0:
            self.health_score = 100.0
            return

        success_rate = ((self.total_syncs - self.failed_syncs_count) / self.total_syncs) * 60

        hours_since_sync = (timezone.now() - self.last_sync_at).total_seconds() / 3600
        recency_score = max(0, 20 - (hours_since_sync / 24) * 20)

        conflict_rate = (self.conflicts_encountered / self.total_syncs) * 20
        conflict_score = max(0, 20 - conflict_rate)

        self.health_score = success_rate + recency_score + conflict_score
        self.save(update_fields=['health_score'])