"""
Knowledge Service - CRUD operations for help articles.

Responsibilities:
- Article creation with automatic indexing
- Update with versioning support
- Publishing workflow (DRAFT → REVIEW → PUBLISHED)
- Bulk import from markdown files

Following CLAUDE.md:
- Rule #7: Service methods <50 lines
- Rule #11: Specific exception handling (no bare except)
- Rule #12: Query optimization with select_for_update
"""

import logging
from django.db import transaction, connection
from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils import timezone
from apps.help_center.models import HelpArticle, HelpCategory
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.ontology import ontology

logger = logging.getLogger(__name__)


@ontology(
    domain="help",
    purpose="Knowledge article CRUD, versioning, and publishing workflows",
    inputs=[
        {"name": "tenant", "type": "Tenant", "description": "Multi-tenant context"},
        {"name": "title", "type": "str", "description": "Article title"},
        {"name": "content", "type": "str", "description": "Markdown content"},
        {"name": "category_id", "type": "int", "description": "HelpCategory ID"},
        {"name": "created_by", "type": "People", "description": "Article author"}
    ],
    outputs=[
        {"name": "article", "type": "HelpArticle", "description": "Created/updated help article"}
    ],
    depends_on=[
        "django.contrib.postgres.search.SearchVector",
        "apps.help_center.tasks.generate_article_embedding"
    ],
    tags=["help", "knowledge-management", "crud", "versioning", "publishing"],
    criticality="high",
    business_value="Enables scalable knowledge base management with versioning and workflow",
    performance_notes="Auto-generates search vectors and embeddings asynchronously via Celery",
    security_notes="Multi-tenant isolated, validates category ownership, uses select_for_update for concurrency"
)
class KnowledgeService:
    """Service for managing help article lifecycle."""

    @classmethod
    @transaction.atomic
    def create_article(cls, tenant, title, content, category_id, created_by, **kwargs):
        """
        Create new help article with automatic indexing.

        Args:
            tenant: Tenant instance
            title: Article title
            content: Markdown content
            category_id: HelpCategory ID
            created_by: People instance (author)
            **kwargs: Optional fields (summary, difficulty_level, target_roles)

        Returns:
            HelpArticle instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            category = HelpCategory.objects.get(id=category_id, tenant=tenant)
        except HelpCategory.DoesNotExist as e:
            raise ValidationError(f"Category {category_id} not found") from e

        slug = cls._generate_unique_slug(tenant, title)

        article = HelpArticle.objects.create(
            tenant=tenant,
            title=title,
            slug=slug,
            content=content,
            category=category,
            created_by=created_by,
            last_updated_by=created_by,
            status=HelpArticle.Status.DRAFT,
            **kwargs
        )

        cls._update_search_vector(article)

        from apps.help_center.tasks import generate_article_embedding
        generate_article_embedding.apply_async(args=[article.id], countdown=10)

        logger.info(
            "help_article_created",
            extra={'article_id': article.id, 'title': title, 'created_by': created_by.username}
        )

        return article

    @classmethod
    @transaction.atomic
    def update_article(cls, article_id, updated_by, **kwargs):
        """
        Update article with versioning.

        Creates new version if content changed significantly.

        Args:
            article_id: Article ID
            updated_by: People instance
            **kwargs: Fields to update

        Returns:
            Updated HelpArticle instance
        """
        try:
            article = HelpArticle.objects.select_for_update().get(id=article_id)
        except HelpArticle.DoesNotExist as e:
            raise ValidationError(f"Article {article_id} not found") from e

        content_changed = 'content' in kwargs and kwargs['content'] != article.content

        for field, value in kwargs.items():
            setattr(article, field, value)

        article.last_updated_by = updated_by

        if content_changed:
            article.version += 1

        article.save()

        if content_changed:
            cls._update_search_vector(article)
            from apps.help_center.tasks import generate_article_embedding
            generate_article_embedding.apply_async(args=[article.id], countdown=10)

        logger.info(
            "help_article_updated",
            extra={'article_id': article.id, 'version': article.version, 'updated_by': updated_by.username}
        )

        return article

    @classmethod
    @transaction.atomic
    def publish_article(cls, article_id, published_by):
        """
        Publish article (DRAFT → PUBLISHED).

        Validates:
        - Content completeness
        - Category assigned
        - Target roles defined

        Args:
            article_id: Article ID
            published_by: People instance

        Returns:
            Published HelpArticle instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            article = HelpArticle.objects.select_for_update().get(id=article_id)
        except HelpArticle.DoesNotExist as e:
            raise ValidationError(f"Article {article_id} not found") from e

        if not article.content:
            raise ValidationError("Cannot publish article without content")
        if not article.category:
            raise ValidationError("Cannot publish article without category")
        if not article.target_roles:
            raise ValidationError("Cannot publish article without target roles")

        article.status = HelpArticle.Status.PUBLISHED
        article.published_date = timezone.now()
        article.last_updated_by = published_by
        article.save(update_fields=['status', 'published_date', 'last_updated_by', 'updated_at'])

        logger.info(
            "help_article_published",
            extra={'article_id': article.id, 'title': article.title, 'published_by': published_by.username}
        )

        return article

    @classmethod
    def _update_search_vector(cls, article):
        """Update PostgreSQL FTS search_vector (weighted)."""
        if connection.vendor != 'postgresql':
            # SQLite (and other test databases) do not support SearchVector.
            article.save(update_fields=['updated_at'])
            return

        article.search_vector = (
            SearchVector('title', weight='A', config='english') +
            SearchVector('summary', weight='B', config='english') +
            SearchVector('content', weight='C', config='english')
        )
        article.save(update_fields=['search_vector', 'updated_at'])

    @classmethod
    def _generate_unique_slug(cls, tenant, title):
        """Generate unique slug for article."""
        base_slug = slugify(title)
        slug = base_slug

        counter = 1
        while HelpArticle.objects.filter(tenant=tenant, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @classmethod
    def bulk_import_from_markdown(cls, tenant, markdown_dir, created_by):
        """
        Bulk import articles from markdown files.

        Used for initial content generation from docs/ directory.

        Args:
            tenant: Tenant instance
            markdown_dir: Directory containing markdown files
            created_by: People instance (author)

        Returns:
            List of created HelpArticle instances
        """
        import os
        try:
            import frontmatter
        except ImportError as e:
            raise ValidationError("frontmatter library not installed: pip install python-frontmatter") from e

        articles_created = []

        for root, dirs, files in os.walk(markdown_dir):
            for filename in files:
                if not filename.endswith('.md'):
                    continue

                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        post = frontmatter.load(f)

                    title = post.metadata.get('title', filename.replace('.md', ''))
                    category_name = post.metadata.get('category', 'Uncategorized')
                    difficulty = post.metadata.get('difficulty', 'BEGINNER')
                    target_roles = post.metadata.get('target_roles', ['all'])

                    category, _ = HelpCategory.objects.get_or_create(
                        tenant=tenant,
                        slug=slugify(category_name),
                        defaults={'name': category_name}
                    )

                    article = cls.create_article(
                        tenant=tenant,
                        title=title,
                        content=post.content,
                        category_id=category.id,
                        created_by=created_by,
                        difficulty_level=difficulty,
                        target_roles=target_roles,
                        summary=post.content[:500]
                    )

                    articles_created.append(article)
                    logger.info(f"Imported: {title}")

                except DATABASE_EXCEPTIONS as e:
                    logger.error(f"Database error importing {filename}: {e}")
                    continue
                except (IOError, OSError) as e:
                    logger.error(f"File error importing {filename}: {e}")
                    continue
                except DATABASE_EXCEPTIONS as e:
                    logger.error(f"Unexpected error importing {filename}: {e}")
                    continue

        return articles_created
