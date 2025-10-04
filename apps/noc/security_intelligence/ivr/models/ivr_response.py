"""
IVR Response Model.

Stores guard responses from IVR calls.
Tracks DTMF input and voice transcriptions.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class IVRResponse(BaseModel, TenantAwareModel):
    """
    Guard response from IVR call.

    Stores DTMF keypresses or voice transcriptions.
    """

    RESPONSE_TYPE_CHOICES = [
        ('DTMF', 'DTMF Keypress'),
        ('VOICE', 'Voice Response'),
        ('TIMEOUT', 'No Response (Timeout)'),
    ]

    VALIDATION_RESULT_CHOICES = [
        ('CONFIRMED', 'Guard Confirmed Present'),
        ('DENIED', 'Guard Denied/Suspicious'),
        ('ASSISTANCE_REQUESTED', 'Assistance Requested'),
        ('UNCLEAR', 'Unclear Response'),
        ('TIMEOUT', 'No Response'),
        ('INVALID', 'Invalid Response'),
    ]

    call_log = models.ForeignKey(
        'IVRCallLog',
        on_delete=models.CASCADE,
        related_name='responses',
        help_text="Related IVR call"
    )

    response_timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When response was received"
    )

    response_type = models.CharField(
        max_length=20,
        choices=RESPONSE_TYPE_CHOICES,
        help_text="Type of response"
    )

    # DTMF response
    dtmf_input = models.CharField(
        max_length=10,
        blank=True,
        help_text="DTMF digits pressed (e.g., '1', '2')"
    )

    # Voice response
    voice_transcript = models.TextField(
        blank=True,
        help_text="STT transcript of voice response"
    )

    voice_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="STT confidence score (0-1)"
    )

    audio_recording_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Audio recording URL (if enabled)"
    )

    audio_duration_seconds = models.IntegerField(
        default=0,
        help_text="Audio duration (seconds)"
    )

    # Validation
    is_valid_response = models.BooleanField(
        default=False,
        help_text="Whether response is valid"
    )

    validation_result = models.CharField(
        max_length=30,
        choices=VALIDATION_RESULT_CHOICES,
        db_index=True,
        help_text="Validation outcome"
    )

    validation_confidence = models.FloatField(
        default=0.0,
        help_text="Validation confidence (0-1)"
    )

    # Processing
    processing_time_ms = models.IntegerField(
        default=0,
        help_text="Response processing time (ms)"
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When response was processed"
    )

    # Actions taken
    action_taken = models.CharField(
        max_length=50,
        blank=True,
        help_text="Action taken based on response"
    )

    escalated = models.BooleanField(
        default=False,
        help_text="Whether response triggered escalation"
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Additional response data"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_ivr_response'
        verbose_name = 'IVR Response'
        verbose_name_plural = 'IVR Responses'
        ordering = ['-response_timestamp']
        indexes = [
            models.Index(fields=['tenant', 'response_timestamp']),
            models.Index(fields=['call_log', 'response_type']),
            models.Index(fields=['validation_result', 'escalated']),
        ]

    def __str__(self):
        return f"Response: {self.validation_result} ({self.response_type})"

    def mark_validated(self, result, confidence, action=""):
        """Mark response as validated."""
        self.is_valid_response = result in ['CONFIRMED', 'ASSISTANCE_REQUESTED']
        self.validation_result = result
        self.validation_confidence = confidence
        self.action_taken = action
        self.processed_at = timezone.now()
        self.save()

    @property
    def response_text(self):
        """Get human-readable response text."""
        if self.response_type == 'DTMF':
            return f"Pressed: {self.dtmf_input}"
        elif self.response_type == 'VOICE':
            return self.voice_transcript or "Voice response (no transcript)"
        else:
            return "No response"