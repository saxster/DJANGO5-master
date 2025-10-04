"""
Wisdom Conversation Translation Models

Database models for caching translated wisdom conversations with proper
quality assurance, version tracking, and performance optimization.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
from .wisdom_conversations import WisdomConversation


class WisdomConversationTranslation(TenantAwareModel, BaseModel):
    """
    Database cache for translated wisdom conversations.

    Stores high-quality translations with proper versioning, quality tracking,
    and performance optimization. Prevents repeated API calls for the same
    content and language combinations.
    """

    TRANSLATION_BACKENDS = [
        ('google', 'Google Translate'),
        ('azure', 'Azure Translator'),
        ('openai', 'OpenAI GPT Translation'),
        ('manual', 'Manual Translation'),
        ('hybrid', 'Hybrid (Multiple Backends)'),
    ]

    QUALITY_LEVELS = [
        ('unverified', 'Unverified (Auto-translated)'),
        ('reviewed', 'Reviewed by Human'),
        ('professional', 'Professional Translation'),
        ('native', 'Native Speaker Verified'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Translation Pending'),
        ('processing', 'Translation in Progress'),
        ('completed', 'Translation Completed'),
        ('failed', 'Translation Failed'),
        ('expired', 'Translation Cache Expired'),
    ]

    # Core relationship and content
    original_conversation = models.ForeignKey(
        WisdomConversation,
        on_delete=models.CASCADE,
        related_name='translations',
        help_text=_("Original English conversation being translated")
    )

    target_language = models.CharField(
        _("Target Language"),
        max_length=10,
        choices=[
            ('hi', 'हिन्दी (Hindi)'),
            ('te', 'తెలుగు (Telugu)'),
            ('es', 'Español (Spanish)'),
            ('fr', 'Français (French)'),
            ('ar', 'العربية (Arabic)'),
            ('zh', '中文 (Chinese)'),
        ],
        help_text=_("Language code for the translation")
    )

    translated_text = models.TextField(
        _("Translated Text"),
        help_text=_("Full translated conversation text")
    )

    warning_message = models.CharField(
        _("Translation Warning"),
        max_length=500,
        help_text=_("Localized warning message about translation quality")
    )

    # Translation metadata
    translation_backend = models.CharField(
        _("Translation Backend"),
        max_length=20,
        choices=TRANSLATION_BACKENDS,
        default='google',
        help_text=_("Service used for translation")
    )

    quality_level = models.CharField(
        _("Quality Level"),
        max_length=20,
        choices=QUALITY_LEVELS,
        default='unverified',
        help_text=_("Translation quality assessment")
    )

    status = models.CharField(
        _("Translation Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_("Current processing status")
    )

    # Quality metrics
    confidence_score = models.FloatField(
        _("Confidence Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text=_("AI confidence in translation quality (0.0-1.0)")
    )

    word_count_original = models.PositiveIntegerField(
        _("Original Word Count"),
        null=True,
        blank=True,
        help_text=_("Number of words in original text")
    )

    word_count_translated = models.PositiveIntegerField(
        _("Translated Word Count"),
        null=True,
        blank=True,
        help_text=_("Number of words in translated text")
    )

    # Performance tracking
    translation_time_ms = models.PositiveIntegerField(
        _("Translation Time (ms)"),
        null=True,
        blank=True,
        help_text=_("Time taken for translation in milliseconds")
    )

    cache_hit_count = models.PositiveIntegerField(
        _("Cache Hit Count"),
        default=0,
        help_text=_("Number of times this translation was served from cache")
    )

    last_accessed = models.DateTimeField(
        _("Last Accessed"),
        null=True,
        blank=True,
        help_text=_("When this translation was last retrieved")
    )

    # Versioning and expiry
    source_content_hash = models.CharField(
        _("Source Content Hash"),
        max_length=64,
        help_text=_("SHA-256 hash of original content for version tracking")
    )

    translation_version = models.CharField(
        _("Translation Version"),
        max_length=20,
        default='1.0',
        help_text=_("Version number for translation revisions")
    )

    expires_at = models.DateTimeField(
        _("Expires At"),
        null=True,
        blank=True,
        help_text=_("When this translation cache should expire")
    )

    # Quality assurance
    reviewed_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_translations',
        help_text=_("Person who reviewed this translation")
    )

    review_notes = models.TextField(
        _("Review Notes"),
        blank=True,
        help_text=_("Notes from human reviewers about translation quality")
    )

    # Error tracking
    error_message = models.TextField(
        _("Error Message"),
        blank=True,
        help_text=_("Error details if translation failed")
    )

    retry_count = models.PositiveSmallIntegerField(
        _("Retry Count"),
        default=0,
        help_text=_("Number of translation retry attempts")
    )

    class Meta:
        db_table = 'wellness_conversation_translation'
        verbose_name = _('Wisdom Conversation Translation')
        verbose_name_plural = _('Wisdom Conversation Translations')

        # Ensure unique translations per conversation-language pair
        unique_together = [
            ('original_conversation', 'target_language', 'translation_version')
        ]

        # Performance indexes
        indexes = [
            # Fast lookup by conversation and language
            models.Index(
                fields=['original_conversation', 'target_language'],
                name='wellness_conv_trans_lookup_idx'
            ),
            # Status and quality filtering
            models.Index(
                fields=['status', 'quality_level'],
                name='wellness_conv_trans_status_idx'
            ),
            # Cache management
            models.Index(
                fields=['last_accessed', 'expires_at'],
                name='wellness_conv_trans_cache_idx'
            ),
            # Performance monitoring
            models.Index(
                fields=['translation_backend', 'created_at'],
                name='wellness_conv_trans_perf_idx'
            ),
        ]

        # Default ordering by quality and recency
        ordering = ['-quality_level', '-created_at']

    def __str__(self):
        """String representation showing conversation and target language."""
        return f"Translation: {self.original_conversation.id} → {self.get_target_language_display()}"

    @property
    def is_expired(self):
        """Check if translation cache has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_high_quality(self):
        """Check if translation meets high quality standards."""
        return self.quality_level in ['reviewed', 'professional', 'native']

    @property
    def word_count_ratio(self):
        """Calculate word count ratio between original and translated text."""
        if not (self.word_count_original and self.word_count_translated):
            return None
        return self.word_count_translated / self.word_count_original

    def mark_accessed(self):
        """Update access tracking when translation is retrieved."""
        self.cache_hit_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['cache_hit_count', 'last_accessed'])

    def update_quality_level(self, new_level, reviewer=None, notes=""):
        """Update translation quality level with reviewer tracking."""
        self.quality_level = new_level
        if reviewer:
            self.reviewed_by = reviewer
        if notes:
            self.review_notes = notes
        self.save(update_fields=['quality_level', 'reviewed_by', 'review_notes'])

    def calculate_performance_metrics(self):
        """Calculate and return translation performance metrics."""
        return {
            'translation_speed': self.translation_time_ms,
            'cache_efficiency': self.cache_hit_count,
            'quality_score': self.confidence_score,
            'word_ratio': self.word_count_ratio,
            'backend_used': self.translation_backend,
            'is_expired': self.is_expired,
        }

    def get_display_info(self):
        """Get formatted display information for UI."""
        return {
            'language': self.get_target_language_display(),
            'quality': self.get_quality_level_display(),
            'backend': self.get_translation_backend_display(),
            'status': self.get_status_display(),
            'confidence': f"{(self.confidence_score or 0) * 100:.1f}%" if self.confidence_score else "N/A",
            'cache_hits': self.cache_hit_count,
            'last_used': self.last_accessed,
        }


class TranslationQualityFeedback(TenantAwareModel, BaseModel):
    """
    User feedback on translation quality for continuous improvement.

    Allows users to rate and provide feedback on translation quality,
    helping improve future translations through machine learning.
    """

    FEEDBACK_TYPES = [
        ('rating', 'Quality Rating'),
        ('correction', 'Text Correction'),
        ('complaint', 'Quality Complaint'),
        ('compliment', 'Quality Compliment'),
    ]

    QUALITY_RATINGS = [
        (1, 'Very Poor - Incomprehensible'),
        (2, 'Poor - Many Errors'),
        (3, 'Fair - Some Errors'),
        (4, 'Good - Minor Issues'),
        (5, 'Excellent - Perfect Translation'),
    ]

    translation = models.ForeignKey(
        WisdomConversationTranslation,
        on_delete=models.CASCADE,
        related_name='quality_feedback',
        help_text=_("Translation being rated")
    )

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='translation_feedback',
        help_text=_("User providing feedback")
    )

    feedback_type = models.CharField(
        _("Feedback Type"),
        max_length=20,
        choices=FEEDBACK_TYPES,
        help_text=_("Type of feedback provided")
    )

    quality_rating = models.PositiveSmallIntegerField(
        _("Quality Rating"),
        choices=QUALITY_RATINGS,
        null=True,
        blank=True,
        help_text=_("1-5 star rating of translation quality")
    )

    feedback_text = models.TextField(
        _("Feedback Text"),
        blank=True,
        help_text=_("Detailed feedback or suggested corrections")
    )

    suggested_translation = models.TextField(
        _("Suggested Translation"),
        blank=True,
        help_text=_("User's suggested improved translation")
    )

    is_helpful = models.BooleanField(
        _("Marked as Helpful"),
        default=False,
        help_text=_("Whether feedback was marked as helpful by administrators")
    )

    admin_response = models.TextField(
        _("Admin Response"),
        blank=True,
        help_text=_("Administrator response to feedback")
    )

    class Meta:
        db_table = 'wellness_translation_feedback'
        verbose_name = _('Translation Quality Feedback')
        verbose_name_plural = _('Translation Quality Feedback')

        # Prevent duplicate feedback from same user on same translation
        unique_together = [('translation', 'user')]

        indexes = [
            models.Index(fields=['quality_rating', 'created_at'], name='wellness_trans_feedback_rating_idx'),
            models.Index(fields=['feedback_type', 'is_helpful'], name='wellness_trans_feedback_type_idx'),
        ]

    def __str__(self):
        """String representation showing feedback type and rating."""
        rating_str = f" ({self.quality_rating}/5)" if self.quality_rating else ""
        return f"{self.get_feedback_type_display()}{rating_str} - {self.user.peoplename}"