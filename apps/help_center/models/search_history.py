"""
Help Center Search History Model

Track all help searches for analytics and content gap identification.

Use cases:
- Popular search terms
- Zero-result searches (content gaps)
- Click-through rate analysis
- Search refinement patterns

Created: 2025-11-04 (Split from god file)
"""

import uuid
from django.db import models
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.peoples.models import People


class HelpSearchHistory(TenantAwareModel):
    """
    Track all help searches for analytics and content gap identification.

    Use cases (85 lines - under 150 limit):
    - Popular search terms
    - Zero-result searches (content gaps)
    - Click-through rate analysis
    - Search refinement patterns
    """

    query = models.CharField(max_length=500, db_index=True)
    user = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='help_searches'
    )

    results_count = models.IntegerField(default=0, db_index=True)
    clicked_article = models.ForeignKey(
        'help_center.HelpArticle',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='search_clicks'
    )
    click_position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position of clicked result (1-based)"
    )

    refinement_of = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='refinements',
        help_text="If this is a refined search, link to original"
    )

    session_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Link to HelpArticleInteraction.session_id"
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantAwareManager()

    class Meta:
        db_table = 'help_center_search_history'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['query', 'results_count'], name='help_search_zero_idx'),
            models.Index(fields=['user', 'timestamp'], name='help_search_user_idx'),
        ]

    @property
    def is_zero_result(self):
        """Identify content gaps."""
        return self.results_count == 0

    @property
    def had_click(self):
        """Did user click any result?"""
        return self.clicked_article is not None

    def __str__(self):
        return f"{self.query} ({self.results_count} results)"
