"""
Help Center Article Interaction Model

Track user engagement with help articles.

Metrics:
- View count, time spent, scroll depth
- Bookmarks, shares
- Feedback (helpful/not helpful)
- Session tracking for journey analysis

Created: 2025-11-04 (Split from god file)
"""

import uuid
from django.db import models
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.peoples.models import People


class HelpArticleInteraction(TenantAwareModel):
    """
    Track user engagement with help articles.

    Metrics (120 lines - under 150 limit):
    - View count, time spent, scroll depth
    - Bookmarks, shares
    - Feedback (helpful/not helpful)
    - Session tracking for journey analysis
    """

    class InteractionType(models.TextChoices):
        VIEW = 'VIEW', 'Viewed'
        BOOKMARK = 'BOOKMARK', 'Bookmarked'
        SHARE = 'SHARE', 'Shared'
        VOTE_HELPFUL = 'VOTE_HELPFUL', 'Voted Helpful'
        VOTE_NOT_HELPFUL = 'VOTE_NOT_HELPFUL', 'Voted Not Helpful'
        FEEDBACK_INCORRECT = 'FEEDBACK_INCORRECT', 'Reported Incorrect'
        FEEDBACK_OUTDATED = 'FEEDBACK_OUTDATED', 'Reported Outdated'

    article = models.ForeignKey(
        'help_center.HelpArticle',
        on_delete=models.CASCADE,
        related_name='interactions'
    )
    user = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='help_interactions'
    )

    interaction_type = models.CharField(
        max_length=20,
        choices=InteractionType.choices,
        db_index=True
    )

    time_spent_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time spent reading article (seconds)"
    )
    scroll_depth_percent = models.IntegerField(
        null=True,
        blank=True,
        help_text="How far user scrolled (0-100%)"
    )

    feedback_comment = models.TextField(
        blank=True,
        help_text="Optional comment for votes/feedback"
    )

    session_id = models.UUIDField(db_index=True)
    referrer_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="Page user was on when accessing help"
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantAwareManager()

    class Meta:
        db_table = 'help_center_interaction'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['article', 'interaction_type'], name='help_interaction_type_idx'),
            models.Index(fields=['user', 'timestamp'], name='help_interaction_user_idx'),
            models.Index(fields=['session_id'], name='help_interaction_session_idx'),
        ]

    @classmethod
    def record_view(cls, article, user, session_id, referrer_url='', time_spent=None, scroll_depth=None):
        """Helper method to record article views."""
        return cls.objects.create(
            article=article,
            user=user,
            interaction_type=cls.InteractionType.VIEW,
            session_id=session_id,
            referrer_url=referrer_url,
            time_spent_seconds=time_spent,
            scroll_depth_percent=scroll_depth,
            tenant=user.tenant
        )

    @classmethod
    def record_vote(cls, article, user, is_helpful, comment='', session_id=None):
        """Helper method to record helpful/not helpful votes."""
        if not session_id:
            session_id = uuid.uuid4()

        interaction_type = (
            cls.InteractionType.VOTE_HELPFUL if is_helpful
            else cls.InteractionType.VOTE_NOT_HELPFUL
        )

        if is_helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1
        article.save(update_fields=['helpful_count', 'not_helpful_count', 'updated_at'])

        return cls.objects.create(
            article=article,
            user=user,
            interaction_type=interaction_type,
            feedback_comment=comment,
            session_id=session_id,
            tenant=user.tenant
        )

    def __str__(self):
        return f"{self.user.username} {self.interaction_type} {self.article.title}"
