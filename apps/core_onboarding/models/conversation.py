"""
Conversation Session Model - Shared Kernel

Tracks conversational onboarding sessions across ALL contexts:
- Client setup conversations
- Site survey conversations
- Worker intake conversations

Features:
- Voice OR text input mode
- Multi-language support
- State machine (7 states)
- Audio transcript storage
- Context routing

Extracted from: apps/onboarding/models/conversational_ai.py
Complies with Rule #7: Model < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TenantAwareModel


class ConversationSession(TenantAwareModel):
    """
    Conversation session for multimodal onboarding.

    Used by all three contexts:
    - CLIENT: "Help me set up a new client"
    - SITE: "I want to survey this site"
    - WORKER: "Onboard a new security guard"
    """

    class ConversationType(models.TextChoices):
        INITIAL_SETUP = 'INITIAL_SETUP', _('Initial Setup')
        CONFIG_UPDATE = 'CONFIG_UPDATE', _('Configuration Update')
        TROUBLESHOOTING = 'TROUBLESHOOTING', _('Troubleshooting')
        FEATURE_REQUEST = 'FEATURE_REQUEST', _('Feature Request')

    class CurrentState(models.TextChoices):
        STARTED = 'STARTED', _('Started')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        GENERATING_RECOMMENDATIONS = 'GENERATING_RECOMMENDATIONS', _('Generating Recommendations')
        AWAITING_USER_APPROVAL = 'AWAITING_USER_APPROVAL', _('Awaiting User Approval')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')
        ERROR = 'ERROR', _('Error')

    class ContextType(models.TextChoices):
        CLIENT = 'CLIENT', _('Client Onboarding')
        SITE = 'SITE', _('Site Survey')
        WORKER = 'WORKER', _('Worker Intake')

    # Identifiers
    session_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Context routing (NEW: determines which handler to use)
    context_type = models.CharField(
        _('Context Type'),
        max_length=20,
        choices=ContextType.choices,
        help_text=_('Which bounded context this conversation is for')
    )
    context_object_id = models.CharField(
        _('Context Object ID'),
        max_length=100,
        blank=True,
        help_text=_('ID of created object (site_id, request_id, client_id)')
    )
    handler_class = models.CharField(
        _('Handler Class'),
        max_length=200,
        blank=True,
        help_text=_('Fully qualified handler class name')
    )

    # Session details
    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='conversation_sessions'
    )
    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversation_sessions',
        help_text=_('Client context for this conversation')
    )
    conversation_type = models.CharField(
        _('Conversation Type'),
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.INITIAL_SETUP
    )
    current_state = models.CharField(
        _('Current State'),
        max_length=30,
        choices=CurrentState.choices,
        default=CurrentState.STARTED
    )

    # Context data
    context_data = models.JSONField(
        default=dict,
        help_text=_('Initial context: {"client_id": "...", "language": "en"}')
    )
    collected_data = models.JSONField(
        default=dict,
        help_text=_('Accumulated data from conversation')
    )

    # Voice support
    voice_enabled = models.BooleanField(
        default=False,
        help_text=_('Voice input enabled for this session')
    )
    audio_transcripts = models.JSONField(
        default=list,
        help_text=_('Array of voice interactions: [{"user": "...", "assistant": "..."}]')
    )

    # Language
    language = models.CharField(
        _('Language'),
        max_length=10,
        default='en',
        help_text=_('ISO 639-1 language code')
    )

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    last_interaction_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_onboarding_conversation'
        verbose_name = 'Conversation Session'
        verbose_name_plural = 'Conversation Sessions'
        indexes = [
            models.Index(fields=['context_type', 'current_state'], name='conv_context_state_idx'),
            models.Index(fields=['user'], name='conv_user_idx'),
            models.Index(fields=['started_at'], name='conv_started_idx'),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.get_context_type_display()} - {self.get_current_state_display()}"

    # Backward compatibility aliases
    @property
    def initiated_by(self):
        return self.user

    @initiated_by.setter
    def initiated_by(self, value):
        self.user = value
