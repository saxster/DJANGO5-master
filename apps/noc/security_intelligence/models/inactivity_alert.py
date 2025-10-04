"""
Inactivity Alert Model.

Records detected inactivity incidents for night shift guards.
Links to NOC alert system for immediate escalation.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class InactivityAlert(BaseModel, TenantAwareModel):
    """
    Alert for detected guard inactivity.

    Triggered when guard shows no activity for extended period.
    """

    SEVERITY_CHOICES = [
        ('LOW', 'Low - Minor Inactivity'),
        ('MEDIUM', 'Medium - Concerning Pattern'),
        ('HIGH', 'High - Likely Sleeping'),
        ('CRITICAL', 'Critical - No Response'),
    ]

    STATUS_CHOICES = [
        ('DETECTED', 'Detected'),
        ('VERIFYING', 'Verification in Progress'),
        ('CONFIRMED', 'Confirmed Inactivity'),
        ('RESOLVED', 'Resolved'),
        ('FALSE_POSITIVE', 'False Positive'),
    ]

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='inactivity_alerts',
        help_text="Guard with detected inactivity"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='inactivity_alerts',
        help_text="Site where inactivity detected"
    )

    activity_tracking = models.ForeignKey(
        'GuardActivityTracking',
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text="Related activity tracking record"
    )

    noc_alert = models.ForeignKey(
        'noc.NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inactivity_alerts',
        help_text="Related NOC alert"
    )

    detected_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When inactivity was detected"
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        db_index=True,
        help_text="Severity of inactivity"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DETECTED',
        db_index=True,
        help_text="Alert status"
    )

    inactivity_score = models.FloatField(
        help_text="Inactivity score (0-1)"
    )

    inactivity_duration_minutes = models.IntegerField(
        help_text="Duration of inactivity (minutes)"
    )

    # Missing activity indicators
    no_phone_activity = models.BooleanField(
        default=False,
        help_text="No phone/app activity detected"
    )

    no_movement = models.BooleanField(
        default=False,
        help_text="No GPS movement detected"
    )

    no_tasks_completed = models.BooleanField(
        default=False,
        help_text="No tasks completed"
    )

    no_tour_scans = models.BooleanField(
        default=False,
        help_text="No tour checkpoints scanned"
    )

    is_deep_night = models.BooleanField(
        default=False,
        help_text="Occurred during deep night hours (1-5 AM)"
    )

    evidence_data = models.JSONField(
        default=dict,
        help_text="Activity counters and evidence"
    )

    # Verification and resolution
    verification_attempted = models.BooleanField(
        default=False,
        help_text="Whether verification was attempted"
    )

    verification_method = models.CharField(
        max_length=20,
        choices=[
            ('NONE', 'No Verification'),
            ('CALL', 'Phone Call'),
            ('IVR', 'Automated IVR'),
            ('SUPERVISOR', 'Supervisor Check'),
            ('CAMERA', 'CCTV Review'),
        ],
        default='NONE',
        help_text="Verification method used"
    )

    verification_response = models.TextField(
        blank=True,
        help_text="Response from verification"
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_inactivity_alerts',
        help_text="Who resolved the alert"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When alert was resolved"
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text="Resolution details"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_inactivity_alert'
        verbose_name = 'Inactivity Alert'
        verbose_name_plural = 'Inactivity Alerts'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['tenant', 'detected_at']),
            models.Index(fields=['person', 'detected_at']),
            models.Index(fields=['site', 'severity', 'detected_at']),
            models.Index(fields=['status', 'is_deep_night']),
        ]

    def __str__(self):
        return f"Inactivity: {self.person.peoplename} @ {self.site.name} ({self.severity})"

    def mark_verified(self, method, response=""):
        """Mark alert as verified."""
        self.verification_attempted = True
        self.verification_method = method
        self.verification_response = response
        self.status = 'VERIFYING'
        self.save()

    def mark_confirmed(self, resolved_by, notes=""):
        """Mark as confirmed inactivity."""
        self.status = 'CONFIRMED'
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()

    def mark_resolved(self, resolved_by, notes=""):
        """Mark as resolved."""
        self.status = 'RESOLVED'
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()