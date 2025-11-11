"""
WebSocket Connection Tracking Model.

Tracks active WebSocket connections for accurate broadcast metrics in NOC system.
Resolves hardcoded recipient_count=1 issue in NOCEventLog (Ultrathink remediation).

@ontology(
    domain="noc",
    purpose="Track active WebSocket connections for accurate broadcast recipient counting",
    criticality="medium",
    data_quality_impact="high - enables accurate monitoring metrics",
    tags=["websocket", "metrics", "monitoring", "connection-tracking"]
)
"""

from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel, TenantAwareModel

User = get_user_model()

__all__ = ['WebSocketConnection']


class WebSocketConnection(BaseModel, TenantAwareModel):
    """
    Tracks active WebSocket connections for broadcast recipient counting.

    Each WebSocket consumer registers a connection on connect() and unregisters on disconnect().
    The NOC broadcast service queries this model to count actual recipients instead of hardcoding 1.

    Usage:
        # In consumer.connect():
        WebSocketConnection.objects.create(
            tenant=self.tenant,
            user=self.user,
            channel_name=self.channel_name,
            group_name=f'noc_tenant_{tenant_id}',
            consumer_type='noc_dashboard'
        )

        # In websocket_service.broadcast_event():
        recipient_count = WebSocketConnection.objects.filter(
            group_name=f'noc_tenant_{tenant_id}'
        ).count()
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='websocket_connections',
        help_text="User who owns this WebSocket connection"
    )

    channel_name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique channel name from Django Channels (e.g., 'specific.ABC123')"
    )

    group_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Group name the connection is subscribed to (e.g., 'noc_tenant_5', 'noc_client_123')"
    )

    consumer_type = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('noc_dashboard', 'NOC Dashboard'),
            ('threat_alerts', 'Threat Alerts'),
            ('streaming_anomaly', 'Streaming Anomaly'),
            ('presence_monitor', 'Presence Monitor'),
        ],
        help_text="Type of WebSocket consumer (for filtering/analytics)"
    )

    connected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when connection was established"
    )

    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last activity (updated on heartbeat/message)"
    )

    class Meta:
        verbose_name = "WebSocket Connection"
        verbose_name_plural = "WebSocket Connections"
        indexes = [
            # Primary query: Count recipients by group
            models.Index(fields=['group_name', 'tenant']),
            # Analytics: Connections by tenant
            models.Index(fields=['tenant', '-connected_at']),
            # Monitoring: Active connections by consumer type
            models.Index(fields=['consumer_type', 'tenant']),
        ]
        constraints = [
            # Ensure channel_name is globally unique (enforced by unique=True)
            models.UniqueConstraint(fields=['channel_name'], name='unique_channel_name'),
        ]
        ordering = ['-connected_at']

    def __str__(self):
        return f"{self.user.username} @ {self.group_name} ({self.consumer_type})"

    @classmethod
    def get_group_member_count(cls, group_name: str, tenant_id: int = None) -> int:
        """
        Count active connections in a group.

        Args:
            group_name: Group name (e.g., 'noc_tenant_5')
            tenant_id: Optional tenant filter for additional safety

        Returns:
            Number of active connections in the group
        """
        queryset = cls.objects.filter(group_name=group_name)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.count()

    @classmethod
    def get_active_connections_by_type(cls, consumer_type: str, tenant_id: int = None):
        """
        Get all active connections for a consumer type.

        Args:
            consumer_type: Type of consumer ('noc_dashboard', 'threat_alerts', etc.)
            tenant_id: Optional tenant filter

        Returns:
            QuerySet of WebSocketConnection objects
        """
        queryset = cls.objects.filter(consumer_type=consumer_type)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.select_related('user', 'tenant')

    @classmethod
    def cleanup_stale_connections(cls, hours: int = 24):
        """
        Remove connections older than specified hours (cleanup task).

        WebSocket disconnects should normally call delete(), but this handles cases
        where disconnect() wasn't called (crashes, network issues, etc.).

        Args:
            hours: Age threshold in hours

        Returns:
            Number of connections deleted
        """
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=hours)
        stale_connections = cls.objects.filter(last_activity__lt=cutoff)
        count = stale_connections.count()
        stale_connections.delete()
        return count
