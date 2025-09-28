"""
Wellness User Progress - Gamification and engagement tracking

This module implements user wellness education progress with:
- Streak tracking for engagement motivation
- Category-specific progress tracking
- Achievements and milestone rewards
- Engagement metrics for personalization

Complies with Rule #7 (Model Complexity Limits < 150 lines)
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenants.models import TenantAwareModel
import uuid
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class WellnessUserProgress(TenantAwareModel):
    """
    User wellness education progress and gamification

    Business logic delegated to apps.wellness.services.progress_tracker
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wellness_progress')

    # Engagement metrics
    current_streak_days = models.IntegerField(default=0, help_text="Current consecutive days of engagement")
    longest_streak_days = models.IntegerField(default=0, help_text="Personal best streak")
    total_content_viewed = models.IntegerField(default=0)
    total_content_completed = models.IntegerField(default=0)
    total_time_spent_minutes = models.IntegerField(default=0)

    # Category progress (JSON for flexibility)
    category_progress = models.JSONField(default=dict, encoder=DjangoJSONEncoder, help_text="Progress by category")
    category_preferences = models.JSONField(default=dict, help_text="User preferences by category")

    # Achievements and milestones
    achievements_earned = models.JSONField(default=list, help_text="List of achievement IDs earned")
    milestone_alerts_enabled = models.BooleanField(default=True)

    # Activity tracking
    last_activity_date = models.DateTimeField(null=True, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    personalization_profile = models.JSONField(default=dict, help_text="ML personalization data")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Wellness Progress"
        verbose_name_plural = "User Wellness Progress Records"
        indexes = [
            models.Index(fields=['user', 'current_streak_days']),
            models.Index(fields=['tenant', 'last_activity_date']),
        ]

    def __str__(self):
        return f"{self.user.peoplename} - {self.current_streak_days} day streak"

    def update_streak(self):
        """Update engagement streak - business logic in service layer"""
        from apps.wellness.services.progress_tracker import ProgressTracker
        return ProgressTracker.update_user_streak(self)

    def add_progress_for_category(self, category, points):
        """Add progress points - business logic in service layer"""
        from apps.wellness.services.progress_tracker import ProgressTracker
        return ProgressTracker.add_category_progress(self, category, points)

    def check_and_award_achievements(self):
        """Check and award new achievements - business logic in service layer"""
        from apps.wellness.services.achievements import AchievementService
        return AchievementService.check_achievements(self)

    @property
    def is_recently_active(self):
        if not self.last_activity_date:
            return False
        return (timezone.now().date() - self.last_activity_date.date()).days <= 7