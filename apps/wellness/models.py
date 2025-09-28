"""
Wellness Education Models - Complete implementation from specification

This module implements the evidence-based wellness education system with:
- WHO/CDC compliant content curation and delivery
- ML-powered personalization and contextual delivery
- Gamification with progress tracking and achievements
- Evidence-based wellness practices and interventions
- Integration with journal system for pattern-based delivery
- Multi-tenant support for enterprise deployment
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenants.models import TenantAwareModel
import uuid
import logging

User = get_user_model()  # Will use People model
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


class WellnessUserProgress(TenantAwareModel):
    """
    User wellness education progress and gamification

    Features:
    - Streak tracking for engagement motivation
    - Category-specific progress tracking
    - Learning metrics and time investment
    - Achievement system for milestones
    - Preference management for personalization
    - Gamification elements for sustained engagement
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wellness_progress',
        help_text="User this progress belongs to"
    )

    # Streak tracking (gamification)
    current_streak = models.IntegerField(
        default=0,
        help_text="Current consecutive days of wellness engagement"
    )
    longest_streak = models.IntegerField(
        default=0,
        help_text="Longest streak ever achieved"
    )
    last_activity_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last date user engaged with wellness content"
    )

    # Learning metrics
    total_content_viewed = models.IntegerField(
        default=0,
        help_text="Total number of content items viewed"
    )
    total_content_completed = models.IntegerField(
        default=0,
        help_text="Total number of content items fully completed"
    )
    total_time_spent_minutes = models.IntegerField(
        default=0,
        help_text="Total time spent consuming wellness content"
    )
    total_score = models.IntegerField(
        default=0,
        help_text="Cumulative engagement score"
    )

    # Category-specific progress (matches WellnessContentCategory choices)
    mental_health_progress = models.IntegerField(
        default=0,
        help_text="Progress score for mental health content"
    )
    physical_wellness_progress = models.IntegerField(
        default=0,
        help_text="Progress score for physical wellness content"
    )
    workplace_health_progress = models.IntegerField(
        default=0,
        help_text="Progress score for workplace health content"
    )
    substance_awareness_progress = models.IntegerField(
        default=0,
        help_text="Progress score for substance awareness content"
    )
    preventive_care_progress = models.IntegerField(
        default=0,
        help_text="Progress score for preventive care content"
    )

    # User preferences for personalization
    preferred_content_level = models.CharField(
        max_length=20,
        choices=WellnessContentLevel.choices,
        default=WellnessContentLevel.SHORT_READ,
        help_text="Preferred content complexity level"
    )
    preferred_delivery_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Preferred time of day for content delivery"
    )
    enabled_categories = models.JSONField(
        default=list,
        help_text="Wellness categories user wants to receive content for"
    )
    daily_tip_enabled = models.BooleanField(
        default=True,
        help_text="Whether user wants daily wellness tips"
    )
    contextual_delivery_enabled = models.BooleanField(
        default=True,
        help_text="Whether to deliver content based on journal patterns"
    )

    # Achievements and gamification
    achievements_earned = models.JSONField(
        default=list,
        help_text="List of achievement IDs/names earned by user"
    )
    milestone_alerts_enabled = models.BooleanField(
        default=True,
        help_text="Whether to notify user of milestones and achievements"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Wellness Progress"
        verbose_name_plural = "User Wellness Progress"

        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['current_streak']),
            models.Index(fields=['last_activity_date']),
            models.Index(fields=['tenant']),
        ]

    def __str__(self):
        return f"Progress - {self.user.peoplename} (Streak: {self.current_streak})"

    def update_streak(self):
        """Update user's engagement streak based on activity"""
        today = timezone.now().date()

        if not self.last_activity_date:
            # First activity
            self.current_streak = 1
            self.last_activity_date = timezone.now()
        else:
            last_activity_date = self.last_activity_date.date()
            days_since_activity = (today - last_activity_date).days

            if days_since_activity == 0:
                # Already active today, no change
                pass
            elif days_since_activity == 1:
                # Consecutive day, extend streak
                self.current_streak += 1
                self.last_activity_date = timezone.now()
            else:
                # Streak broken, reset
                self.current_streak = 1
                self.last_activity_date = timezone.now()

        # Update longest streak if current streak is longer
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak

    def add_progress_for_category(self, category, points=1):
        """Add progress points for a specific wellness category"""
        category_field_map = {
            'mental_health': 'mental_health_progress',
            'physical_wellness': 'physical_wellness_progress',
            'workplace_health': 'workplace_health_progress',
            'substance_awareness': 'substance_awareness_progress',
            'preventive_care': 'preventive_care_progress',
        }

        field_name = category_field_map.get(category)
        if field_name:
            current_value = getattr(self, field_name, 0)
            setattr(self, field_name, current_value + points)
            self.total_score += points

    def check_and_award_achievements(self):
        """Check for new achievements and award them"""
        new_achievements = []

        # Streak achievements
        if self.current_streak >= 7 and 'week_streak' not in self.achievements_earned:
            new_achievements.append('week_streak')

        if self.current_streak >= 30 and 'month_streak' not in self.achievements_earned:
            new_achievements.append('month_streak')

        # Content consumption achievements
        if self.total_content_viewed >= 10 and 'content_explorer' not in self.achievements_earned:
            new_achievements.append('content_explorer')

        if self.total_content_viewed >= 50 and 'wellness_scholar' not in self.achievements_earned:
            new_achievements.append('wellness_scholar')

        # Add new achievements
        if new_achievements:
            self.achievements_earned.extend(new_achievements)
            logger.info(f"New achievements for {self.user.peoplename}: {new_achievements}")

        return new_achievements

    @property
    def completion_rate(self):
        """Calculate content completion rate"""
        if self.total_content_viewed == 0:
            return 0.0
        return self.total_content_completed / self.total_content_viewed

    @property
    def is_active_user(self):
        """Check if user is recently active (within 7 days)"""
        if not self.last_activity_date:
            return False
        return (timezone.now().date() - self.last_activity_date.date()).days <= 7


class WellnessContentInteraction(models.Model):
    """
    Detailed tracking of user engagement with wellness content

    Features:
    - Comprehensive interaction tracking (viewed, completed, rated, etc.)
    - Context capture for effectiveness analysis
    - User feedback and rating system
    - Delivery context tracking for optimization
    - Journal entry correlation for pattern analysis
    - Engagement metrics for ML personalization
    """

    INTERACTION_TYPES = [
        ('viewed', 'Viewed'),
        ('completed', 'Completed Reading'),
        ('bookmarked', 'Bookmarked'),
        ('shared', 'Shared'),
        ('dismissed', 'Dismissed'),
        ('rated', 'Rated'),
        ('acted_upon', 'Took Action'),
        ('requested_more', 'Requested More Info'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wellness_interactions',
        help_text="User who interacted with content"
    )
    content = models.ForeignKey(
        WellnessContent,
        on_delete=models.CASCADE,
        related_name='interactions',
        help_text="Content that was interacted with"
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES,
        help_text="Type of interaction performed"
    )
    delivery_context = models.CharField(
        max_length=50,
        choices=WellnessDeliveryContext.choices,
        help_text="Context in which content was delivered"
    )

    # Engagement metrics
    time_spent_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time spent engaging with content"
    )
    completion_percentage = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of content consumed (0-100)"
    )
    user_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User rating of content (1-5 stars)"
    )
    user_feedback = models.TextField(
        blank=True,
        help_text="Optional user feedback or comments"
    )
    action_taken = models.BooleanField(
        default=False,
        help_text="Whether user indicated they took recommended action"
    )

    # Context when content was delivered (CRITICAL for effectiveness analysis)
    trigger_journal_entry = models.ForeignKey(
        'journal.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_wellness_content',
        help_text="Journal entry that triggered this content delivery"
    )
    user_mood_at_delivery = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="User's mood rating when content was delivered"
    )
    user_stress_at_delivery = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User's stress level when content was delivered"
    )

    interaction_date = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text="Additional context and metadata"
    )

    class Meta:
        verbose_name = "Wellness Content Interaction"
        verbose_name_plural = "Wellness Content Interactions"
        ordering = ['-interaction_date']

        indexes = [
            models.Index(fields=['user', 'interaction_date']),
            models.Index(fields=['content', 'interaction_type']),
            models.Index(fields=['trigger_journal_entry']),
            models.Index(fields=['delivery_context']),
            models.Index(fields=['interaction_type']),
            models.Index(fields=['user_rating']),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(completion_percentage__gte=0, completion_percentage__lte=100) | models.Q(completion_percentage__isnull=True),
                name='valid_completion_percentage'
            ),
            models.CheckConstraint(
                check=models.Q(user_rating__gte=1, user_rating__lte=5) | models.Q(user_rating__isnull=True),
                name='valid_user_rating'
            ),
        ]

    def __str__(self):
        return f"{self.user.peoplename} {self.interaction_type} '{self.content.title}'"

    def save(self, *args, **kwargs):
        """Handle automatic engagement scoring and progress updates"""
        super().save(*args, **kwargs)

        # Update user progress based on interaction
        if hasattr(self.user, 'wellness_progress'):
            progress = self.user.wellness_progress

            if self.interaction_type == 'viewed':
                progress.total_content_viewed += 1
                if self.time_spent_seconds:
                    progress.total_time_spent_minutes += max(1, self.time_spent_seconds // 60)

            elif self.interaction_type == 'completed':
                progress.total_content_completed += 1
                progress.add_progress_for_category(self.content.category, 2)

            elif self.interaction_type == 'acted_upon':
                progress.add_progress_for_category(self.content.category, 5)

            # Update streak and check achievements
            progress.update_streak()
            new_achievements = progress.check_and_award_achievements()

            progress.save()

            # Log new achievements
            if new_achievements and progress.milestone_alerts_enabled:
                logger.info(f"User {self.user.peoplename} earned achievements: {new_achievements}")

    @property
    def is_positive_interaction(self):
        """Check if this represents a positive user interaction"""
        positive_types = ['viewed', 'completed', 'bookmarked', 'rated', 'acted_upon', 'requested_more']
        return self.interaction_type in positive_types

    @property
    def engagement_score(self):
        """Calculate engagement score for this interaction"""
        base_scores = {
            'viewed': 1,
            'completed': 3,
            'bookmarked': 2,
            'shared': 4,
            'dismissed': -1,
            'rated': 2,
            'acted_upon': 5,
            'requested_more': 3,
        }

        score = base_scores.get(self.interaction_type, 0)

        # Bonus for rating
        if self.user_rating and self.user_rating >= 4:
            score += 1

        # Bonus for high completion
        if self.completion_percentage and self.completion_percentage >= 80:
            score += 1

        return score