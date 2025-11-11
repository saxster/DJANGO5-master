"""
Mobile sync payload storage models.

Persist sanitized behavioral, session, and metrics data received from mobile clients
to ensure durability and auditing parity with sync responses.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantAwareModel


class BehavioralSyncEvent(TenantAwareModel):
    """Sanitized behavioral signal emitted by a mobile client."""

    user = models.ForeignKey(
        "peoples.People",
        on_delete=models.CASCADE,
        related_name="behavioral_sync_events",
    )
    device_id = models.CharField(max_length=255, db_index=True)
    client_event_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Id supplied by the client for deduplication",
    )
    event_type = models.CharField(max_length=64, help_text="Behavioral event type label")
    timestamp = models.DateTimeField(help_text="Client-side event timestamp")
    session_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    interaction_count = models.IntegerField(default=0)
    performance_score = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    schema_hash = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sync_behavioral_event"
        indexes = [
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["device_id", "timestamp"]),
            models.Index(fields=["client_event_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client_event_id"],
                name="behavioral_sync_user_client_event_uk",
            )
        ]
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.event_type}@{self.timestamp.isoformat()}"


class SessionSyncEvent(TenantAwareModel):
    """Session level telemetry emitted by mobile clients."""

    user = models.ForeignKey(
        "peoples.People",
        on_delete=models.CASCADE,
        related_name="session_sync_events",
    )
    device_id = models.CharField(max_length=255, db_index=True)
    session_id = models.CharField(max_length=255, blank=True, null=True)
    session_start = models.DateTimeField(null=True, blank=True)
    session_end = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    event_count = models.IntegerField(default=0)
    status = models.CharField(max_length=32, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    schema_hash = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sync_session_event"
        indexes = [
            models.Index(fields=["tenant", "session_start"]),
            models.Index(fields=["device_id", "session_start"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "session_id"],
                name="session_sync_user_session_id_uk",
            )
        ]
        ordering = ["-session_start", "-created_at"]

    def __str__(self) -> str:
        session_label = self.session_id or "anonymous"
        return f"{self.user_id}:{session_label}"


class DeviceMetricSnapshot(TenantAwareModel):
    """Aggregated device metrics synced from the client."""

    user = models.ForeignKey(
        "peoples.People",
        on_delete=models.CASCADE,
        related_name="device_metric_snapshots",
    )
    device_id = models.CharField(max_length=255, db_index=True)
    metric_name = models.CharField(max_length=100)
    metric_value = models.FloatField()
    unit = models.CharField(max_length=32, blank=True)
    aggregation_type = models.CharField(max_length=32, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    schema_hash = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sync_device_metric_snapshot"
        indexes = [
            models.Index(fields=["tenant", "recorded_at"]),
            models.Index(fields=["device_id", "recorded_at"]),
            models.Index(fields=["metric_name"]),
        ]
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"{self.device_id}:{self.metric_name}={self.metric_value}"
