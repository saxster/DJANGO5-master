"""
LLM Knowledge and Recommendation Models - Shared Kernel

Contains models for LLM-powered recommendations and authoritative knowledge
used across all onboarding contexts.

Models:
- LLMRecommendation: Maker-checker pattern recommendations
- AuthoritativeKnowledge: Grounding knowledge for LLMs
- AuthoritativeKnowledgeChunk: RAG retrieval chunks

Extracted from: apps/onboarding/models/conversational_ai.py
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField

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


class AuthoritativeKnowledge(BaseModel, TenantAwareModel):
    """Stores authoritative knowledge for LLM grounding and validation."""

    class AuthorityLevelChoices(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        OFFICIAL = "official", _("Official")

    knowledge_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    source_organization = models.CharField(
        _("Source Organization"),
        max_length=200,
        help_text="Organization that published this knowledge"
    )
    document_title = models.CharField(
        _("Document Title"),
        max_length=500,
        help_text="Title of the source document"
    )
    document_version = models.CharField(
        _("Document Version"),
        max_length=50,
        blank=True,
        help_text="Version of the document"
    )
    authority_level = models.CharField(
        _("Authority Level"),
        max_length=20,
        choices=AuthorityLevelChoices.choices,
        default=AuthorityLevelChoices.MEDIUM
    )
    content_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Content Vector"),
        help_text="Vector embedding of the content",
        null=True,
        blank=True
    )
    content_summary = models.TextField(
        _("Content Summary"),
        help_text="Summary of the knowledge content"
    )
    publication_date = models.DateTimeField(
        _("Publication Date"),
        help_text="When this knowledge was published"
    )
    last_verified = models.DateTimeField(
        _("Last Verified"),
        auto_now=True,
        help_text="When this knowledge was last verified"
    )
    is_current = models.BooleanField(
        _("Is Current"),
        default=True,
        help_text="Whether this knowledge is still current"
    )

    class Meta(BaseModel.Meta):
        db_table = "authoritative_knowledge"
        verbose_name = "Authoritative Knowledge"
        verbose_name_plural = "Authoritative Knowledge"
        get_latest_by = ["publication_date", "mdtz"]
        indexes = [
            models.Index(fields=['cdtz'], name='auth_know_cdtz_idx'),
            models.Index(fields=['mdtz'], name='auth_know_mdtz_idx'),
        ]

    def __str__(self):
        return f"{self.document_title} - {self.source_organization}"


class AuthoritativeKnowledgeChunk(BaseModel, TenantAwareModel):
    """Chunked knowledge content for RAG retrieval (Phase 2)."""

    chunk_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    knowledge = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name=_("Knowledge Document")
    )
    chunk_index = models.IntegerField(
        _("Chunk Index"),
        help_text="Sequential chunk number within the document"
    )
    content_text = models.TextField(
        _("Content Text"),
        help_text="Text content of this chunk"
    )
    content_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Content Vector"),
        help_text="Vector embedding of the chunk content",
        null=True,
        blank=True
    )
    tags = models.JSONField(
        _("Tags"),
        default=dict,
        blank=True,
        help_text="Metadata tags for filtering and categorization"
    )
    last_verified = models.DateTimeField(
        _("Last Verified"),
        auto_now=True,
        help_text="When this chunk was last verified for accuracy"
    )
    is_current = models.BooleanField(
        _("Is Current"),
        default=True,
        help_text="Whether this chunk is still current and valid"
    )

    class Meta(BaseModel.Meta):
        db_table = "authoritative_knowledge_chunk"
        verbose_name = "Knowledge Chunk"
        verbose_name_plural = "Knowledge Chunks"
        get_latest_by = ["last_verified", "mdtz"]
        indexes = [
            models.Index(fields=['knowledge', 'chunk_index'], name='knowledge_chunk_idx'),
            models.Index(fields=['is_current'], name='chunk_current_idx'),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.knowledge.document_title}"
