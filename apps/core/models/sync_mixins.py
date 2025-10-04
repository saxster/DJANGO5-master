"""
Syncable Model Mixins - Standardized sync fields for mobile offline sync

Eliminates duplicate mobile sync field patterns found in migrations:
- apps/activity/migrations/0012_add_mobile_sync_fields.py
- apps/y_helpdesk/migrations/0011_add_mobile_sync_fields.py
- apps/attendance/migrations/0011_add_mobile_sync_fields.py
- apps/work_order_management/migrations/0003_add_mobile_sync_fields.py

Following .claude/rules.md:
- Rule #7: Model mixin <150 lines
- Rule #12: Database indexes for performance
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class SyncableModelMixin(models.Model):
    """
    Abstract mixin providing standardized mobile sync fields.

    Adds consistent sync infrastructure to any model:
    - mobile_id: Unique identifier from mobile client
    - last_sync_timestamp: Last successful sync time
    - sync_status: Current sync state
    - version: Optimistic locking version number

    Usage:
        class YourModel(SyncableModelMixin, models.Model):
            # Your model fields here
            pass
    """

    SYNC_STATUS_CHOICES = [
        ('synced', 'Synced'),
        ('pending_sync', 'Pending Sync'),
        ('sync_error', 'Sync Error'),
        ('pending_delete', 'Pending Delete'),
        ('conflict', 'Conflict Detected'),
    ]

    mobile_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Unique identifier from mobile client for sync tracking'
    )

    last_sync_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last successful sync timestamp from mobile client'
    )

    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default='synced',
        help_text='Current sync status for mobile client'
    )

    version = models.PositiveIntegerField(
        default=1,
        help_text='Version number for optimistic locking'
    )

    class Meta:
        abstract = True
        indexes = [
            # Composite index for efficient sync queries
            models.Index(fields=['mobile_id', 'version'], name='%(app_label)s_%(class)s_sync_idx'),
            # Index for querying pending syncs
            models.Index(fields=['sync_status', 'last_sync_timestamp'], name='%(app_label)s_%(class)s_status_idx'),
        ]

    def save(self, *args, **kwargs):
        """Override save to handle sync field defaults."""
        # Generate mobile_id if not set
        if not self.mobile_id:
            self.mobile_id = uuid.uuid4()

        # Update sync timestamp on save
        if self.sync_status == 'synced':
            self.last_sync_timestamp = timezone.now()

        super().save(*args, **kwargs)

    def mark_for_sync(self, status: str = 'pending_sync') -> None:
        """
        Mark object for sync with mobile clients.

        Args:
            status: Sync status to set ('pending_sync', 'sync_error', etc.)
        """
        if status not in dict(self.SYNC_STATUS_CHOICES):
            raise ValidationError(f"Invalid sync status: {status}")

        self.sync_status = status
        self.save(update_fields=['sync_status'])

    def mark_synced(self) -> None:
        """Mark object as successfully synced."""
        self.sync_status = 'synced'
        self.last_sync_timestamp = timezone.now()
        self.save(update_fields=['sync_status', 'last_sync_timestamp'])

    def increment_version(self) -> None:
        """Increment version for optimistic locking."""
        self.version += 1
        self.save(update_fields=['version'])

    def get_sync_metadata(self) -> dict:
        """
        Get sync metadata for API responses.

        Returns:
            Dict with sync-related fields
        """
        return {
            'mobile_id': str(self.mobile_id) if self.mobile_id else None,
            'version': self.version,
            'sync_status': self.sync_status,
            'last_sync_timestamp': self.last_sync_timestamp.isoformat() if self.last_sync_timestamp else None,
        }

    @classmethod
    def get_pending_sync_queryset(cls):
        """
        Get queryset of objects pending sync.

        Returns:
            QuerySet of objects with pending sync status
        """
        return cls.objects.filter(
            sync_status__in=['pending_sync', 'sync_error', 'conflict']
        ).order_by('-last_sync_timestamp')

    @classmethod
    def get_changes_since(cls, timestamp, limit=100):
        """
        Get objects changed since timestamp for delta sync.

        Args:
            timestamp: ISO timestamp string
            limit: Maximum objects to return

        Returns:
            QuerySet of changed objects
        """
        queryset = cls.objects.filter(
            models.Q(updated_at__gt=timestamp) | models.Q(created_at__gt=timestamp)
        ).order_by('-updated_at')

        return queryset[:limit]


class ConflictTrackingMixin(models.Model):
    """
    Mixin for tracking sync conflicts on models.

    Adds fields to track conflict resolution state and metadata.
    """

    CONFLICT_RESOLUTION_CHOICES = [
        ('none', 'No Conflict'),
        ('client_wins', 'Client Version Wins'),
        ('server_wins', 'Server Version Wins'),
        ('manual_required', 'Manual Resolution Required'),
        ('merged', 'Merged Resolution'),
    ]

    conflict_resolution = models.CharField(
        max_length=20,
        choices=CONFLICT_RESOLUTION_CHOICES,
        default='none',
        help_text='How conflicts should be resolved for this record'
    )

    conflict_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Metadata about conflicts and resolution attempts'
    )

    conflict_detected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When conflict was first detected'
    )

    conflict_resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When conflict was resolved'
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['conflict_resolution'], name='%(app_label)s_%(class)s_conflict_idx'),
            models.Index(fields=['conflict_detected_at'], name='%(app_label)s_%(class)s_conflict_time_idx'),
        ]

    def mark_conflict(self, conflict_data: dict = None) -> None:
        """
        Mark record as having a sync conflict.

        Args:
            conflict_data: Additional conflict metadata
        """
        self.conflict_resolution = 'manual_required'
        self.conflict_detected_at = timezone.now()
        self.conflict_data = conflict_data or {}
        self.save(update_fields=['conflict_resolution', 'conflict_detected_at', 'conflict_data'])

    def resolve_conflict(self, resolution: str, resolution_data: dict = None) -> None:
        """
        Mark conflict as resolved.

        Args:
            resolution: How conflict was resolved
            resolution_data: Additional resolution metadata
        """
        if resolution not in dict(self.CONFLICT_RESOLUTION_CHOICES):
            raise ValidationError(f"Invalid conflict resolution: {resolution}")

        self.conflict_resolution = resolution
        self.conflict_resolved_at = timezone.now()

        if resolution_data:
            self.conflict_data.update(resolution_data)

        self.save(update_fields=['conflict_resolution', 'conflict_resolved_at', 'conflict_data'])

    @property
    def has_unresolved_conflict(self) -> bool:
        """Check if record has unresolved conflict."""
        return self.conflict_resolution == 'manual_required'

    @classmethod
    def get_conflicted_objects(cls):
        """Get queryset of objects with unresolved conflicts."""
        return cls.objects.filter(conflict_resolution='manual_required')


class FullSyncMixin(SyncableModelMixin, ConflictTrackingMixin):
    """
    Complete sync mixin combining syncable fields and conflict tracking.

    Use this for models that need full sync capabilities including
    conflict detection and resolution.
    """

    class Meta:
        abstract = True

    def get_full_sync_metadata(self) -> dict:
        """
        Get complete sync metadata including conflict information.

        Returns:
            Dict with all sync-related fields
        """
        metadata = self.get_sync_metadata()
        metadata.update({
            'conflict_resolution': self.conflict_resolution,
            'has_conflict': self.has_unresolved_conflict,
            'conflict_detected_at': self.conflict_detected_at.isoformat() if self.conflict_detected_at else None,
            'conflict_resolved_at': self.conflict_resolved_at.isoformat() if self.conflict_resolved_at else None,
        })
        return metadata


class SyncMetricsMixin(models.Model):
    """
    Mixin for tracking sync performance metrics on models.

    Adds fields to monitor sync efficiency and identify bottlenecks.
    """

    sync_attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of sync attempts for this record'
    )

    sync_failures = models.PositiveIntegerField(
        default=0,
        help_text='Number of failed sync attempts'
    )

    last_sync_duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Duration of last sync operation in milliseconds'
    )

    avg_sync_duration_ms = models.FloatField(
        default=0.0,
        help_text='Average sync duration across all attempts'
    )

    class Meta:
        abstract = True

    def record_sync_attempt(self, duration_ms: int, success: bool = True) -> None:
        """
        Record a sync attempt with timing and outcome.

        Args:
            duration_ms: Sync duration in milliseconds
            success: Whether sync was successful
        """
        self.sync_attempts += 1
        self.last_sync_duration_ms = duration_ms

        if not success:
            self.sync_failures += 1

        # Update rolling average
        if self.sync_attempts > 1:
            self.avg_sync_duration_ms = (
                (self.avg_sync_duration_ms * (self.sync_attempts - 1) + duration_ms) / self.sync_attempts
            )
        else:
            self.avg_sync_duration_ms = float(duration_ms)

        self.save(update_fields=[
            'sync_attempts', 'sync_failures', 'last_sync_duration_ms', 'avg_sync_duration_ms'
        ])

    @property
    def sync_success_rate(self) -> float:
        """Calculate sync success rate as percentage."""
        if self.sync_attempts == 0:
            return 100.0
        return ((self.sync_attempts - self.sync_failures) / self.sync_attempts) * 100

    @property
    def is_problematic_sync(self) -> bool:
        """Check if this record has sync problems."""
        return (
            self.sync_failures > 5 or
            self.sync_success_rate < 80.0 or
            (self.avg_sync_duration_ms > 5000)  # >5 seconds average
        )