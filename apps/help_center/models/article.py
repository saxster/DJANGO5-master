"""
Help Center Article Model

Knowledge base article with full-text and semantic search.

Architecture:
- Inherits TenantAwareModel for multi-tenant isolation
- search_vector for PostgreSQL FTS (weighted: title > summary > content)
- embedding for pgvector semantic search (384-dim)
- Role-based filtering via target_roles
- Versioning for change tracking

Created: 2025-11-04 (Split from god file)
"""

from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import People


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
        'help_center.HelpCategory',
        on_delete=models.PROTECT,
        related_name='articles'
    )
    tags = models.ManyToManyField('help_center.HelpTag', blank=True)

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
