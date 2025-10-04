"""
Journal Sync Data Models

Extracted from the main JournalEntry model to follow Single Responsibility Principle.
Handles all mobile sync, versioning, and conflict resolution data.
"""

from django.db import models
from django.utils import timezone
import uuid


class JournalSyncStatus(models.TextChoices):
    """Sync status options for offline mobile client support"""
    DRAFT = 'draft', 'Draft'
    PENDING_SYNC = 'pending_sync', 'Pending Sync'
    SYNCED = 'synced', 'Synced'
    SYNC_ERROR = 'sync_error', 'Sync Error'
    PENDING_DELETE = 'pending_delete', 'Pending Delete'


class JournalSyncData(models.Model):
    """
    Sync and versioning data for mobile client support

    Extracted from JournalEntry to reduce model complexity and follow SRP.
    Contains all mobile sync, conflict resolution, and versioning information.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Mobile sync management
    sync_status = models.CharField(
        max_length=20,
        choices=JournalSyncStatus.choices,
        default=JournalSyncStatus.SYNCED,
        help_text="Current sync status with mobile clients"
    )
    mobile_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Client-generated ID for sync conflict resolution"
    )

    # Version control for conflict resolution
    version = models.IntegerField(
        default=1,
        help_text="Version number for conflict resolution"
    )
    last_sync_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful sync with mobile client"
    )

    # Entry state management
    is_draft = models.BooleanField(
        default=False,
        help_text="Whether entry is still a draft"
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )
    is_bookmarked = models.BooleanField(
        default=False,
        help_text="Whether entry is bookmarked by user"
    )

    # Sync metadata
    sync_metadata = models.JSONField(
        default=dict,
        help_text="Additional sync-related metadata"
    )

    # Client tracking
    client_device_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Device identifier from mobile client"
    )
    client_app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mobile app version that created/updated this entry"
    )

    # Conflict resolution
    has_conflicts = models.BooleanField(
        default=False,
        help_text="Whether this entry has unresolved sync conflicts"
    )
    conflict_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Data from conflicting versions for manual resolution"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journal Sync Data"
        verbose_name_plural = "Journal Sync Data"

        indexes = [
            models.Index(fields=['sync_status']),
            models.Index(fields=['mobile_id']),
            models.Index(fields=['version']),
            models.Index(fields=['last_sync_timestamp']),
            models.Index(fields=['is_draft']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['has_conflicts']),
            models.Index(fields=['client_device_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        status_parts = [self.get_sync_status_display()]

        if self.is_draft:
            status_parts.append("Draft")

        if self.is_deleted:
            status_parts.append("Deleted")

        if self.has_conflicts:
            status_parts.append("Has Conflicts")

        return f"Sync Data: {', '.join(status_parts)} (v{self.version})"

    @property
    def needs_sync(self):
        """Check if entry needs to be synced"""
        return self.sync_status in [
            JournalSyncStatus.PENDING_SYNC,
            JournalSyncStatus.SYNC_ERROR
        ]

    @property
    def is_synced(self):
        """Check if entry is fully synced"""
        return self.sync_status == JournalSyncStatus.SYNCED

    @property
    def sync_age_hours(self):
        """Get hours since last sync"""
        if not self.last_sync_timestamp:
            return None

        delta = timezone.now() - self.last_sync_timestamp
        return delta.total_seconds() / 3600

    def increment_version(self):
        """Increment version for conflict resolution"""
        self.version += 1
        self.updated_at = timezone.now()

    def mark_for_sync(self):
        """Mark entry as needing sync"""
        if self.sync_status == JournalSyncStatus.SYNCED:
            self.sync_status = JournalSyncStatus.PENDING_SYNC

    def mark_synced(self):
        """Mark entry as successfully synced"""
        self.sync_status = JournalSyncStatus.SYNCED
        self.last_sync_timestamp = timezone.now()
        self.has_conflicts = False
        self.conflict_data = None

    def mark_sync_error(self, error_details=None):
        """Mark entry as having sync error"""
        self.sync_status = JournalSyncStatus.SYNC_ERROR
        if error_details:
            if not self.sync_metadata:
                self.sync_metadata = {}
            self.sync_metadata['last_error'] = error_details
            self.sync_metadata['error_timestamp'] = timezone.now().isoformat()

    def mark_for_deletion(self):
        """Mark entry for deletion (soft delete)"""
        self.is_deleted = True
        self.sync_status = JournalSyncStatus.PENDING_DELETE

    def create_conflict(self, conflicting_data):
        """Create conflict record for manual resolution"""
        self.has_conflicts = True
        self.conflict_data = {
            'server_version': self.version,
            'client_data': conflicting_data,
            'conflict_timestamp': timezone.now().isoformat(),
            'conflict_type': 'version_mismatch'
        }

    def resolve_conflict(self, resolution_type='server_wins'):
        """Resolve sync conflict"""
        if not self.has_conflicts:
            return

        if resolution_type == 'server_wins':
            # Keep server version, ignore client changes
            self.has_conflicts = False
            self.conflict_data = None
        elif resolution_type == 'client_wins':
            # This would typically involve updating the entry with client data
            # Implementation depends on specific conflict resolution strategy
            self.increment_version()
            self.has_conflicts = False
            self.conflict_data = None
        elif resolution_type == 'manual':
            # Keep conflict for manual resolution
            pass

        if not self.has_conflicts:
            self.mark_synced()

    def get_sync_summary(self):
        """Get summary of sync status"""
        summary = {
            'status': self.get_sync_status_display(),
            'version': self.version,
            'needs_sync': self.needs_sync,
            'has_conflicts': self.has_conflicts,
            'last_sync': self.last_sync_timestamp.isoformat() if self.last_sync_timestamp else None
        }

        if self.sync_age_hours:
            summary['sync_age_hours'] = round(self.sync_age_hours, 1)

        if self.client_device_id:
            summary['client_device'] = self.client_device_id

        if self.client_app_version:
            summary['app_version'] = self.client_app_version

        return summary