"""
Universal Observation Model for Multimodal Onboarding

Supports:
- Voice OR text input (user choice)
- 0 to N photos/videos per observation
- GPS location capture
- AI enhancement (LLM + Vision API)
- Entity extraction (NER)

Complies with Rule #7: Model < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantAwareModel


class OnboardingObservation(TenantAwareModel):
    """
    Universal observation for voice/text + media across all contexts.

    Input modes (mutually exclusive):
    - Voice: audio_file + original_transcript
    - Text: text_input only

    Media attachments (0 to N):
    - Photos, videos linked via ManyToMany
    - GPS captured per media
    """

    # Identifiers
    observation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Context linkage
    context_type = models.CharField(
        _('Context Type'),
        max_length=20,
        choices=[
            ('CLIENT', _('Client Setup')),
            ('SITE', _('Site Survey')),
            ('WORKER', _('Worker Documents')),
        ]
    )
    context_object_id = models.CharField(
        _('Context Object ID'),
        max_length=100,
        help_text=_('UUID of related object')
    )

    # Conversation link (optional)
    conversation_session = models.ForeignKey(
        'core_onboarding.ConversationSession',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='observations'
    )

    # Voice input (Option 1: Voice OR text)
    audio_file = models.FileField(
        _('Audio File'),
        upload_to='observations/audio/',
        null=True,
        blank=True
    )
    original_transcript = models.TextField(
        _('Original Transcript'),
        blank=True,
        help_text=_('Raw speech-to-text output')
    )

    # Text input (Option 2: Voice OR text)
    text_input = models.TextField(
        _('Text Input'),
        blank=True,
        help_text=_('User-typed text (alternative to voice)')
    )

    # Enhanced by AI
    english_translation = models.TextField(
        _('English Translation'),
        blank=True
    )
    enhanced_observation = models.TextField(
        _('Enhanced Observation'),
        blank=True,
        help_text=_('LLM-enhanced version with context')
    )

    # Linked media (0 to N - ManyToMany for flexibility)
    media = models.ManyToManyField(
        'core_onboarding.OnboardingMedia',
        related_name='observations',
        blank=True,
        help_text=_('Photos/videos attached to this observation (0 to N)')
    )

    # Severity/classification
    severity = models.CharField(
        _('Severity'),
        max_length=20,
        choices=[
            ('CRITICAL', _('Critical Issue')),
            ('HIGH', _('High Priority')),
            ('MEDIUM', _('Medium Priority')),
            ('LOW', _('Low Priority')),
            ('INFO', _('Informational')),
        ],
        default='INFO'
    )
    confidence_score = models.FloatField(
        _('Confidence Score'),
        default=0.0,
        help_text=_('AI confidence (0.0-1.0)')
    )

    # Entity extraction (NER)
    entities = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Named entities: {"location": "Gate 3", "asset": "Camera #5"}')
    )

    # Metadata
    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.PROTECT,
        related_name='created_observations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_onboarding_observation'
        verbose_name = 'Onboarding Observation'
        verbose_name_plural = 'Onboarding Observations'
        indexes = [
            models.Index(fields=['context_type', 'context_object_id'], name='obs_context_idx'),
            models.Index(fields=['created_at'], name='obs_created_idx'),
            models.Index(fields=['severity'], name='obs_severity_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        input_type = 'Voice' if self.audio_file else 'Text'
        return f"{input_type} observation - {self.context_type} ({self.created_at})"

    def has_media(self) -> bool:
        """Check if observation has any media attachments"""
        return self.media.exists()

    def media_count(self) -> int:
        """Count of attached media"""
        return self.media.count()
