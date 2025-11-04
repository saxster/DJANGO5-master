"""
Wellness User Progress Model

User wellness education progress and gamification.
Extracted from monolithic models.py (697 lines → focused modules).

Features:
- Streak tracking for engagement motivation
- Category-specific progress tracking
- Learning metrics and time investment
- Achievement system for milestones
- Preference management for personalization
- Gamification elements for sustained engagement

Related: Ultrathink Code Review Phase 3 - ARCH-001
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from .enums import WellnessContentLevel
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


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


__all__ = ['WellnessUserProgress']
