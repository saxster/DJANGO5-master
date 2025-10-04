"""
Device Registry Models

Tracks user devices and sync state for cross-device coordination.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
"""

from django.db import models
from django.utils import timezone


class UserDevice(models.Model):
    """
    Registry of user devices for cross-device sync.

    Tracks all devices belonging to a user and their priority for conflict resolution.
    """

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='devices'
    )

    device_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique device identifier"
    )

    device_type = models.CharField(
        max_length=20,
        choices=[
            ('phone', 'Mobile Phone'),
            ('tablet', 'Tablet'),
            ('laptop', 'Laptop'),
            ('desktop', 'Desktop'),
        ],
        help_text="Device type"
    )

    priority = models.IntegerField(
        default=50,
        help_text="Conflict resolution priority (higher = more authoritative)"
    )

    device_name = models.CharField(max_length=255, blank=True)
    os_type = models.CharField(max_length=50, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    app_version = models.CharField(max_length=50, blank=True)

    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_device'
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_type']),
        ]
        verbose_name = 'User Device'
        verbose_name_plural = 'User Devices'

    def __str__(self):
        return f"{self.device_id} ({self.device_type}) - {self.user.loginid}"


class DeviceSyncState(models.Model):
    """
    Per-device sync state for entities.

    Tracks which device has the latest version of each entity.
    """

    device = models.ForeignKey(
        UserDevice,
        on_delete=models.CASCADE,
        related_name='sync_states'
    )

    domain = models.CharField(
        max_length=50,
        help_text="Data domain"
    )

    entity_id = models.UUIDField(
        help_text="Entity identifier"
    )

    last_sync_version = models.IntegerField(
        default=0,
        help_text="Version number at last sync"
    )

    last_modified_at = models.DateTimeField(
        help_text="Last modification timestamp"
    )

    is_dirty = models.BooleanField(
        default=False,
        help_text="Has unsynced changes"
    )

    checksum = models.CharField(
        max_length=64,
        blank=True,
        help_text="Data checksum for integrity"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_sync_state'
        unique_together = [('device', 'domain', 'entity_id')]
        ordering = ['-last_modified_at']
        indexes = [
            models.Index(fields=['device', 'domain']),
            models.Index(fields=['domain', 'entity_id']),
            models.Index(fields=['is_dirty']),
        ]
        verbose_name = 'Device Sync State'
        verbose_name_plural = 'Device Sync States'

    def __str__(self):
        status = 'dirty' if self.is_dirty else 'clean'
        return f"{self.device.device_id} - {self.domain}/{self.entity_id} ({status})"