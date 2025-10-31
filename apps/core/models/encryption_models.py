"""
Encryption key management models.

This module contains models for encryption key lifecycle and rotation management:
- EncryptionKeyMetadata: Track encryption key lifecycle for key rotation

Migration Date: 2025-10-10
Migrated from: apps/core/models.py (lines 412-626)
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class EncryptionKeyMetadata(models.Model):
    """
    Track encryption key lifecycle for key rotation management.

    This model addresses the CVSS 7.5 vulnerability where no key rotation
    mechanism existed. It enables:
    - Multi-key support for safe rotation
    - Key age tracking and expiration
    - Audit trail of all key operations
    - Rollback capability during rotation failures
    """

    # Key identification
    key_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the encryption key"
    )

    # Key lifecycle status
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this key is currently active for encryption/decryption"
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the key was created"
    )

    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key was activated for use"
    )

    expires_at = models.DateTimeField(
        help_text="When the key should expire and be rotated"
    )

    rotated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key was rotated out"
    )

    # Rotation tracking
    rotation_status = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Created - Not Yet Active'),
            ('active', 'Active - Current Key'),
            ('rotating', 'Rotating - Migration In Progress'),
            ('retired', 'Retired - No Longer Used'),
            ('expired', 'Expired - Past Expiration Date'),
        ],
        default='created',
        db_index=True,
        help_text="Current status of the key in rotation lifecycle"
    )

    replaced_by_key_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Key ID that replaced this key during rotation"
    )

    # Audit trail
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_encryption_keys',
        help_text="User who created this key"
    )

    rotation_notes = models.TextField(
        blank=True,
        help_text="Notes about key rotation process"
    )

    # Metadata
    data_encrypted_count = models.BigIntegerField(
        default=0,
        help_text="Approximate count of records encrypted with this key"
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this key was used for encryption/decryption"
    )

    class Meta:
        db_table = 'encryption_key_metadata'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_id']),
            models.Index(fields=['is_active', 'expires_at']),
            models.Index(fields=['rotation_status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Encryption Key Metadata'
        verbose_name_plural = 'Encryption Key Metadata'

    def __str__(self):
        status_indicator = "✅" if self.is_active else "⏸️"
        return f"{status_indicator} {self.key_id} ({self.rotation_status})"

    def save(self, *args, **kwargs):
        """Override save to update timestamps and audit trail."""
        # Update activated_at when becoming active
        if self.is_active and not self.activated_at:
            self.activated_at = timezone.now()

        # Update rotated_at when status changes to retired
        if self.rotation_status == 'retired' and not self.rotated_at:
            self.rotated_at = timezone.now()

        # Check for expiration
        if timezone.now() > self.expires_at and self.rotation_status not in ['retired', 'expired']:
            self.rotation_status = 'expired'
            self.is_active = False

        super().save(*args, **kwargs)

    @property
    def age_days(self):
        """Calculate key age in days."""
        return (timezone.now() - self.created_at).days

    @property
    def expires_in_days(self):
        """Calculate days until expiration."""
        return (self.expires_at - timezone.now()).days

    @property
    def is_expired(self):
        """Check if key has expired."""
        return timezone.now() > self.expires_at

    @property
    def needs_rotation(self):
        """Check if key needs rotation (within 14 days of expiration)."""
        return self.expires_in_days < 14

    def mark_for_rotation(self, new_key_id: str, notes: str = "") -> None:
        """
        Mark this key for rotation.

        Args:
            new_key_id: ID of the new key that will replace this one
            notes: Notes about the rotation process
        """
        self.rotation_status = 'rotating'
        self.replaced_by_key_id = new_key_id
        if notes:
            self.rotation_notes = f"{self.rotation_notes}\n{timezone.now()}: {notes}"
        self.save()

    def retire(self, notes: str = "") -> None:
        """
        Retire this key after successful rotation.

        Args:
            notes: Notes about retirement
        """
        self.is_active = False
        self.rotation_status = 'retired'
        self.rotated_at = timezone.now()
        if notes:
            self.rotation_notes = f"{self.rotation_notes}\n{timezone.now()}: {notes}"
        self.save()

    @classmethod
    def get_current_key(cls):
        """Get the current active encryption key."""
        return cls.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

    @classmethod
    def get_keys_needing_rotation(cls):
        """Get keys that need rotation (expiring within 14 days)."""
        from datetime import timedelta
        rotation_threshold = timezone.now() + timedelta(days=14)

        return cls.objects.filter(
            is_active=True,
            expires_at__lt=rotation_threshold
        )

    @classmethod
    def cleanup_old_keys(cls, days=365):
        """
        Clean up retired keys older than specified days.

        Args:
            days: Number of days to keep retired keys

        Returns:
            int: Number of deleted records
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(
            rotation_status='retired',
            rotated_at__lt=cutoff
        ).delete()

        return deleted
