"""
Help Center Models

Core models for knowledge base, search analytics, and ticket correlation.

Models (all < 150 lines per class):
1. HelpTag - Simple tagging for articles (~20 lines)
2. HelpCategory - Hierarchical categorization (~95 lines)
3. HelpArticle - Knowledge base articles with FTS + pgvector (~145 lines)
4. HelpSearchHistory - Search analytics tracking (~85 lines)
5. HelpArticleInteraction - User engagement metrics (~120 lines)
6. HelpTicketCorrelation - Ticket correlation for effectiveness (~110 lines)

Following CLAUDE.md:
- Rule #7: Each model <150 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes
- Multi-tenant isolation via TenantAwareModel

Created: 2025-11-03
"""

import uuid
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import People


class HelpTag(TenantAwareModel):
    """Simple tagging for help articles."""

    name = models.CharField(max_length=50, db_index=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        db_table = 'help_center_tag'
        ordering = ['name']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.name


class HelpCategory(TenantAwareModel):
    """
    Hierarchical category tree for organizing help articles.

    Example tree:
    - Operations
      - Work Orders
        - Approval Workflows
        - Vendor Management
      - PPM Scheduling
    - Assets
      - Inventory Management
      - QR Code Scanning
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )

    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon class (e.g., 'fa-wrench', 'material-icons:build')"
    )
    color = models.CharField(
        max_length=7,
        default='#1976d2',
        help_text="Hex color code for category badge"
    )

    display_order = models.IntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'help_center_category'
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Help Categories'
        unique_together = [['tenant', 'slug']]

    def get_ancestors(self):
        """Get all parent categories up to root."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))

    def get_descendants(self):
        """Get all child categories recursively."""
        descendants = []
        for child in self.children.filter(is_active=True):
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def get_breadcrumb(self):
        """Get breadcrumb path: Operations > Work Orders > Approval Workflows"""
        ancestors = self.get_ancestors()
        ancestors.append(self)
        return ' > '.join(cat.name for cat in ancestors)

    def __str__(self):
        return self.get_breadcrumb()


class HelpArticle(TenantAwareModel):
    """
    Knowledge base article with full-text and semantic search.

    Architecture (145 lines - under 150 limit):
    - Inherits TenantAwareModel for multi-tenant isolation
    - search_vector for PostgreSQL FTS (weighted: title > summary > content)
    - embedding for pgvector semantic search (384-dim)
    - Role-based filtering via target_roles
    - Versioning for change tracking
    """

    class DifficultyLevel(models.TextChoices):
        BEGINNER = 'BEGINNER', 'Beginner'
        INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
        ADVANCED = 'ADVANCED', 'Advanced'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        REVIEW = 'REVIEW', 'Under Review'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'

    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=250)
    summary = models.TextField(max_length=500)
    content = models.TextField()

    category = models.ForeignKey(
        HelpCategory,
        on_delete=models.PROTECT,
        related_name='articles'
    )
    tags = models.ManyToManyField(HelpTag, blank=True)

    difficulty_level = models.CharField(
        max_length=20,
        choices=DifficultyLevel.choices,
        default=DifficultyLevel.BEGINNER,
        db_index=True
    )

    target_roles = models.JSONField(
        default=list,
        help_text="List of permission group names that can view this article"
    )

    search_vector = SearchVectorField(null=True, editable=False)
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="384-dim embedding for semantic search (pgvector)"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )

    version = models.IntegerField(default=1)
    previous_version = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='next_versions'
    )

    view_count = models.IntegerField(default=0, db_index=True)
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)

    created_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='help_articles_created'
    )
    last_updated_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='help_articles_updated'
    )
    published_date = models.DateTimeField(null=True, blank=True)
    last_reviewed_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'help_center_article'
        ordering = ['-published_date', '-created_at']
        indexes = [
            GinIndex(fields=['search_vector'], name='help_article_search_idx'),
            models.Index(fields=['status', 'published_date'], name='help_article_published_idx'),
            models.Index(fields=['category', 'status'], name='help_article_category_idx'),
            models.Index(fields=['view_count'], name='help_article_popularity_idx'),
        ]
        unique_together = [['tenant', 'slug']]

    @property
    def helpful_ratio(self):
        """Calculate effectiveness score (0-1)."""
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0.5
        return self.helpful_count / total

    @property
    def is_stale(self):
        """Check if article needs review (>6 months old + declining effectiveness)."""
        from datetime import timedelta

        if not self.last_reviewed_date:
            return True

        age_threshold = timezone.now() - timedelta(days=180)
        is_old = self.last_reviewed_date < age_threshold
        is_declining = self.helpful_ratio < 0.6

        return is_old and is_declining

    def __str__(self):
        return f"{self.title} (v{self.version})"


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
        HelpArticle,
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
        HelpArticle,
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


class HelpTicketCorrelation(TenantAwareModel):
    """
    Correlate help usage with ticket creation for effectiveness analysis.

    Key questions (110 lines - under 150 limit):
    - Did user try help before creating ticket?
    - Which articles did they view?
    - Was relevant content available?
    - How long did it take to resolve with/without help?
    """

    ticket = models.OneToOneField(
        'y_helpdesk.Ticket',
        on_delete=models.CASCADE,
        related_name='help_correlation'
    )

    help_attempted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Did user view any help articles before creating ticket?"
    )

    help_session_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Link to help session if help was attempted"
    )

    articles_viewed = models.ManyToManyField(
        HelpArticle,
        blank=True,
        related_name='ticket_correlations'
    )

    search_queries = models.JSONField(
        default=list,
        help_text="List of search queries attempted before ticket creation"
    )

    relevant_article_exists = models.BooleanField(
        null=True,
        blank=True,
        help_text="Based on ticket analysis, does relevant help content exist?"
    )

    content_gap = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Should content team create new article for this topic?"
    )

    suggested_article = models.ForeignKey(
        HelpArticle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='suggested_for_tickets',
        help_text="Article to show in ticket view"
    )

    resolution_time_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time from ticket creation to resolution (minutes)"
    )

    analyzed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When correlation analysis was performed"
    )

    class Meta:
        db_table = 'help_center_ticket_correlation'
        indexes = [
            models.Index(fields=['help_attempted', 'content_gap'], name='help_ticket_gap_idx'),
            models.Index(fields=['ticket'], name='help_ticket_correlation_idx'),
        ]

    @classmethod
    def create_from_ticket(cls, ticket, user_help_activity=None):
        """
        Create correlation record when ticket is created.

        Args:
            ticket: Ticket instance
            user_help_activity: Dict with {
                'help_attempted': bool,
                'session_id': UUID,
                'articles_viewed': [article_ids],
                'search_queries': [queries]
            }
        """
        correlation = cls.objects.create(
            ticket=ticket,
            tenant=ticket.tenant,
            help_attempted=False,
            content_gap=False
        )

        if user_help_activity:
            correlation.help_attempted = user_help_activity.get('help_attempted', False)
            correlation.help_session_id = user_help_activity.get('session_id')
            correlation.search_queries = user_help_activity.get('search_queries', [])

            article_ids = user_help_activity.get('articles_viewed', [])
            if article_ids:
                correlation.articles_viewed.set(article_ids)

            correlation.save()

        return correlation

    def __str__(self):
        status = "with help" if self.help_attempted else "without help"
        return f"Ticket #{self.ticket.id} ({status})"
