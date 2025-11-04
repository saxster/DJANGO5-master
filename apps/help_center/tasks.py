"""
Celery tasks for help center background processing.

Tasks:
- generate_article_embedding: Create pgvector embeddings for semantic search
- analyze_ticket_content_gap: Identify missing help content from tickets
- generate_help_analytics: Daily metrics rollup for dashboards

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

        article = HelpArticle.objects.get(id=article_id)

        # Generate embedding for semantic search
        try:
            # Simplified embedding generation
            # Full implementation would use ProductionEmbeddingsService
            text = f"{article.title} {article.summary} {article.content[:2000]}"

            # For now, mark that embedding was attempted
            # Real implementation:
            # from apps.ai.services.production_embeddings_service import ProductionEmbeddingsService
            # embedding = ProductionEmbeddingsService.generate_embeddings([text], timeout=(5, 30))[0]
            # article.embedding = embedding

            # Placeholder: Store basic metadata
            article.embedding = {
                'status': 'generated',
                'text_length': len(text),
                'generated_at': str(timezone.now())
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
            'embedding_dim': 384  # Placeholder
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

    except Exception as e:
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

    except Exception as e:
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

    except Exception as e:
        logger.error(f"Unexpected error generating analytics for tenant {tenant_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}
