"""
Device Trust Registry Models

Implements device fingerprinting and trust scoring for voice biometric enrollment.
Part of Sprint 1: Voice Enrollment Security implementation.

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #17: Transaction-aware operations

Created: 2025-10-11
"""

import hashlib
import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.peoples.models import People
from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class DeviceRegistration(TenantAwareModel):
    """
    Registered devices for biometric enrollment.

    Tracks device fingerprints, trust scores, and security events.
    """

    # Primary identification
    device_id = models.CharField(
        max_length=64,
        unique=True,
        primary_key=True,
        help_text="SHA256 hash of device fingerprint"
    )
    user = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='registered_devices',
        help_text="Device owner"
    )

    # Device characteristics
    device_fingerprint = models.JSONField(
        default=dict,
        help_text="Browser/device fingerprint data"
    )
    user_agent = models.TextField(
        help_text="User agent string"
    )
    ip_address = models.GenericIPAddressField(
        help_text="Last known IP address"
    )

    # Trust scoring
    trust_score = models.IntegerField(
        default=0,
        help_text="Trust score (0-100, threshold: 70 for enrollment)"
    )
    trust_factors = models.JSONField(
        default=dict,
        help_text="Breakdown of trust score components"
    )

    # Status tracking
    is_trusted = models.BooleanField(
        default=False,
        help_text="Device meets trust threshold"
    )
    is_blocked = models.BooleanField(
        default=False,
        help_text="Device blocked due to security events"
    )
    block_reason = models.TextField(
        blank=True,
        help_text="Reason for blocking"
    )

    # Activity tracking
    first_seen = models.DateTimeField(
        auto_now_add=True,
        help_text="First registration timestamp"
    )
    last_seen = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp"
    )
    last_location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last known location (city/country)"
    )

    # Biometric enrollment tracking
    biometric_enrolled = models.BooleanField(
        default=False,
        help_text="Device used for biometric enrollment"
    )
    enrollment_count = models.IntegerField(
        default=0,
        help_text="Number of enrollment attempts"
    )

    class Meta:
        db_table = 'device_registration'
        indexes = [
            models.Index(fields=['user', 'is_trusted']),
            models.Index(fields=['last_seen']),
            models.Index(fields=['is_blocked']),
        ]
        verbose_name = "Device Registration"
        verbose_name_plural = "Device Registrations"

    def __str__(self):
        return f"{self.user.peoplename} - {self.device_id[:16]}..."

    @staticmethod
    def generate_device_id(fingerprint_data: Dict[str, Any]) -> str:
        """Generate device ID from fingerprint data."""
        # Combine relevant fingerprint fields
        fingerprint_str = '|'.join([
            str(fingerprint_data.get('canvas', '')),
            str(fingerprint_data.get('webgl', '')),
            str(fingerprint_data.get('fonts', '')),
            str(fingerprint_data.get('plugins', '')),
            str(fingerprint_data.get('screen', '')),
        ])
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()


class DeviceRiskEvent(TenantAwareModel):
    """
    Security events related to device activity.

    Tracks suspicious behavior, failed attempts, and security violations.
    """

    EVENT_TYPES = [
        ('ENROLLMENT_FAIL', 'Enrollment Failed'),
        ('SPOOFING_DETECTED', 'Spoofing Detected'),
        ('LOCATION_ANOMALY', 'Unusual Location'),
        ('EXCESSIVE_ATTEMPTS', 'Too Many Attempts'),
        ('DEVICE_CHANGE', 'Device Characteristics Changed'),
        ('NETWORK_RISK', 'Risky Network'),
    ]

    # Event identification
    event_id = models.AutoField(primary_key=True)
    device = models.ForeignKey(
        DeviceRegistration,
        on_delete=models.CASCADE,
        related_name='risk_events',
        help_text="Associated device"
    )

    # Event details
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES,
        help_text="Type of security event"
    )
    risk_score = models.IntegerField(
        help_text="Risk score for this event (0-100)"
    )
    event_data = models.JSONField(
        default=dict,
        help_text="Detailed event information"
    )

    # Context
    detected_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When event was detected"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        help_text="IP address at time of event"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent at time of event"
    )

    # Response
    action_taken = models.CharField(
        max_length=100,
        blank=True,
        help_text="Automated action taken"
    )
    resolved = models.BooleanField(
        default=False,
        help_text="Event resolved/cleared"
    )
    resolved_at = models.DateTimeField(
        null=True,
        help_text="When event was resolved"
    )

    class Meta:
        db_table = 'device_risk_event'
        indexes = [
            models.Index(fields=['device', 'detected_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['resolved', 'detected_at']),
        ]
        ordering = ['-detected_at']
        verbose_name = "Device Risk Event"
        verbose_name_plural = "Device Risk Events"

    def __str__(self):
        return f"{self.event_type} - {self.device.device_id[:16]}... ({self.detected_at})"
