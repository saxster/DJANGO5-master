"""
Gamification Service for Help Center.

Manages badges and points system.

Features:
- Automatic badge awarding based on criteria
- Points tracking per action
- Leaderboard generation
- Badge notifications

Following CLAUDE.md Rule #7: Methods <50 lines
"""

import logging
from django.db import transaction
from django.utils import timezone
from apps.help_center.gamification_models import HelpBadge, HelpUserBadge, HelpUserPoints
from apps.help_center.models import HelpArticleInteraction

logger = logging.getLogger(__name__)


class GamificationService:
    """Service for managing gamification features."""

    POINTS_CONFIG = {
        'article_view': 1,
        'article_feedback': 5,
        'article_suggestion': 10,
        'bug_report': 20,
        'article_contribution': 50,
    }

    @classmethod
    def award_points(cls, user, action, points=None):
        """
        Award points to user for action.

        Args:
            user: People instance
            action: Action type (article_view, article_feedback, etc.)
            points: Custom points (overrides default)
        """
        if points is None:
            points = cls.POINTS_CONFIG.get(action, 0)

        user_points, created = HelpUserPoints.objects.get_or_create(
            user=user,
            tenant=user.tenant
        )

        category = cls._get_points_category(action)
        user_points.add_points(points, category)

        cls.check_and_award_badges(user)

        logger.info(
            "points_awarded",
            extra={'user': user.username, 'action': action, 'points': points}
        )

    @classmethod
    def _get_points_category(cls, action):
        """Map action to points category."""
        if 'feedback' in action or 'vote' in action:
            return 'feedback'
        elif 'suggestion' in action:
            return 'suggestion'
        elif 'contribution' in action:
            return 'contribution'
        else:
            return 'feedback'

    @classmethod
    @transaction.atomic
    def check_and_award_badges(cls, user):
        """
        Check if user qualifies for any badges and award them.

        Args:
            user: People instance
        """
        active_badges = HelpBadge.objects.filter(
            tenant=user.tenant,
            is_active=True
        )

        for badge in active_badges:
            if cls._user_meets_criteria(user, badge.criteria):
                if not HelpUserBadge.objects.filter(user=user, badge=badge).exists():
                    HelpUserBadge.objects.create(
                        user=user,
                        badge=badge,
                        tenant=user.tenant
                    )

                    user_points, _ = HelpUserPoints.objects.get_or_create(
                        user=user,
                        tenant=user.tenant
                    )
                    user_points.add_points(badge.points_awarded, 'badge_bonus')

                    logger.info(
                        "badge_awarded",
                        extra={'user': user.username, 'badge': badge.name}
                    )

    @classmethod
    def _user_meets_criteria(cls, user, criteria):
        """Check if user meets badge criteria."""
        for criterion, threshold in criteria.items():
            if criterion == 'feedback_count':
                count = HelpArticleInteraction.objects.filter(
                    user=user,
                    interaction_type__in=['VOTE_HELPFUL', 'VOTE_NOT_HELPFUL']
                ).count()
                if count < threshold:
                    return False

            elif criterion == 'article_views':
                count = HelpArticleInteraction.objects.filter(
                    user=user,
                    interaction_type='VIEW'
                ).count()
                if count < threshold:
                    return False

            elif criterion == 'helpful_votes':
                count = HelpArticleInteraction.objects.filter(
                    user=user,
                    interaction_type='VOTE_HELPFUL'
                ).count()
                if count < threshold:
                    return False

        return True

    @classmethod
    def get_leaderboard(cls, tenant, limit=10, timeframe='all_time'):
        """
        Get top users by points.

        Args:
            tenant: Tenant instance
            limit: Number of users to return
            timeframe: 'all_time', 'month', 'week'

        Returns:
            List of {user, points, rank, badges}
        """
        qs = HelpUserPoints.objects.filter(tenant=tenant).select_related('user')

        if timeframe == 'month':
            from datetime import timedelta
            from django.utils import timezone
            month_ago = timezone.now() - timedelta(days=30)
            qs = qs.filter(last_updated__gte=month_ago)
        elif timeframe == 'week':
            from datetime import timedelta
            from django.utils import timezone
            week_ago = timezone.now() - timedelta(days=7)
            qs = qs.filter(last_updated__gte=week_ago)

        top_users = qs.order_by('-total_points')[:limit]

        leaderboard = []
        for rank, user_points in enumerate(top_users, 1):
            badges_earned = HelpUserBadge.objects.filter(
                user=user_points.user
            ).select_related('badge').count()

            leaderboard.append({
                'rank': rank,
                'user': user_points.user,
                'points': user_points.total_points,
                'badges_count': badges_earned
            })

        return leaderboard
