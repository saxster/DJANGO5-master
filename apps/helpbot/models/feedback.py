"""
HelpBot Feedback Model

User feedback on HelpBot interactions for continuous improvement.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel


class HelpBotFeedback(BaseModel, TenantAwareModel):
    """
    User feedback on HelpBot interactions for continuous improvement.
    Extends existing UserFeedbackLearning patterns.
    """

    class FeedbackTypeChoices(models.TextChoices):
        HELPFUL = "helpful", _("Helpful")
        NOT_HELPFUL = "not_helpful", _("Not Helpful")
        INCORRECT = "incorrect", _("Incorrect")
        INCOMPLETE = "incomplete", _("Incomplete")
        SUGGESTION = "suggestion", _("Suggestion")

    feedback_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session = models.ForeignKey(
        'helpbot.HelpBotSession',
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name=_("Session")
    )
    message = models.ForeignKey(
        'helpbot.HelpBotMessage',
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name=_("Message"),
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="helpbot_feedback",
        verbose_name=_("User")
    )
    feedback_type = models.CharField(
        _("Feedback Type"),
        max_length=20,
        choices=FeedbackTypeChoices.choices
    )
    rating = models.IntegerField(
        _("Rating"),
        null=True,
        blank=True,
        help_text="Numeric rating (1-5)"
    )
    comment = models.TextField(
        _("Comment"),
        blank=True,
        null=True,
        help_text="User's detailed feedback"
    )
    suggestion = models.TextField(
        _("Suggestion"),
        blank=True,
        null=True,
        help_text="User's suggestion for improvement"
    )
    context_data = models.JSONField(
        _("Context Data"),
        default=dict,
        blank=True,
        help_text="Context when feedback was given"
    )
    is_processed = models.BooleanField(
        _("Is Processed"),
        default=False,
        help_text="Whether this feedback has been processed for learning"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_feedback"
        verbose_name = "HelpBot Feedback"
        verbose_name_plural = "HelpBot Feedback"
        get_latest_by = ["cdtz"]
        indexes = [
            models.Index(fields=['session', 'feedback_type'], name='hb_feedback_sess_type_idx'),
            models.Index(fields=['is_processed', 'cdtz'], name='hb_feedback_processed_idx'),
        ]

    def __str__(self):
        return f"Feedback {self.feedback_id} - {self.feedback_type} ({self.rating}/5)"
