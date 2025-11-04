"""
Wellness Content Model

Evidence-based wellness education content with intelligent delivery.
Extracted from monolithic models.py (697 lines → focused modules).

Features:
- WHO/CDC compliant content with citations and evidence levels
- Smart targeting based on user patterns and context
- Multi-format content support (text, video, interactive)
- Workplace-specific adaptations for field workers
- Pattern-based triggering for contextual delivery
- Evidence tracking for medical compliance

Related: Ultrathink Code Review Phase 3 - ARCH-001
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenants.models import TenantAwareModel
from .enums import (
    WellnessContentCategory,
    WellnessDeliveryContext,
    WellnessContentLevel,
    EvidenceLevel,
)
import uuid

User = get_user_model()


class WellnessContent(TenantAwareModel):
    """
    Evidence-based wellness education content with intelligent delivery

    Features:
    - WHO/CDC compliant content with citations and evidence levels
    - Smart targeting based on user patterns and context
    - Multi-format content support (text, video, interactive)
    - Workplace-specific adaptations for field workers
    - Pattern-based triggering for contextual delivery
    - Evidence tracking for medical compliance
    """

    # Content identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(
        max_length=200,
        help_text="Content title - clear and actionable"
    )
    summary = models.TextField(
        max_length=500,
        help_text="Brief summary for quick scanning"
    )
    content = models.TextField(
        help_text="Main educational content"
    )

    # Classification and targeting
    category = models.CharField(
        max_length=50,
        choices=WellnessContentCategory.choices,
        help_text="Primary wellness category"
    )
    delivery_context = models.CharField(
        max_length=50,
        choices=WellnessDeliveryContext.choices,
        help_text="When/how this content should be delivered"
    )
    content_level = models.CharField(
        max_length=20,
        choices=WellnessContentLevel.choices,
        help_text="Content complexity and time requirement"
    )
    evidence_level = models.CharField(
        max_length=30,
        choices=EvidenceLevel.choices,
        help_text="Quality of evidence backing this content"
    )

    # Smart targeting and pattern matching
    tags = models.JSONField(
        default=list,
        help_text="Tags for pattern matching with journal entries"
    )
    trigger_patterns = models.JSONField(
        default=dict,
        help_text="Complex trigger conditions for content delivery",
        encoder=DjangoJSONEncoder
    )
    workplace_specific = models.BooleanField(
        default=False,
        help_text="Content specifically adapted for workplace contexts"
    )
    field_worker_relevant = models.BooleanField(
        default=False,
        help_text="Relevant for field workers and mobile contexts"
    )

    # Educational content structure
    action_tips = models.JSONField(
        default=list,
        help_text="Concrete, actionable advice points"
    )
    key_takeaways = models.JSONField(
        default=list,
        help_text="Key learning points and insights"
    )
    related_topics = models.JSONField(
        default=list,
        help_text="IDs of related content for progressive learning"
    )

    # Evidence and credibility (CRITICAL for medical compliance)
    source_name = models.CharField(
        max_length=100,
        help_text="Source organization (WHO, CDC, Mayo Clinic, etc.)"
    )
    source_url = models.URLField(
        blank=True,
        null=True,
        help_text="Original source URL for verification"
    )
    evidence_summary = models.TextField(
        blank=True,
        help_text="Summary of evidence backing this content"
    )
    citations = models.JSONField(
        default=list,
        help_text="Academic citations and references"
    )
    last_verified_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time content accuracy was verified"
    )

    # Content management
    is_active = models.BooleanField(
        default=True,
        help_text="Whether content is available for delivery"
    )
    priority_score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Priority for content selection (1-100, higher = more likely to show)"
    )
    seasonal_relevance = models.JSONField(
        default=list,
        help_text="Months when content is most relevant (1-12)"
    )
    frequency_limit_days = models.IntegerField(
        default=0,
        help_text="Minimum days between showings to same user"
    )

    # Publishing and versioning metadata
    estimated_reading_time = models.IntegerField(
        help_text="Estimated reading/consumption time in minutes"
    )
    complexity_score = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Content complexity/reading difficulty (1-5)"
    )
    content_version = models.CharField(
        max_length=10,
        default='1.0',
        help_text="Version for content updates and tracking"
    )

    # Multi-tenancy and audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text="Content creator/editor"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wellness Content"
        verbose_name_plural = "Wellness Content Items"
        ordering = ['-priority_score', '-created_at']

        indexes = [
            models.Index(fields=['category', 'delivery_context']),
            models.Index(fields=['is_active', 'priority_score']),
            models.Index(fields=['workplace_specific', 'field_worker_relevant']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['evidence_level']),
            models.Index(fields=['tags']),  # GIN index for JSON field
            models.Index(fields=['created_at']),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(priority_score__gte=1, priority_score__lte=100),
                name='valid_wellness_priority_score'
            ),
            models.CheckConstraint(
                check=models.Q(complexity_score__gte=1, complexity_score__lte=5),
                name='valid_wellness_complexity_score'
            ),
            models.CheckConstraint(
                check=models.Q(estimated_reading_time__gte=1),
                name='valid_reading_time'
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"

    def save(self, *args, **kwargs):
        """Handle automatic fields and validation"""
        if not self.last_verified_date:
            self.last_verified_date = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_high_evidence(self):
        """Check if content has high-quality evidence backing"""
        return self.evidence_level in ['who_cdc', 'peer_reviewed']

    @property
    def needs_verification(self):
        """Check if content needs evidence verification (older than 6 months)"""
        if not self.last_verified_date:
            return True
        return (timezone.now() - self.last_verified_date).days > 180

    def is_relevant_for_season(self):
        """Check if content is relevant for current season"""
        if not self.seasonal_relevance:
            return True  # No seasonal restrictions
        current_month = timezone.now().month
        return current_month in self.seasonal_relevance

    def can_be_shown_to_user(self, user, last_shown_date=None):
        """Check if content can be shown to user based on frequency limits"""
        if not self.is_active:
            return False

        if self.frequency_limit_days == 0:
            return True  # No frequency restrictions

        if not last_shown_date:
            return True  # Never shown before

        days_since_shown = (timezone.now().date() - last_shown_date).days
        return days_since_shown >= self.frequency_limit_days


__all__ = ['WellnessContent']
