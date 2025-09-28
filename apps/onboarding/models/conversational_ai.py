"""
Conversational AI and LLM Models - Phase 1 MVP.

This module contains models for managing AI-powered conversational onboarding
sessions with maker-checker patterns and comprehensive tracking.

Key Features:
- ConversationSession tracking for user interactions
- LLMRecommendation with maker-checker validation
- AuthoritativeKnowledge for grounding AI responses
- UserFeedbackLearning for continuous improvement
- AuthoritativeKnowledgeChunk for RAG retrieval

Security:
- Comprehensive audit trails for all AI interactions
- Input validation and sanitization
- Confidence scoring and quality metrics
- Secure handling of user data and AI outputs
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


class ConversationSession(BaseModel, TenantAwareModel):
    """Tracks conversational onboarding sessions with users."""

    class ConversationTypeChoices(models.TextChoices):
        INITIAL_SETUP = "initial_setup", _("Initial Setup")
        CONFIGURATION_UPDATE = "config_update", _("Configuration Update")
        TROUBLESHOOTING = "troubleshooting", _("Troubleshooting")
        FEATURE_REQUEST = "feature_request", _("Feature Request")

    class StateChoices(models.TextChoices):
        STARTED = "started", _("Started")
        IN_PROGRESS = "in_progress", _("In Progress")
        GENERATING_RECOMMENDATIONS = "generating", _("Generating Recommendations")
        AWAITING_USER_APPROVAL = "awaiting_approval", _("Awaiting User Approval")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        ERROR = "error", _("Error")

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_sessions",
        verbose_name=_("User")
    )
    client = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="conversation_sessions",
        verbose_name=_("Client")
    )
    language = models.CharField(
        _("Language"),
        max_length=10,
        default="en",
        help_text="ISO language code for the conversation"
    )
    conversation_type = models.CharField(
        _("Conversation Type"),
        max_length=50,
        choices=ConversationTypeChoices.choices,
        default=ConversationTypeChoices.INITIAL_SETUP
    )
    context_data = models.JSONField(
        _("Context Data"),
        default=dict,
        blank=True,
        help_text="Initial context and environment data"
    )
    current_state = models.CharField(
        _("Current State"),
        max_length=50,
        choices=StateChoices.choices,
        default=StateChoices.STARTED
    )
    collected_data = models.JSONField(
        _("Collected Data"),
        default=dict,
        blank=True,
        help_text="Data collected during the conversation"
    )
    error_message = models.TextField(
        _("Error Message"),
        blank=True,
        null=True,
        help_text="Error details if session failed"
    )

    class Meta(BaseModel.Meta):
        db_table = "conversation_session"
        verbose_name = "Conversation Session"
        verbose_name_plural = "Conversation Sessions"
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return f"Session {self.session_id} - {self.user.email} ({self.conversation_type})"


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
        ConversationSession,
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
        help_text="Overall confidence score (0.0 to 1.0)"
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

    def __str__(self):
        return f"{self.document_title} - {self.source_organization}"


class UserFeedbackLearning(BaseModel, TenantAwareModel):
    """Captures user feedback for continuous learning and model improvement."""

    class FeedbackTypeChoices(models.TextChoices):
        RECOMMENDATION_QUALITY = "rec_quality", _("Recommendation Quality")
        CONVERSATION_FLOW = "conv_flow", _("Conversation Flow")
        ACCURACY = "accuracy", _("Accuracy")
        COMPLETENESS = "completeness", _("Completeness")
        USABILITY = "usability", _("Usability")
        OTHER = "other", _("Other")

    feedback_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recommendation = models.ForeignKey(
        LLMRecommendation,
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name=_("Recommendation")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_given",
        verbose_name=_("User")
    )
    client = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="feedback_received",
        verbose_name=_("Client")
    )
    feedback_type = models.CharField(
        _("Feedback Type"),
        max_length=50,
        choices=FeedbackTypeChoices.choices
    )
    feedback_data = models.JSONField(
        _("Feedback Data"),
        help_text="Structured feedback data"
    )
    learning_extracted = models.JSONField(
        _("Learning Extracted"),
        default=dict,
        blank=True,
        help_text="Learning patterns extracted from this feedback"
    )
    applied_to_model = models.BooleanField(
        _("Applied to Model"),
        default=False,
        help_text="Whether this feedback has been applied to improve the model"
    )

    class Meta(BaseModel.Meta):
        db_table = "user_feedback_learning"
        verbose_name = "User Feedback Learning"
        verbose_name_plural = "User Feedback Learning"
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return f"Feedback {self.feedback_id} - {self.feedback_type}"


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