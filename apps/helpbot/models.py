"""
AI HelpBot Models

Extends existing conversational AI infrastructure to provide intelligent help and support.
Integrates with txtai, semantic search, and existing knowledge management systems.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


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
        "onboarding.Bt",
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
        HelpBotSession,
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


class HelpBotKnowledge(BaseModel, TenantAwareModel):
    """
    HelpBot-specific knowledge base entries.
    Extends existing AuthoritativeKnowledge with HelpBot-specific features.
    """

    class KnowledgeTypeChoices(models.TextChoices):
        DOCUMENTATION = "documentation", _("Documentation")
        FAQ = "faq", _("FAQ")
        TUTORIAL = "tutorial", _("Tutorial")
        API_REFERENCE = "api_reference", _("API Reference")
        TROUBLESHOOTING = "troubleshooting", _("Troubleshooting")
        FEATURE_GUIDE = "feature_guide", _("Feature Guide")
        ERROR_SOLUTION = "error_solution", _("Error Solution")

    class CategoryChoices(models.TextChoices):
        OPERATIONS = "operations", _("Operations")
        ASSETS = "assets", _("Assets")
        PEOPLE = "people", _("People")
        HELPDESK = "helpdesk", _("Help Desk")
        REPORTS = "reports", _("Reports")
        ADMINISTRATION = "administration", _("Administration")
        TECHNICAL = "technical", _("Technical")
        GENERAL = "general", _("General")

    knowledge_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(
        _("Title"),
        max_length=500,
        help_text="Human-readable title for this knowledge entry"
    )
    content = models.TextField(
        _("Content"),
        help_text="The actual help content (markdown supported)"
    )
    knowledge_type = models.CharField(
        _("Knowledge Type"),
        max_length=30,
        choices=KnowledgeTypeChoices.choices,
        default=KnowledgeTypeChoices.DOCUMENTATION
    )
    category = models.CharField(
        _("Category"),
        max_length=30,
        choices=CategoryChoices.choices,
        default=CategoryChoices.GENERAL
    )
    tags = ArrayField(
        models.CharField(max_length=50),
        verbose_name=_("Tags"),
        default=list,
        blank=True,
        help_text="Search tags and keywords"
    )
    related_urls = ArrayField(
        models.URLField(max_length=500),
        verbose_name=_("Related URLs"),
        default=list,
        blank=True,
        help_text="Related application URLs or external links"
    )
    search_keywords = ArrayField(
        models.CharField(max_length=100),
        verbose_name=_("Search Keywords"),
        default=list,
        blank=True,
        help_text="Keywords that should trigger this knowledge"
    )
    embedding_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Embedding Vector"),
        null=True,
        blank=True,
        help_text="Vector embedding for semantic search"
    )
    usage_count = models.IntegerField(
        _("Usage Count"),
        default=0,
        help_text="Number of times this knowledge has been accessed"
    )
    effectiveness_score = models.FloatField(
        _("Effectiveness Score"),
        default=0.5,
        help_text="How effective this knowledge is based on user feedback (0.0 to 1.0)"
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text="Whether this knowledge entry is active and searchable"
    )
    source_file = models.CharField(
        _("Source File"),
        max_length=500,
        blank=True,
        null=True,
        help_text="Original file path if imported from documentation"
    )
    last_updated = models.DateTimeField(
        _("Last Updated"),
        auto_now=True,
        help_text="When this knowledge was last updated"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_knowledge"
        verbose_name = "HelpBot Knowledge"
        verbose_name_plural = "HelpBot Knowledge"
        get_latest_by = ["last_updated", "mdtz"]
        indexes = [
            models.Index(fields=['category', 'knowledge_type'], name='helpbot_knowledge_cat_type_idx'),
            models.Index(fields=['is_active', 'effectiveness_score'], name='helpbot_knowledge_active_score_idx'),
            models.Index(fields=['usage_count'], name='helpbot_knowledge_usage_idx'),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"


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
        HelpBotSession,
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name=_("Session")
    )
    message = models.ForeignKey(
        HelpBotMessage,
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
            models.Index(fields=['session', 'feedback_type'], name='helpbot_feedback_session_type_idx'),
            models.Index(fields=['is_processed', 'cdtz'], name='helpbot_feedback_processed_idx'),
        ]

    def __str__(self):
        return f"Feedback {self.feedback_id} - {self.feedback_type} ({self.rating}/5)"


class HelpBotContext(BaseModel, TenantAwareModel):
    """
    Stores contextual information about user's current location and state in the application.
    This enables context-aware help and suggestions.
    """

    context_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="helpbot_contexts",
        verbose_name=_("User")
    )
    session = models.ForeignKey(
        HelpBotSession,
        on_delete=models.CASCADE,
        related_name="contexts",
        verbose_name=_("Session"),
        null=True,
        blank=True
    )
    current_url = models.URLField(
        _("Current URL"),
        help_text="URL where user is seeking help"
    )
    page_title = models.CharField(
        _("Page Title"),
        max_length=200,
        blank=True,
        help_text="Title of the current page"
    )
    app_name = models.CharField(
        _("App Name"),
        max_length=50,
        blank=True,
        help_text="Django app name (e.g., 'activity', 'peoples')"
    )
    view_name = models.CharField(
        _("View Name"),
        max_length=100,
        blank=True,
        help_text="Django view name"
    )
    user_role = models.CharField(
        _("User Role"),
        max_length=50,
        blank=True,
        help_text="User's role/permission level"
    )
    form_data = models.JSONField(
        _("Form Data"),
        default=dict,
        blank=True,
        help_text="Current form data if user is on a form"
    )
    error_context = models.JSONField(
        _("Error Context"),
        default=dict,
        blank=True,
        help_text="Error information if user encountered an error"
    )
    user_journey = models.JSONField(
        _("User Journey"),
        default=list,
        blank=True,
        help_text="Recent pages visited by the user"
    )
    browser_info = models.JSONField(
        _("Browser Info"),
        default=dict,
        blank=True,
        help_text="Browser and device information"
    )
    timestamp = models.DateTimeField(
        _("Timestamp"),
        auto_now=True,
        help_text="When this context was captured"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_context"
        verbose_name = "HelpBot Context"
        verbose_name_plural = "HelpBot Contexts"
        get_latest_by = ["timestamp"]
        indexes = [
            models.Index(fields=['user', 'timestamp'], name='helpbot_context_user_time_idx'),
            models.Index(fields=['app_name', 'view_name'], name='helpbot_context_app_view_idx'),
        ]

    def __str__(self):
        return f"Context {self.context_id} - {self.user.email} at {self.current_url}"


class HelpBotAnalytics(BaseModel, TenantAwareModel):
    """
    Analytics and metrics for HelpBot usage and performance.
    Used for monitoring and continuous improvement.
    """

    class MetricTypeChoices(models.TextChoices):
        SESSION_COUNT = "session_count", _("Session Count")
        MESSAGE_COUNT = "message_count", _("Message Count")
        RESPONSE_TIME = "response_time", _("Response Time")
        USER_SATISFACTION = "user_satisfaction", _("User Satisfaction")
        KNOWLEDGE_USAGE = "knowledge_usage", _("Knowledge Usage")
        ERROR_RATE = "error_rate", _("Error Rate")

    analytics_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    metric_type = models.CharField(
        _("Metric Type"),
        max_length=30,
        choices=MetricTypeChoices.choices
    )
    value = models.FloatField(
        _("Value"),
        help_text="Numeric value of the metric"
    )
    dimension_data = models.JSONField(
        _("Dimension Data"),
        default=dict,
        blank=True,
        help_text="Breakdown dimensions (e.g., by category, user type, time period)"
    )
    date = models.DateField(
        _("Date"),
        default=timezone.now,
        help_text="Date for this metric"
    )
    hour = models.IntegerField(
        _("Hour"),
        null=True,
        blank=True,
        help_text="Hour of day (0-23) for hourly metrics"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_analytics"
        verbose_name = "HelpBot Analytics"
        verbose_name_plural = "HelpBot Analytics"
        get_latest_by = ["date", "cdtz"]
        indexes = [
            models.Index(fields=['metric_type', 'date'], name='helpbot_analytics_metric_date_idx'),
            models.Index(fields=['date', 'hour'], name='helpbot_analytics_date_hour_idx'),
        ]
        unique_together = [
            ('metric_type', 'date', 'hour')
        ]

    def __str__(self):
        return f"{self.metric_type}: {self.value} on {self.date}"