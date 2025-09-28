"""
Wellness Content Models - WHO/CDC compliant educational content

This module implements evidence-based wellness education content with:
- Multi-category health education (mental, physical, workplace)
- Evidence-level tracking for medical compliance
- Smart targeting and delivery context
- Workplace-specific adaptations
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenants.models import TenantAwareModel
import uuid
import logging

logger = logging.getLogger(__name__)


class WellnessContentCategory(models.TextChoices):
    """Wellness content categories for comprehensive health education"""
    MENTAL_HEALTH = 'mental_health', 'Mental Health'
    PHYSICAL_WELLNESS = 'physical_wellness', 'Physical Wellness'
    WORKPLACE_HEALTH = 'workplace_health', 'Workplace Health'
    SUBSTANCE_AWARENESS = 'substance_awareness', 'Substance Awareness'
    PREVENTIVE_CARE = 'preventive_care', 'Preventive Care'
    SLEEP_HYGIENE = 'sleep_hygiene', 'Sleep Hygiene'
    NUTRITION_BASICS = 'nutrition_basics', 'Nutrition Basics'
    STRESS_MANAGEMENT = 'stress_management', 'Stress Management'
    PHYSICAL_ACTIVITY = 'physical_activity', 'Physical Activity'
    MINDFULNESS = 'mindfulness', 'Mindfulness'


class WellnessDeliveryContext(models.TextChoices):
    """Context-based delivery triggers for intelligent content serving"""
    DAILY_TIP = 'daily_tip', 'Daily Wellness Tip'
    PATTERN_TRIGGERED = 'pattern_triggered', 'Pattern-Based Delivery'
    STRESS_RESPONSE = 'stress_response', 'High Stress Response'
    MOOD_SUPPORT = 'mood_support', 'Low Mood Support'
    ENERGY_BOOST = 'energy_boost', 'Low Energy Response'
    SHIFT_TRANSITION = 'shift_transition', 'Shift Start/End'
    STREAK_MILESTONE = 'streak_milestone', 'Milestone Reward'
    SEASONAL = 'seasonal', 'Seasonal Health'
    WORKPLACE_SPECIFIC = 'workplace_specific', 'Workplace Guidance'
    GRATITUDE_ENHANCEMENT = 'gratitude_enhancement', 'Positive Psychology Reinforcement'


class WellnessContentLevel(models.TextChoices):
    """Content complexity and time investment levels"""
    QUICK_TIP = 'quick_tip', 'Quick Tip (1 min)'
    SHORT_READ = 'short_read', 'Short Read (3 min)'
    DEEP_DIVE = 'deep_dive', 'Deep Dive (7 min)'
    INTERACTIVE = 'interactive', 'Interactive (5 min)'
    VIDEO_CONTENT = 'video_content', 'Video Content (4 min)'


class EvidenceLevel(models.TextChoices):
    """Evidence quality levels for medical/health compliance"""
    WHO_CDC_GUIDELINE = 'who_cdc', 'WHO/CDC Guideline'
    PEER_REVIEWED_RESEARCH = 'peer_reviewed', 'Peer-Reviewed Research'
    PROFESSIONAL_CONSENSUS = 'professional', 'Professional Consensus'
    ESTABLISHED_PRACTICE = 'established', 'Established Practice'
    EDUCATIONAL_CONTENT = 'educational', 'General Education'


class WellnessContent(TenantAwareModel):
    """
    Evidence-based wellness education content with intelligent delivery

    Complies with Rule #7 (Model Complexity Limits) - Core content model only
    Business logic delegated to apps.wellness.services.content_delivery
    """

    from django.contrib.auth import get_user_model
    from django.core.serializers.json import DjangoJSONEncoder
    User = get_user_model()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=200, help_text="Content title - clear and actionable")
    summary = models.TextField(max_length=500, help_text="Brief summary for quick scanning")
    content = models.TextField(help_text="Main educational content")

    category = models.CharField(max_length=50, choices=WellnessContentCategory.choices, help_text="Primary wellness category")
    delivery_context = models.CharField(max_length=50, choices=WellnessDeliveryContext.choices, help_text="When/how this content should be delivered")
    content_level = models.CharField(max_length=20, choices=WellnessContentLevel.choices, help_text="Content complexity and time requirement")
    evidence_level = models.CharField(max_length=30, choices=EvidenceLevel.choices, help_text="Quality of evidence backing this content")

    tags = models.JSONField(default=list, help_text="Tags for pattern matching with journal entries")
    trigger_patterns = models.JSONField(default=dict, help_text="Complex trigger conditions for content delivery", encoder=DjangoJSONEncoder)
    workplace_specific = models.BooleanField(default=False, help_text="Content specifically adapted for workplace contexts")
    field_worker_relevant = models.BooleanField(default=False, help_text="Relevant for field workers and mobile contexts")

    action_tips = models.JSONField(default=list, help_text="Concrete, actionable advice points")
    key_takeaways = models.JSONField(default=list, help_text="Key learning points and insights")
    related_topics = models.JSONField(default=list, help_text="IDs of related content for progressive learning")

    source_name = models.CharField(max_length=100, help_text="Source organization (WHO, CDC, Mayo Clinic, etc.)")
    source_url = models.URLField(blank=True, null=True, help_text="Original source URL for verification")
    evidence_summary = models.TextField(blank=True, help_text="Summary of evidence backing this content")
    citations = models.JSONField(default=list, help_text="Academic citations and references")
    last_verified_date = models.DateTimeField(null=True, blank=True, help_text="Last time content accuracy was verified")

    is_active = models.BooleanField(default=True, help_text="Whether content is available for delivery")
    priority_score = models.IntegerField(default=50, validators=[MinValueValidator(1), MaxValueValidator(100)])
    seasonal_relevance = models.JSONField(default=list, help_text="Months when content is most relevant (1-12)")
    frequency_limit_days = models.IntegerField(default=0, help_text="Minimum days between showings to same user")

    estimated_reading_time = models.IntegerField(help_text="Estimated reading/consumption time in minutes")
    complexity_score = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    content_version = models.CharField(max_length=10, default='1.0', help_text="Version for content updates and tracking")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, help_text="Content creator/editor")
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
            models.Index(fields=['tags']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(priority_score__gte=1, priority_score__lte=100), name='valid_wellness_priority_score'),
            models.CheckConstraint(check=models.Q(complexity_score__gte=1, complexity_score__lte=5), name='valid_wellness_complexity_score'),
            models.CheckConstraint(check=models.Q(estimated_reading_time__gte=1), name='valid_reading_time'),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"

    def save(self, *args, **kwargs):
        if not self.last_verified_date:
            self.last_verified_date = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_high_evidence(self):
        return self.evidence_level in ['who_cdc', 'peer_reviewed']

    @property
    def needs_verification(self):
        if not self.last_verified_date:
            return True
        return (timezone.now() - self.last_verified_date).days > 180

    def is_relevant_for_season(self):
        if not self.seasonal_relevance:
            return True
        current_month = timezone.now().month
        return current_month in self.seasonal_relevance

    def can_be_shown_to_user(self, user, last_shown_date=None):
        if not self.is_active:
            return False
        if self.frequency_limit_days == 0:
            return True
        if not last_shown_date:
            return True
        days_since_shown = (timezone.now().date() - last_shown_date).days
        return days_since_shown >= self.frequency_limit_days