"""
Voice Script Template Model.

Configurable voice scripts for different anomaly types.
Supports multiple languages and dynamic variable replacement.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class VoiceScriptTemplate(BaseModel, TenantAwareModel):
    """
    Voice script template for IVR calls.

    Templates use variable replacement (e.g., {guard_name}, {site_name}).
    """

    ANOMALY_TYPE_CHOICES = [
        ('GUARD_INACTIVITY', 'Guard Inactivity'),
        ('WRONG_PERSON', 'Wrong Person at Site'),
        ('UNAUTHORIZED_SITE', 'Unauthorized Site Access'),
        ('BUDDY_PUNCHING', 'Buddy Punching Suspected'),
        ('GPS_SPOOFING', 'GPS Spoofing Suspected'),
        ('GEOFENCE_VIOLATION', 'Geofence Violation'),
        ('TASK_OVERDUE', 'Critical Task Overdue'),
        ('TOUR_MISSED', 'Tour Missed'),
        ('GENERIC', 'Generic Security Check'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('mr', 'Marathi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
        ('kn', 'Kannada'),
    ]

    name = models.CharField(
        max_length=100,
        help_text="Template name"
    )

    anomaly_type = models.CharField(
        max_length=30,
        choices=ANOMALY_TYPE_CHOICES,
        db_index=True,
        help_text="Anomaly type for this script"
    )

    language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='en',
        db_index=True,
        help_text="Script language"
    )

    script_text = models.TextField(
        help_text="Script with variable placeholders (e.g., {guard_name}, {site_name})"
    )

    tts_audio_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Pre-generated TTS audio URL"
    )

    tts_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When TTS audio was generated"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether template is active"
    )

    expected_responses = models.JSONField(
        default=dict,
        help_text="Expected DTMF/voice responses with meanings"
    )

    escalation_triggers = models.JSONField(
        default=list,
        help_text="Responses that should trigger escalation"
    )

    version = models.CharField(
        max_length=20,
        default='1.0',
        help_text="Template version"
    )

    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times used"
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last usage timestamp"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_voice_script_template'
        verbose_name = 'Voice Script Template'
        verbose_name_plural = 'Voice Script Templates'
        indexes = [
            models.Index(fields=['tenant', 'anomaly_type', 'language', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'anomaly_type', 'language', 'version'],
                name='unique_template_per_anomaly_lang'
            ),
        ]

    def __str__(self):
        return f"{self.get_anomaly_type_display()} - {self.get_language_display()} v{self.version}"

    def render_script(self, context):
        """
        Render script with variable replacement.

        Args:
            context: dict with variable values

        Returns:
            str: Rendered script
        """
        return self.script_text.format(**context)

    def increment_usage(self):
        """Increment usage counter."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])

    @classmethod
    def get_active_template(cls, tenant, anomaly_type, language='en'):
        """
        Get active template for anomaly type and language.

        Args:
            tenant: Tenant instance
            anomaly_type: Anomaly type
            language: Language code

        Returns:
            VoiceScriptTemplate or None
        """
        return cls.objects.filter(
            tenant=tenant,
            anomaly_type=anomaly_type,
            language=language,
            is_active=True
        ).order_by('-version').first()