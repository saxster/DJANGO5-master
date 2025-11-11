"""
Sync Tracking Models for ML Conflict Prediction

Tracks all sync operations from mobile/web clients to enable:
- ML-based conflict prediction
- Concurrent edit detection
- Sync pattern analysis
- Conflict resolution tracking

Architecture:
- SyncLog: Records every sync operation (create/update/delete)
- ConflictResolution: Tracks detected conflicts and their resolutions

Created: November 2025 (Ultrathink Phase 4 - ML Conflict Prediction)
"""

from django.db import models
from django.utils import timezone
from apps.tenants.models import TenantAwareModel


class SyncLog(TenantAwareModel):
    """
    Records all sync operations for conflict prediction.

    Each sync operation from mobile/web clients creates a SyncLog entry
    capturing what changed, when, and by whom.

    Purpose:
    - ML training data for conflict prediction
    - Audit trail for sync operations
    - Conflict detection input

    Retention: 30 days (configurable)
    """

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='sync_logs',
        help_text="User who performed the sync operation"
    )

    entity_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Entity type (e.g., 'Task', 'WorkOrder', 'Asset')"
    )

    entity_id = models.IntegerField(
        db_index=True,
        help_text="ID of the synced entity"
    )

    operation = models.CharField(
        max_length=20,
        choices=[
            ('create', 'Create'),
            ('update', 'Update'),
            ('delete', 'Delete'),
        ],
        db_index=True,
        help_text="Type of operation"
    )

    field_changes = models.JSONField(
        default=dict,
        help_text="""
        Changed fields with old/new values.
        Format: {"field_name": {"old": value, "new": value}}
        Example: {"title": {"old": "Old Title", "new": "New Title"}}
        """
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the sync operation occurred"
    )

    device_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Device identifier (for mobile clients)"
    )

    sync_session_id = models.UUIDField(
        db_index=True,
        help_text="Session ID grouping related sync operations"
    )

    app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Client app version (e.g., '2.1.0')"
    )

    network_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('wifi', 'WiFi'),
            ('cellular', 'Cellular'),
            ('unknown', 'Unknown'),
        ],
        help_text="Network type during sync"
    )

    class Meta:
        db_table = 'core_sync_log'
        ordering = ['-timestamp']
        indexes = [
            # Query by entity for conflict detection
            models.Index(fields=['entity_type', 'entity_id', 'timestamp'], name='synclog_entity_time'),
            # Query by user for analytics
            models.Index(fields=['user', 'timestamp'], name='synclog_user_time'),
            # Query by session for batch operations
            models.Index(fields=['sync_session_id'], name='synclog_session'),
        ]

    def __str__(self):
        return f"{self.user.username} {self.operation} {self.entity_type}:{self.entity_id} at {self.timestamp}"

    @property
    def changed_field_count(self) -> int:
        """Number of fields changed in this operation."""
        return len(self.field_changes)

    @property
    def time_since_sync(self):
        """Time elapsed since this sync operation."""
        return timezone.now() - self.timestamp

    def get_concurrent_edits(self, time_window_seconds: int = 300):
        """
        Find other edits to same entity within time window.

        Args:
            time_window_seconds: Time window for concurrency check (default 5 minutes)

        Returns:
            QuerySet of SyncLog entries
        """
        from datetime import timedelta

        window_start = self.timestamp - timedelta(seconds=time_window_seconds)
        window_end = self.timestamp + timedelta(seconds=time_window_seconds)

        return SyncLog.objects.filter(
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            timestamp__gte=window_start,
            timestamp__lte=window_end
        ).exclude(pk=self.pk)


class ConflictResolution(TenantAwareModel):
    """
    Records detected conflicts and their resolutions.

    Tracks conflicts arising from concurrent edits and how they
    were resolved (automatically or manually).

    Purpose:
    - ML training labels for conflict prediction
    - Conflict resolution analytics
    - Audit trail for manual interventions
    """

    sync_logs = models.ManyToManyField(
        SyncLog,
        related_name='conflicts',
        help_text="Sync operations involved in this conflict"
    )

    conflict_type = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('concurrent_edit', 'Concurrent Edit'),
            ('stale_update', 'Stale Update'),
            ('field_collision', 'Field Collision'),
            ('delete_conflict', 'Delete Conflict'),
        ],
        help_text="Type of conflict detected"
    )

    detected_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When conflict was detected"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When conflict was resolved (null if unresolved)"
    )

    resolution_strategy = models.CharField(
        max_length=50,
        choices=[
            ('last_write_wins', 'Last Write Wins'),
            ('manual_merge', 'Manual Merge'),
            ('auto_merge', 'Auto Merge'),
            ('first_write_wins', 'First Write Wins'),
            ('unresolved', 'Unresolved'),
        ],
        default='unresolved',
        help_text="Strategy used to resolve conflict"
    )

    resolution_data = models.JSONField(
        default=dict,
        help_text="""
        Resolution details including:
        - merged_fields: Fields that were merged
        - discarded_changes: Changes that were discarded
        - manual_intervention: User who resolved manually
        """
    )

    severity = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium',
        help_text="Conflict severity based on data importance"
    )

    notified_users = models.ManyToManyField(
        'peoples.People',
        related_name='conflict_notifications',
        blank=True,
        help_text="Users notified about this conflict"
    )

    class Meta:
        db_table = 'core_conflict_resolution'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['conflict_type', 'detected_at'], name='conflict_type_time'),
            models.Index(fields=['resolution_strategy'], name='conflict_strategy'),
        ]

    def __str__(self):
        status = "resolved" if self.resolved_at else "unresolved"
        return f"{self.conflict_type} conflict ({status}) - {self.detected_at}"

    @property
    def is_resolved(self) -> bool:
        """Whether conflict has been resolved."""
        return self.resolved_at is not None

    @property
    def resolution_time_seconds(self):
        """
        Time taken to resolve conflict in seconds.

        Returns None if unresolved.
        """
        if not self.resolved_at:
            return None
        return (self.resolved_at - self.detected_at).total_seconds()

    @property
    def user_count(self) -> int:
        """Number of users involved in conflict."""
        sync_logs_list = self.sync_logs.all()
        if not sync_logs_list:
            return 0
        return len(set(log.user_id for log in sync_logs_list))

    def mark_resolved(self, strategy: str, resolution_data: dict = None):
        """
        Mark conflict as resolved.

        Args:
            strategy: Resolution strategy used
            resolution_data: Additional resolution details
        """
        self.resolved_at = timezone.now()
        self.resolution_strategy = strategy
        if resolution_data:
            self.resolution_data = resolution_data
        self.save()

    def get_conflicting_fields(self) -> set:
        """
        Get set of fields that had conflicts.

        Returns:
            Set of field names
        """
        fields = set()
        for sync_log in self.sync_logs.all():
            fields.update(sync_log.field_changes.keys())
        return fields
