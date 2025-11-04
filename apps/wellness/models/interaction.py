"""
Wellness Content Interaction Model

Detailed tracking of user engagement with wellness content.
Extracted from monolithic models.py (697 lines → focused modules).

Features:
- Comprehensive interaction tracking (viewed, completed, rated, etc.)
- Context capture for effectiveness analysis
- User feedback and rating system
- Delivery context tracking for optimization
- Journal entry correlation for pattern analysis
- Engagement metrics for ML personalization

Related: Ultrathink Code Review Phase 3 - ARCH-001
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from .enums import WellnessDeliveryContext
import uuid
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


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
        'wellness.WellnessContent',
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


__all__ = ['WellnessContentInteraction']
