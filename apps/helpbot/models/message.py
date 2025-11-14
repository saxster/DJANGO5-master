"""
HelpBot Message Model

Individual messages within a HelpBot conversation.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel


class HelpBotMessage(BaseModel, TenantAwareModel):
    """
    Individual messages within a HelpBot conversation.
    Supports text, voice, and rich content including code examples and links.
    """

    class MessageTypeChoices(models.TextChoices):
        USER_TEXT = "user_text", _("User Text")
        USER_VOICE = "user_voice", _("User Voice")
        BOT_RESPONSE = "bot_response", _("Bot Response")
        SYSTEM_MESSAGE = "system", _("System Message")
        CONTEXT_UPDATE = "context", _("Context Update")

    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session = models.ForeignKey(
        'helpbot.HelpBotSession',
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Session")
    )
    message_type = models.CharField(
        _("Message Type"),
        max_length=20,
        choices=MessageTypeChoices.choices
    )
    content = models.TextField(
        _("Content"),
        help_text="Raw message content (text or transcript)"
    )
    rich_content = models.JSONField(
        _("Rich Content"),
        default=dict,
        blank=True,
        help_text="Structured content: links, code blocks, images, buttons"
    )
    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Technical metadata: confidence scores, processing time, sources"
    )
    knowledge_sources = models.JSONField(
        _("Knowledge Sources"),
        default=list,
        blank=True,
        help_text="References to knowledge sources used for this response"
    )
    confidence_score = models.FloatField(
        _("Confidence Score"),
        null=True,
        blank=True,
        help_text="AI confidence in the response (0.0 to 1.0)"
    )
    processing_time_ms = models.IntegerField(
        _("Processing Time (ms)"),
        null=True,
        blank=True,
        help_text="Time taken to generate the response"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_message"
        verbose_name = "HelpBot Message"
        verbose_name_plural = "HelpBot Messages"
        get_latest_by = ["cdtz"]
        indexes = [
            models.Index(fields=['session', 'cdtz'], name='helpbot_msg_session_time_idx'),
            models.Index(fields=['message_type', 'cdtz'], name='helpbot_msg_type_time_idx'),
        ]
        ordering = ['cdtz']

    def __str__(self):
        return f"Message {self.message_id} - {self.message_type} in {self.session}"
