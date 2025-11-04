"""
LLM Recommendation Model - Maker-checker pattern recommendations.

Stores LLM-generated recommendations with validation and user decision tracking.
Part of the shared kernel for conversational AI onboarding.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


class LLMRecommendation(BaseModel, TenantAwareModel):
    """Stores LLM-generated recommendations with maker-checker pattern."""

    class UserDecisionChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        MODIFIED = "modified", _("Modified")

    class StatusChoices(models.TextChoices):
        QUEUED = "queued", _("Queued")
        PROCESSING = "processing", _("Processing")
        VALIDATED = "validated", _("Validated")
        NEEDS_REVIEW = "needs_review", _("Needs Review")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")

    recommendation_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session = models.ForeignKey(
        'core_onboarding.ConversationSession',
        on_delete=models.CASCADE,
        related_name="recommendations",
        verbose_name=_("Session")
    )
    maker_output = models.JSONField(
        _("Maker Output"),
        help_text="Raw output from the maker LLM"
    )
    checker_output = models.JSONField(
        _("Checker Output"),
        null=True,
        blank=True,
        help_text="Validation output from checker LLM"
    )
    consensus = models.JSONField(
        _("Consensus"),
        default=dict,
        blank=True,
        help_text="Final consensus between maker and checker"
    )
    authoritative_sources = models.JSONField(
        _("Authoritative Sources"),
        default=list,
        blank=True,
        help_text="References to authoritative knowledge sources"
    )
    confidence_score = models.FloatField(
        _("Confidence Score"),
        help_text=_("Overall confidence score (0.0 to 1.0)")
    )
    user_decision = models.CharField(
        _("User Decision"),
        max_length=20,
        choices=UserDecisionChoices.choices,
        default=UserDecisionChoices.PENDING
    )
    rejection_reason = models.TextField(
        _("Rejection Reason"),
        blank=True,
        null=True,
        help_text="Why the user rejected the recommendation"
    )
    modifications = models.JSONField(
        _("Modifications"),
        default=dict,
        blank=True,
        help_text="User modifications to the recommendation"
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.QUEUED,
        help_text="Current processing status of the recommendation"
    )
    latency_ms = models.IntegerField(
        _("Latency (ms)"),
        null=True,
        blank=True,
        help_text="Total processing time in milliseconds"
    )
    provider_cost_cents = models.IntegerField(
        _("Provider Cost (cents)"),
        null=True,
        blank=True,
        help_text="Cost of LLM provider calls in cents"
    )
    eval_scores = models.JSONField(
        _("Evaluation Scores"),
        default=dict,
        blank=True,
        help_text="Quality evaluation scores and metrics"
    )
    trace_id = models.CharField(
        _("Trace ID"),
        max_length=50,
        blank=True,
        help_text="Distributed tracing ID for request correlation"
    )

    class Meta(BaseModel.Meta):
        db_table = "llm_recommendation"
        verbose_name = "LLM Recommendation"
        verbose_name_plural = "LLM Recommendations"
        get_latest_by = ["mdtz", "cdtz"]
        indexes = [
            models.Index(fields=['session', 'status'], name='llm_rec_session_status_idx'),
            models.Index(fields=['confidence_score'], name='llm_rec_confidence_idx'),
            models.Index(fields=['trace_id'], name='llm_rec_trace_id_idx'),
            models.Index(fields=['status', 'cdtz'], name='llm_rec_status_created_idx'),
        ]

    def __str__(self):
        return f"Recommendation {self.recommendation_id} - {self.status} - {self.user_decision}"
