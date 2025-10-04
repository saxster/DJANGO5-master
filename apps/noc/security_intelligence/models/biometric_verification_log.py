"""
Biometric Verification Log Model.

Enhanced biometric tracking for fraud detection.
Records biometric quality, timing patterns, and concurrent usage.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class BiometricVerificationLog(BaseModel, TenantAwareModel):
    """
    Detailed biometric verification log for fraud detection.

    Tracks biometric quality, patterns, and concurrent usage.
    """

    VERIFICATION_TYPE_CHOICES = [
        ('FACE', 'Face Recognition'),
        ('FINGERPRINT', 'Fingerprint'),
        ('IRIS', 'Iris Scan'),
        ('MULTI', 'Multi-factor Biometric'),
    ]

    RESULT_CHOICES = [
        ('SUCCESS', 'Verified Successfully'),
        ('FAILED', 'Verification Failed'),
        ('LOW_QUALITY', 'Low Quality Image/Scan'),
        ('SUSPICIOUS', 'Suspicious Pattern'),
        ('FRAUD_DETECTED', 'Fraud Detected'),
    ]

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='biometric_verifications',
        help_text="Person being verified"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='biometric_verifications',
        help_text="Site where verification occurred"
    )

    attendance_event = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biometric_verifications',
        help_text="Related attendance event"
    )

    verified_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Verification timestamp"
    )

    verification_type = models.CharField(
        max_length=20,
        choices=VERIFICATION_TYPE_CHOICES,
        help_text="Type of biometric verification"
    )

    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        db_index=True,
        help_text="Verification result"
    )

    confidence_score = models.FloatField(
        help_text="Biometric match confidence (0-1)"
    )

    quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Image/scan quality score (0-1)"
    )

    device_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Device used for verification"
    )

    # Fraud detection fields
    is_concurrent = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Concurrent verification detected"
    )

    concurrent_sites = models.JSONField(
        default=list,
        help_text="Other sites with concurrent verification"
    )

    is_suspicious_pattern = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Suspicious timing pattern detected"
    )

    pattern_indicators = models.JSONField(
        default=list,
        help_text="List of suspicious pattern indicators"
    )

    fraud_score = models.FloatField(
        default=0.0,
        help_text="Overall fraud probability (0-1)"
    )

    # Face recognition specific
    face_embedding_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of face embedding used"
    )

    liveness_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Liveness detection score (0-1)"
    )

    # Metadata
    verification_metadata = models.JSONField(
        default=dict,
        help_text="Additional verification details"
    )

    # Investigation
    flagged_for_review = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged for manual review"
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_biometric_logs',
        help_text="Reviewer"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Review timestamp"
    )

    review_notes = models.TextField(
        blank=True,
        help_text="Review findings"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_biometric_verification_log'
        verbose_name = 'Biometric Verification Log'
        verbose_name_plural = 'Biometric Verification Logs'
        ordering = ['-verified_at']
        indexes = [
            models.Index(fields=['tenant', 'verified_at']),
            models.Index(fields=['person', 'verified_at']),
            models.Index(fields=['site', 'result', 'verified_at']),
            models.Index(fields=['is_concurrent', 'is_suspicious_pattern']),
            models.Index(fields=['fraud_score']),
            models.Index(fields=['flagged_for_review']),
        ]

    def __str__(self):
        return f"{self.verification_type} - {self.person.peoplename} @ {self.site.name} ({self.result})"

    def flag_for_review(self, reason=""):
        """Flag for manual review."""
        self.flagged_for_review = True
        if reason:
            self.review_notes = f"Auto-flagged: {reason}"
        self.save()

    @classmethod
    def get_recent_for_person(cls, person, hours=24):
        """Get recent verifications for person."""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return cls.objects.filter(
            person=person,
            verified_at__gte=cutoff
        ).order_by('-verified_at')