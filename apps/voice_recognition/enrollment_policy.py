"""
Voice Enrollment Policy Model

Configurable security policies for voice biometric enrollment.

Policy Controls:
- Device trust threshold (0-100)
- Location requirements (on-site, approved networks)
- Supervisor approval requirements
- Re-enrollment intervals
- Step-up authentication triggers

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization

Sprint 4: Voice Enrollment Security Enhancement
"""

import logging
from django.db import models
from django.core.exceptions import ValidationError
from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class EnrollmentPolicy(TenantAwareModel):
    """
    Configurable security policy for voice biometric enrollment.

    Defines security controls and requirements for enrollment process.
    """

    LOCATION_REQUIREMENTS = [
        ('any', 'Any Location (Least Secure)'),
        ('approved_network', 'Approved Network Only'),
        ('on_site', 'On-Site Only (Most Secure)'),
        ('geofence', 'Within Geofence'),
    ]

    # Identification
    policy_name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Policy name (e.g., 'Standard Security', 'High Security')"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Policy is active and enforced"
    )

    # Device trust requirements
    min_device_trust_score = models.IntegerField(
        default=70,
        help_text="Minimum device trust score (0-100) required for enrollment"
    )

    require_device_registration = models.BooleanField(
        default=True,
        help_text="Device must be pre-registered before enrollment"
    )

    # Location requirements
    location_requirement = models.CharField(
        max_length=20,
        choices=LOCATION_REQUIREMENTS,
        default='approved_network',
        help_text="Location security requirement"
    )

    approved_networks = models.JSONField(
        default=list,
        help_text="List of approved network CIDRs (e.g., ['192.168.1.0/24'])"
    )

    approved_sites = models.JSONField(
        default=list,
        help_text="List of approved site IDs for on-site enrollment"
    )

    # Supervisor approval
    require_supervisor_approval = models.BooleanField(
        default=True,
        help_text="Require supervisor approval for enrollment"
    )

    supervisor_approval_timeout_hours = models.IntegerField(
        default=24,
        help_text="Hours before supervisor approval request expires"
    )

    # Re-enrollment controls
    min_reenrollment_interval_days = models.IntegerField(
        default=365,
        help_text="Minimum days before re-enrollment allowed"
    )

    force_reenrollment_after_days = models.IntegerField(
        default=730,
        help_text="Force re-enrollment after N days (biometric refresh)"
    )

    # Step-up authentication triggers
    require_mfa_for_remote_enrollment = models.BooleanField(
        default=True,
        help_text="Require MFA if enrolling from unapproved location"
    )

    require_face_biometrics = models.BooleanField(
        default=True,
        help_text="Require face biometrics before voice enrollment"
    )

    # Sample collection requirements
    min_voice_samples = models.IntegerField(
        default=5,
        help_text="Minimum voice samples required"
    )

    max_voice_samples = models.IntegerField(
        default=7,
        help_text="Maximum voice samples allowed"
    )

    min_voice_quality_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.70,
        help_text="Minimum voice quality score (0.00-1.00)"
    )

    # Timestamps
    cdtz = models.DateTimeField(
        auto_now_add=True,
        help_text="Created datetime"
    )

    mdtz = models.DateTimeField(
        auto_now=True,
        help_text="Modified datetime"
    )

    class Meta:
        db_table = 'voice_enrollment_policy'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['policy_name']),
        ]
        verbose_name = "Voice Enrollment Policy"
        verbose_name_plural = "Voice Enrollment Policies"
        ordering = ['policy_name']

    def __str__(self):
        return f"{self.policy_name} ({'Active' if self.is_active else 'Inactive'})"

    def clean(self):
        """Validate policy configuration."""
        super().clean()

        # Validate trust score range
        if not (0 <= self.min_device_trust_score <= 100):
            raise ValidationError({
                'min_device_trust_score': 'Score must be between 0 and 100'
            })

        # Validate sample counts
        if self.min_voice_samples > self.max_voice_samples:
            raise ValidationError({
                'min_voice_samples': 'Min samples cannot exceed max samples'
            })

        # Validate quality score
        if not (0 <= self.min_voice_quality_score <= 1):
            raise ValidationError({
                'min_voice_quality_score': 'Score must be between 0.00 and 1.00'
            })

        # Validate re-enrollment intervals
        if self.min_reenrollment_interval_days > self.force_reenrollment_after_days:
            raise ValidationError(
                'Min re-enrollment interval cannot exceed force re-enrollment interval'
            )

    def allows_enrollment(self, context: dict) -> tuple:
        """
        Check if policy allows enrollment given context.

        Args:
            context: Dict with device_trust_score, location_type, etc.

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Check device trust
        device_score = context.get('device_trust_score', 0)
        if device_score < self.min_device_trust_score:
            return False, f"Device trust score {device_score} below minimum {self.min_device_trust_score}"

        # Check location requirement
        if self.location_requirement == 'on_site' and not context.get('is_on_site'):
            return False, "On-site enrollment required"

        if self.location_requirement == 'approved_network' and not context.get('is_approved_network'):
            return False, "Approved network required"

        return True, "Policy requirements met"
