"""
Gamification Models for Help Center.

Implements badges, points, and leaderboards to boost user engagement.

Based on 2025 research:
- 83% motivation increase with gamification (TalentLMS 2024)
- 100-150% engagement boost vs traditional recognition
- 60% faster content updates with community contributions

Models (all < 150 lines):
1. HelpBadge - Badge definitions with criteria
2. HelpUserBadge - User-earned badges
3. HelpUserPoints - Points accumulation

Following CLAUDE.md Rule #7: Each model <150 lines
"""

from django.db import models
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import People


class HelpBadge(TenantAwareModel):
    """
    Badge definitions with earning criteria.

    Badges are awarded automatically when users meet criteria.

    Examples:
    - "First Feedback" - Submit first article vote
    - "Helpful Reviewer" - 10+ helpful votes
    - "Content Contributor" - Suggest 3+ articles
    - "Power User" - 50+ article views
    """

    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(max_length=500)

    icon = models.CharField(
        max_length=50,
        help_text="Icon/emoji (e.g., '🏆', '⭐', '🎖️')"
    )

    color = models.CharField(
        max_length=7,
        default='#ffd700',
        help_text="Hex color for badge display"
    )

    criteria = models.JSONField(
        help_text="""
        Earning criteria as JSON. Examples:
        {"feedback_count": 10} - 10 feedback submissions
        {"article_suggestions": 3} - 3 article suggestions
        {"helpful_votes": 50} - 50 helpful votes given
        """
    )

    points_awarded = models.IntegerField(
        default=10,
        help_text="Points awarded when badge is earned"
    )

    rarity = models.CharField(
        max_length=20,
        choices=[
            ('COMMON', 'Common'),
            ('RARE', 'Rare'),
            ('EPIC', 'Epic'),
            ('LEGENDARY', 'Legendary')
        ],
        default='COMMON',
        db_index=True
    )

    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'help_center_badge'
        ordering = ['name']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return f"{self.icon} {self.name}"


class HelpUserBadge(TenantAwareModel):
    """
    User-earned badges tracking.

    Records when users earn badges for achievements.
    """

    user = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='help_badges_earned'
    )

    badge = models.ForeignKey(
        HelpBadge,
        on_delete=models.CASCADE,
        related_name='user_badges'
    )

    earned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user was notified of badge"
    )

    class Meta:
        db_table = 'help_center_user_badge'
        ordering = ['-earned_at']
        unique_together = [['user', 'badge']]  # Can only earn each badge once

    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"


class HelpUserPoints(TenantAwareModel):
    """
    User points accumulation.

    Points system:
    - +5 for article feedback
    - +10 for article suggestion
    - +20 for bug report
    - +50 for writing article (if approved)
    """

    user = models.OneToOneField(
        People,
        on_delete=models.CASCADE,
        related_name='help_points'
    )

    total_points = models.IntegerField(default=0, db_index=True)

    feedback_points = models.IntegerField(default=0)
    suggestion_points = models.IntegerField(default=0)
    contribution_points = models.IntegerField(default=0)
    badge_bonus_points = models.IntegerField(default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'help_center_user_points'
        ordering = ['-total_points']

    def add_points(self, points, category='feedback'):
        """
        Add points to user's total.

        Args:
            points: Number of points to add
            category: Points category (feedback, suggestion, contribution, badge_bonus)
        """
        self.total_points += points

        if category == 'feedback':
            self.feedback_points += points
        elif category == 'suggestion':
            self.suggestion_points += points
        elif category == 'contribution':
            self.contribution_points += points
        elif category == 'badge_bonus':
            self.badge_bonus_points += points

        self.save()

    def __str__(self):
        return f"{self.user.username}: {self.total_points} points"
