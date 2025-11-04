"""
Mobile Sync Conflict Model

Tracks conflicts during mobile synchronization.

Features:
- Server-wins vs client-wins tracking
- Conflict resolution history
- User notification
- Analytics for conflict patterns
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
import uuid


class SyncConflict(BaseModel, TenantAwareModel):
    """
    Record of a synchronization conflict.

    Created when mobile client data conflicts with server data.
    """

    class ConflictType(models.TextChoices):
        CONCURRENT_UPDATE = 'CONCURRENT_UPDATE', 'Concurrent Update'
        VERSION_MISMATCH = 'VERSION_MISMATCH', 'Version Mismatch'
        DATA_CORRUPTION = 'DATA_CORRUPTION', 'Data Corruption'
        TIMESTAMP_CONFLICT = 'TIMESTAMP_CONFLICT', 'Timestamp Conflict'

    class Resolution(models.TextChoices):
        SERVER_WINS = 'SERVER_WINS', 'Server Wins'
        CLIENT_WINS = 'CLIENT_WINS', 'Client Wins'
        MERGED = 'MERGED', 'Merged'
        MANUAL = 'MANUAL', 'Manual Resolution'

    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        related_name='sync_conflicts'
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sync_conflicts'
    )

    conflict_type = models.CharField(max_length=50, choices=ConflictType.choices)
    detected_at = models.DateTimeField(default=timezone.now)

    client_version = models.JSONField(help_text="Client's version of the data")
    server_version = models.JSONField(help_text="Server's version of the data")

    resolution = models.CharField(max_length=20, choices=Resolution.choices)
    resolved_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_sync_conflicts'
    )

    # Notification
    user_notified = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    # Device info
    device_id = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = 'sync_conflict'
        verbose_name = 'Sync Conflict'
        verbose_name_plural = 'Sync Conflicts'
        indexes = [
            models.Index(fields=['tenant', 'employee'], name='sc_tenant_emp_idx'),
            models.Index(fields=['detected_at'], name='sc_detected_idx'),
            models.Index(fields=['user_notified'], name='sc_notified_idx'),
        ]

    def __str__(self):
        return f"Conflict: {self.employee.username} - {self.conflict_type}"
