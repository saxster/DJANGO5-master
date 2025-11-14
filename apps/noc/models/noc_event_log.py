"""
NOC Event Log Model.

Audit trail for all WebSocket events broadcast via NOC real-time system.
Enables forensic analysis and debugging of real-time notifications.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

import uuid
from django.db import models
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class NOCEventLog(BaseModel, TenantAwareModel):
    """
    Audit log for all NOC WebSocket broadcast events.

    Records every event sent via the real-time notification system
    for compliance, debugging, and performance monitoring.
    """

    EVENT_TYPE_CHOICES = [
        ('alert_created', 'Alert Created'),
        ('alert_updated', 'Alert Updated'),
        ('finding_created', 'Finding Created'),
        ('anomaly_detected', 'Anomaly Detected'),
        ('ticket_updated', 'Ticket Updated'),
        ('incident_updated', 'Incident Updated'),
        ('correlation_identified', 'Correlation Identified'),
        ('maintenance_window', 'Maintenance Window'),
        ('metrics_refresh', 'Metrics Refresh'),
    ]

    event_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique event identifier"
    )

    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of event broadcast"
    )

    payload = models.JSONField(
        default=dict,
        help_text="Event payload data sent to clients"
    )

    broadcast_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When event was broadcast"
    )

    recipient_count = models.IntegerField(
        default=0,
        help_text="Number of WebSocket clients that received event"
    )

    # Optional foreign key links for easier querying
    alert_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Related alert ID (if event_type is alert_*)"
    )

    finding_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Related finding ID (if event_type is finding_*)"
    )

    ticket_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Related ticket ID (if event_type is ticket_*)"
    )

    # Broadcast success tracking
    broadcast_success = models.BooleanField(
        default=True,
        help_text="Whether broadcast succeeded"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if broadcast failed"
    )

    # Performance tracking
    broadcast_latency_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Broadcast latency in milliseconds"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_event_log'
        verbose_name = 'NOC Event Log'
        verbose_name_plural = 'NOC Event Logs'
        ordering = ['-broadcast_at']
        indexes = [
            models.Index(fields=['tenant', '-broadcast_at']),
            models.Index(fields=['event_type', '-broadcast_at']),
            models.Index(fields=['broadcast_at', 'event_type']),
            models.Index(fields=['alert_id', '-broadcast_at']),
            models.Index(fields=['finding_id', '-broadcast_at']),
            models.Index(fields=['ticket_id', '-broadcast_at']),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.broadcast_at.strftime('%Y-%m-%d %H:%M:%S')}"

    @classmethod
    def get_recent_events(cls, tenant, event_type=None, hours=24):
        """
        Get recent events for monitoring.

        Args:
            tenant: Tenant instance
            event_type: Optional filter by event type
            hours: How many hours back to query

        Returns:
            QuerySet of recent events
        """
        from datetime import timedelta
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(hours=hours)

        query = cls.objects.filter(
            tenant=tenant,
            broadcast_at__gte=cutoff
        )

        if event_type:
            query = query.filter(event_type=event_type)

        return query.order_by('-broadcast_at')

    @classmethod
    def get_broadcast_stats(cls, tenant, hours=24):
        """
        Get broadcast statistics for monitoring.

        Args:
            tenant: Tenant instance
            hours: Time window in hours

        Returns:
            dict: Broadcast statistics
        """
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count, Avg, Sum

        cutoff = timezone.now() - timedelta(hours=hours)

        events = cls.objects.filter(
            tenant=tenant,
            broadcast_at__gte=cutoff
        )

        stats = events.aggregate(
            total_events=Count('event_id'),
            total_recipients=Sum('recipient_count'),
            avg_latency_ms=Avg('broadcast_latency_ms'),
            failed_broadcasts=Count('event_id', filter=models.Q(broadcast_success=False))
        )

        # Events by type
        by_type = events.values('event_type').annotate(
            count=Count('event_id')
        ).order_by('-count')

        stats['by_type'] = list(by_type)
        stats['hours'] = hours

        return stats
