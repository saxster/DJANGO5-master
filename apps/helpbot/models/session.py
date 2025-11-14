"""
HelpBot Session Model

Tracks user interactions with the AI HelpBot for context and analytics.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel


class HelpBotSession(BaseModel, TenantAwareModel):
    """
    HelpBot conversation session - extends existing ConversationSession patterns.
    Tracks user interactions with the AI HelpBot for context and analytics.
    """

    class SessionTypeChoices(models.TextChoices):
        GENERAL_HELP = "general_help", _("General Help")
        FEATURE_GUIDE = "feature_guide", _("Feature Guide")
        TROUBLESHOOTING = "troubleshooting", _("Troubleshooting")
        API_DOCUMENTATION = "api_docs", _("API Documentation")
        TUTORIAL = "tutorial", _("Tutorial")
        ONBOARDING = "onboarding", _("Onboarding")
        SECURITY_FACILITY = "security_facility", _("Security & Facility Mentor")

    class StateChoices(models.TextChoices):
        ACTIVE = "active", _("Active")
        WAITING = "waiting", _("Waiting for Response")
        COMPLETED = "completed", _("Completed")
        IDLE = "idle", _("Idle")
        ERROR = "error", _("Error")

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="helpbot_sessions",
        verbose_name=_("User")
    )
    client = models.ForeignKey(
        "client_onboarding.Bt",
        on_delete=models.CASCADE,
        related_name="helpbot_sessions",
        verbose_name=_("Client"),
        null=True,
        blank=True
    )
    session_type = models.CharField(
        _("Session Type"),
        max_length=50,
        choices=SessionTypeChoices.choices,
        default=SessionTypeChoices.GENERAL_HELP
    )
    current_state = models.CharField(
        _("Current State"),
        max_length=20,
        choices=StateChoices.choices,
        default=StateChoices.ACTIVE
    )
    context_data = models.JSONField(
        _("Context Data"),
        default=dict,
        blank=True,
        help_text="Current page context, user journey, and session metadata"
    )
    language = models.CharField(
        _("Language"),
        max_length=10,
        default="en",
        help_text="User's preferred language for help content"
    )
    voice_enabled = models.BooleanField(
        _("Voice Enabled"),
        default=False,
        help_text="Whether voice interaction is enabled for this session"
    )
    last_activity = models.DateTimeField(
        _("Last Activity"),
        auto_now=True,
        help_text="Timestamp of last user interaction"
    )
    total_messages = models.IntegerField(
        _("Total Messages"),
        default=0,
        help_text="Total number of messages in this session"
    )
    satisfaction_rating = models.IntegerField(
        _("Satisfaction Rating"),
        null=True,
        blank=True,
        help_text="User satisfaction rating (1-5)"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_session"
        verbose_name = "HelpBot Session"
        verbose_name_plural = "HelpBot Sessions"
        get_latest_by = ["last_activity", "cdtz"]
        indexes = [
            models.Index(fields=['user', 'current_state'], name='helpbot_user_state_idx'),
            models.Index(fields=['session_type', 'last_activity'], name='helpbot_type_activity_idx'),
            models.Index(fields=['last_activity'], name='helpbot_activity_idx'),
        ]

    def __str__(self):
        return f"HelpBot Session {self.session_id} - {self.user.email} ({self.session_type})"
