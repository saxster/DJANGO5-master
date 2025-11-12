"""
Camera Fingerprinting Model

Device fingerprinting for camera identification and fraud tracking.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import logging
from django.db import models
from django.db.models import JSONField
from django.utils import timezone
from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)

class CameraFingerprint(TenantAwareModel):
    """
    Device fingerprinting for camera identification and fraud tracking.

    Tracks unique camera signatures to identify repeat offenders and
    suspicious device usage patterns.
    """

    class TrustLevel(models.TextChoices):
        TRUSTED = 'trusted', 'Trusted Device'
        NEUTRAL = 'neutral', 'Neutral Device'
        SUSPICIOUS = 'suspicious', 'Suspicious Device'
        BLOCKED = 'blocked', 'Blocked Device'

    # Camera identification
    fingerprint_hash = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Unique hash identifying the camera device"
    )
    camera_make = models.CharField(max_length=100, db_index=True)
    camera_model = models.CharField(max_length=100, db_index=True)

    # Usage tracking
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)
    usage_count = models.PositiveIntegerField(default=1)

    # Associated users
    associated_users = models.ManyToManyField(
        'peoples.People',
        related_name='camera_devices',
        help_text="Users who have used this camera"
    )

    # Trust and security
    trust_level = models.CharField(
        max_length=20,
        choices=TrustLevel.choices,
        default=TrustLevel.NEUTRAL,
        db_index=True
    )
    fraud_incidents = models.PositiveIntegerField(
        default=0,
        help_text="Number of fraud incidents associated with this device"
    )

    # Metadata
    device_characteristics = JSONField(
        default=dict,
        help_text="Technical characteristics and patterns"
    )
    security_notes = models.TextField(
        blank=True,
        help_text="Security notes and incident history"
    )

    class Meta:
        db_table = 'core_camera_fingerprint'
        verbose_name = 'Camera Fingerprint'
        verbose_name_plural = 'Camera Fingerprints'
        indexes = [
            models.Index(fields=['trust_level', 'last_seen'], name='idx_camera_trust_activity'),
            models.Index(fields=['fraud_incidents'], name='idx_camera_fraud_count'),
        ]
        ordering = ['-last_seen']

    def __str__(self):
        return f"Camera {self.camera_make} {self.camera_model} - {self.trust_level}"

    @property
    def is_high_risk(self):
        """Check if camera is considered high risk."""
        return (
            self.trust_level in ['suspicious', 'blocked'] or
            self.fraud_incidents > 2
        )

    def update_usage(self, people_instance):
        """Update usage statistics and user associations."""
        self.usage_count += 1
        self.last_seen = timezone.now()
        self.save(update_fields=['usage_count', 'last_seen'])

        if people_instance:
            self.associated_users.add(people_instance)
