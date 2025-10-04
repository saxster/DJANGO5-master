"""
IVR Call Log Model.

Tracks all IVR calls made to guards for security verification.
Records call status, responses, and outcomes.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class IVRCallLog(BaseModel, TenantAwareModel):
    """
    Log of IVR calls made for guard verification.

    Tracks call lifecycle, responses, and verification outcomes.
    """

    CALL_STATUS_CHOICES = [
        ('QUEUED', 'Queued'),
        ('RINGING', 'Ringing'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('BUSY', 'Busy'),
        ('NO_ANSWER', 'No Answer'),
        ('CANCELED', 'Canceled'),
    ]

    PROVIDER_CHOICES = [
        ('TWILIO', 'Twilio Voice'),
        ('GOOGLE_VOICE', 'Google Cloud Voice'),
        ('SMS', 'SMS Fallback'),
        ('MOCK', 'Mock Provider (Testing)'),
    ]

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='ivr_calls',
        help_text="Guard being called"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='ivr_calls',
        help_text="Site where anomaly occurred"
    )

    anomaly_log = models.ForeignKey(
        'noc_security_intelligence.AttendanceAnomalyLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ivr_calls',
        help_text="Triggering attendance anomaly"
    )

    inactivity_alert = models.ForeignKey(
        'noc_security_intelligence.InactivityAlert',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ivr_calls',
        help_text="Triggering inactivity alert"
    )

    noc_alert = models.ForeignKey(
        'noc.NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ivr_calls',
        help_text="Related NOC alert"
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        db_index=True,
        help_text="IVR provider used"
    )

    call_sid = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Provider call identifier"
    )

    phone_number_masked = models.CharField(
        max_length=20,
        help_text="Masked phone number (last 4 digits only)"
    )

    call_status = models.CharField(
        max_length=20,
        choices=CALL_STATUS_CHOICES,
        default='QUEUED',
        db_index=True,
        help_text="Current call status"
    )

    initiated_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When call was initiated"
    )

    answered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When call was answered"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When call completed"
    )

    duration_seconds = models.IntegerField(
        default=0,
        help_text="Call duration (seconds)"
    )

    call_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Call cost in rupees"
    )

    script_template = models.ForeignKey(
        'VoiceScriptTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calls',
        help_text="Voice script used"
    )

    response_received = models.BooleanField(
        default=False,
        help_text="Whether response was received"
    )

    is_successful_verification = models.BooleanField(
        default=False,
        help_text="Whether verification was successful"
    )

    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Provider-specific metadata"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if failed"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_ivr_call_log'
        verbose_name = 'IVR Call Log'
        verbose_name_plural = 'IVR Call Logs'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['tenant', 'initiated_at']),
            models.Index(fields=['person', 'initiated_at']),
            models.Index(fields=['site', 'call_status']),
            models.Index(fields=['provider', 'call_status']),
            models.Index(fields=['is_successful_verification']),
        ]

    def __str__(self):
        return f"IVR Call: {self.person.peoplename} - {self.call_status} ({self.provider})"

    def mark_answered(self):
        """Mark call as answered."""
        self.call_status = 'IN_PROGRESS'
        self.answered_at = timezone.now()
        self.save()

    def mark_completed(self, duration):
        """Mark call as completed."""
        self.call_status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.duration_seconds = duration
        self.save()

    @classmethod
    def get_recent_calls_to_person(cls, person, hours=1):
        """Get recent calls to person for rate limiting."""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return cls.objects.filter(
            person=person,
            initiated_at__gte=cutoff
        ).count()