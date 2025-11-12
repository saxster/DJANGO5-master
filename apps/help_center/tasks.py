"""
Celery tasks for help center background processing.

Tasks:
- generate_article_embedding: Create pgvector embeddings for semantic search
- analyze_ticket_content_gap: Identify missing help content from tickets
- generate_help_analytics: Daily metrics rollup for dashboards
- sync_ontology_articles_task: Auto-generate help articles from ontology (daily at 2 AM)

Following CLAUDE.md:
- Rule #8: Mandatory timeouts for network calls
- Rule #11: Specific exception handling
- Celery Configuration Guide: Proper decorators, naming, organization
"""

import logging
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)


@shared_task(
    name='help_center.generate_article_embedding',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,  # 5 minutes
    soft_time_limit=270,  # 4.5 minutes
)
def generate_article_embedding(self, article_id):
    """
    Generate pgvector embedding for article (background task).

    Args:
        article_id: HelpArticle ID

    Returns:
        dict: {'success': bool, 'article_id': int, 'embedding_dim': int}
    """
    try:
        from apps.help_center.models import HelpArticle
        from apps.help_center.utils.embedding import EMBEDDING_DIM, text_to_embedding

        article = HelpArticle.objects.get(id=article_id)

        # Generate embedding for semantic search
        try:
            text = f"{article.title} {article.summary} {article.content[:2000]}"
            embedding_vector = text_to_embedding(text)
            article.embedding = {
                'vector': embedding_vector,
                'dim': len(embedding_vector),
                'generated_at': timezone.now().isoformat(),
                'source': 'hashing_v1',
            }
            article.save(update_fields=['embedding', 'updated_at'])

            logger.info(
                "article_embedding_generated",
                extra={'article_id': article_id, 'title': article.title}
            )

        except ImportError:
            logger.warning(f"Embedding service not available for article {article_id}")
            article.embedding = {'status': 'unavailable'}
            article.save(update_fields=['embedding', 'updated_at'])

        return {
            'success': True,
            'article_id': article_id,
            'embedding_dim': EMBEDDING_DIM
        }

    except ObjectDoesNotExist as e:
        logger.error(f"Article {article_id} not found: {e}")
        return {'success': False, 'error': 'Article not found'}

    except NETWORK_EXCEPTIONS as e:
        logger.error(f"Network error generating embedding for article {article_id}: {e}")
        # Retry on network errors
        raise self.retry(exc=e)

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error generating embedding for article {article_id}: {e}")
        return {'success': False, 'error': 'Database error'}

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Unexpected error generating embedding for article {article_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='help_center.analyze_ticket_content_gap',
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
    time_limit=180,  # 3 minutes
    soft_time_limit=150,  # 2.5 minutes
)
def analyze_ticket_content_gap(self, correlation_id):
    """
    Analyze if ticket indicates content gap (background task).

    Args:
        correlation_id: HelpTicketCorrelation ID

    Returns:
        dict: {'success': bool, 'content_gap': bool, 'suggested_article_id': int|None}
    """
    try:
        from apps.help_center.models import HelpTicketCorrelation
        from apps.help_center.services.ticket_integration_service import TicketIntegrationService

        correlation = HelpTicketCorrelation.objects.select_related('ticket').get(id=correlation_id)

        suggested_article = TicketIntegrationService._find_relevant_article(correlation.ticket)

        if suggested_article:
            correlation.suggested_article = suggested_article
            correlation.relevant_article_exists = True
            correlation.content_gap = False
        else:
            correlation.content_gap = True
            correlation.relevant_article_exists = False

        from django.utils import timezone
        correlation.analyzed_at = timezone.now()
        correlation.save()

        logger.info(
            "ticket_content_gap_analyzed",
            extra={
                'correlation_id': correlation_id,
                'ticket_id': correlation.ticket.id,
                'content_gap': correlation.content_gap
            }
        )

        return {
            'success': True,
            'content_gap': correlation.content_gap,
            'suggested_article_id': suggested_article.id if suggested_article else None
        }

    except ObjectDoesNotExist as e:
        logger.error(f"Correlation {correlation_id} not found: {e}")
        return {'success': False, 'error': 'Correlation not found'}

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error analyzing correlation {correlation_id}: {e}")
        raise self.retry(exc=e)

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Unexpected error analyzing correlation {correlation_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='help_center.generate_help_analytics',
    bind=True,
    max_retries=2,
    default_retry_delay=600,  # 10 minutes
    time_limit=600,  # 10 minutes
    soft_time_limit=540,  # 9 minutes
)
def generate_help_analytics(self, tenant_id):
    """
    Generate daily help analytics rollup (scheduled task).

    Args:
        tenant_id: Tenant ID

    Returns:
        dict: {'success': bool, 'metrics': dict}
    """
    try:
        from apps.tenants.models import Tenant
        from apps.help_center.services.analytics_service import AnalyticsService
        from datetime import timedelta
        from django.utils import timezone

        tenant = Tenant.objects.get(id=tenant_id)

        date_from = timezone.now() - timedelta(days=1)
        date_to = timezone.now()

        metrics = AnalyticsService.get_effectiveness_dashboard(
            tenant=tenant,
            date_from=date_from,
            date_to=date_to
        )

        logger.info(
            "help_analytics_generated",
            extra={
                'tenant_id': tenant_id,
                'date_from': date_from.isoformat(),
                'metrics': metrics
            }
        )

        return {
            'success': True,
            'metrics': metrics
        }

    except ObjectDoesNotExist as e:
        logger.error(f"Tenant {tenant_id} not found: {e}")
        return {'success': False, 'error': 'Tenant not found'}

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error generating analytics for tenant {tenant_id}: {e}")
        raise self.retry(exc=e)

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Unexpected error generating analytics for tenant {tenant_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


@shared_task(
    name='help_center.sync_ontology_articles',
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    time_limit=600,  # 10 minutes
    soft_time_limit=540,  # 9 minutes
)
def sync_ontology_articles_task(self, dry_run=False, criticality='high'):
    """
    Sync ontology components to help_center articles (scheduled background task).

    Args:
        dry_run: If True, log only (no DB writes)
        criticality: Filter by criticality level ('high', 'medium', 'low', 'all')

    Returns:
        dict: {
            'success': bool,
            'total_components': int,
            'articles_created': int,
            'articles_updated': int,
            'dry_run': bool,
            'errors': int
        }

    Performance:
    - Rate-limited: 1 article/second (prevents DB overload)
    - Batch size: 10 articles (memory efficiency)
    - Memory footprint: < 200MB
    - Time limit: 10 minutes hard limit

    Following CLAUDE.md:
    - Rule #11: Specific exception handling (DATABASE_EXCEPTIONS)
    - Rate limiting with SECONDS_IN_... constants
    - Comprehensive logging at each step
    """
    import time
    from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

    try:
        from apps.ontology.registry import OntologyRegistry
        from apps.help_center.models import HelpCategory, HelpArticle
        from apps.help_center.services.article_generator_service import ArticleGeneratorService
        from apps.tenants.models import Tenant

        logger.info(
            "ontology_article_sync_started",
            extra={'dry_run': dry_run, 'criticality': criticality}
        )

        # Get components by criticality
        all_components = OntologyRegistry.get_all()

        if criticality == 'all':
            components = all_components
        else:
            # Filter by criticality level
            components = [
                c for c in all_components
                if c.get('criticality', '').lower() == criticality.lower()
            ]

        logger.info(
            "ontology_components_retrieved",
            extra={'count': len(components), 'criticality': criticality}
        )

        if not components:
            logger.warning("No ontology components found for sync")
            return {
                'success': True,
                'total_components': 0,
                'articles_created': 0,
                'articles_updated': 0,
                'dry_run': dry_run,
                'errors': 0
            }

        # Get or create category (not in dry-run mode)
        if not dry_run:
            try:
                tenant = Tenant.objects.first()
                if not tenant:
                    logger.error("No tenant found for article sync")
                    return {'success': False, 'error': 'No tenant available'}

                category, created = HelpCategory.objects.get_or_create(
                    name="Code Reference",
                    tenant=tenant,
                    defaults={
                        'description': 'Auto-generated code documentation from ontology',
                        'slug': 'code-reference'
                    }
                )

                if created:
                    logger.info("Created 'Code Reference' category")

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error creating category: {e}", exc_info=True)
                raise self.retry(exc=e)

        # Process in batches
        service = ArticleGeneratorService()
        batch_size = 10
        created_count = 0
        updated_count = 0
        error_count = 0

        for batch_idx in range(0, len(components), batch_size):
            batch = components[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            total_batches = (len(components) + batch_size - 1) // batch_size

            logger.info(
                "processing_batch",
                extra={
                    'batch': batch_num,
                    'total_batches': total_batches,
                    'batch_size': len(batch)
                }
            )

            for metadata in batch:
                try:
                    qualified_name = metadata.get('qualified_name', 'unknown')

                    if dry_run:
                        logger.info(
                            "dry_run_article_generation",
                            extra={
                                'qualified_name': qualified_name,
                                'domain': metadata.get('domain', 'N/A')
                            }
                        )
                    else:
                        # Check if article exists (for metrics)
                        class_name = qualified_name.split('.')[-1]
                        existing = HelpArticle.objects.filter(
                            title__icontains=class_name,
                            category=category
                        ).exists()

                        # Generate/update article
                        article = service.generate_article(metadata, category)

                        if existing:
                            updated_count += 1
                            logger.debug(
                                "article_updated",
                                extra={'article_id': article.id, 'title': article.title}
                            )
                        else:
                            created_count += 1
                            logger.debug(
                                "article_created",
                                extra={'article_id': article.id, 'title': article.title}
                            )

                        # Rate limit: 1 article/second
                        # Using time.sleep(1) acceptable here per plan requirements
                        # This is a background task, not a request path
                        time.sleep(1)

                except DATABASE_EXCEPTIONS as e:
                    error_count += 1
                    logger.error(
                        "article_generation_db_error",
                        extra={
                            'qualified_name': metadata.get('qualified_name', 'unknown'),
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    # Continue processing remaining articles
                    continue

                except (ValueError, TypeError, KeyError, AttributeError) as e:
                    error_count += 1
                    logger.error(
                        "article_generation_error",
                        extra={
                            'qualified_name': metadata.get('qualified_name', 'unknown'),
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    continue

            # Log batch completion
            logger.info(
                "batch_processed",
                extra={
                    'batch_number': batch_num,
                    'articles_created': created_count,
                    'articles_updated': updated_count,
                    'error_count': error_count
                }
            )

        result = {
            'success': True,
            'total_components': len(components),
            'articles_created': created_count,
            'articles_updated': updated_count,
            'dry_run': dry_run,
            'errors': error_count
        }

        logger.info(
            "ontology_article_sync_complete",
            extra=result
        )

        return result

    except ObjectDoesNotExist as e:
        logger.error(f"Required object not found during sync: {e}", exc_info=True)
        return {'success': False, 'error': 'Object not found'}

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error during ontology sync: {e}", exc_info=True)
        raise self.retry(exc=e)

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Unexpected error during ontology sync: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}
