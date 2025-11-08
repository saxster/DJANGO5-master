"""
Search Indexing Celery Tasks

Incremental and full reindexing tasks for unified semantic search.
Uses Celery with idempotency framework for reliable background processing.

Follows CLAUDE.md Celery standards:
- Rule #8: Celery task decorators with retries
- Rule #14: Idempotency with correlation IDs
- Task naming: module_action (search_index_tickets)
- Short task methods (<30 lines)
"""

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from celery import shared_task
from django.core.cache import cache

from apps.core.tasks.base import BaseIdempotentTask
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.search.services.unified_semantic_search_service import UnifiedSemanticSearchService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)


@shared_task(
    base=BaseIdempotentTask,
    bind=True,
    name='search.index_tickets',
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=540,
)
def search_index_tickets(
    self,
    tenant_id: Optional[int] = None,
    correlation_id: Optional[str] = None
):
    """
    Index all tickets for semantic search.

    Args:
        tenant_id: Specific tenant to index (None = all)
        correlation_id: Idempotency correlation ID

    Returns:
        dict: Indexing results
    """
    try:
        logger.info(f"Starting ticket indexing for tenant {tenant_id}")

        service = UnifiedSemanticSearchService()
        indexed_count = len(service._index_tickets(tenant_id))

        logger.info(f"Successfully indexed {indexed_count} tickets")

        return {
            'success': True,
            'module': 'tickets',
            'indexed_count': indexed_count,
            'tenant_id': tenant_id,
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error indexing tickets: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error indexing tickets: {e}", exc_info=True)
        return {
            'success': False,
            'module': 'tickets',
            'error': str(e),
        }


@shared_task(
    base=BaseIdempotentTask,
    bind=True,
    name='search.index_work_orders',
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=540,
)
def search_index_work_orders(
    self,
    tenant_id: Optional[int] = None,
    correlation_id: Optional[str] = None
):
    """
    Index all work orders for semantic search.

    Args:
        tenant_id: Specific tenant to index (None = all)
        correlation_id: Idempotency correlation ID

    Returns:
        dict: Indexing results
    """
    try:
        logger.info(f"Starting work order indexing for tenant {tenant_id}")

        service = UnifiedSemanticSearchService()
        indexed_count = len(service._index_work_orders(tenant_id))

        logger.info(f"Successfully indexed {indexed_count} work orders")

        return {
            'success': True,
            'module': 'work_orders',
            'indexed_count': indexed_count,
            'tenant_id': tenant_id,
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error indexing work orders: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error indexing work orders: {e}", exc_info=True)
        return {
            'success': False,
            'module': 'work_orders',
            'error': str(e),
        }


@shared_task(
    base=BaseIdempotentTask,
    bind=True,
    name='search.index_assets',
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=540,
)
def search_index_assets(
    self,
    tenant_id: Optional[int] = None,
    correlation_id: Optional[str] = None
):
    """
    Index all assets for semantic search.

    Args:
        tenant_id: Specific tenant to index (None = all)
        correlation_id: Idempotency correlation ID

    Returns:
        dict: Indexing results
    """
    try:
        logger.info(f"Starting asset indexing for tenant {tenant_id}")

        service = UnifiedSemanticSearchService()
        indexed_count = len(service._index_assets(tenant_id))

        logger.info(f"Successfully indexed {indexed_count} assets")

        return {
            'success': True,
            'module': 'assets',
            'indexed_count': indexed_count,
            'tenant_id': tenant_id,
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error indexing assets: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error indexing assets: {e}", exc_info=True)
        return {
            'success': False,
            'module': 'assets',
            'error': str(e),
        }


@shared_task(
    base=BaseIdempotentTask,
    bind=True,
    name='search.index_people',
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=540,
)
def search_index_people(
    self,
    tenant_id: Optional[int] = None,
    correlation_id: Optional[str] = None
):
    """
    Index all people for semantic search.

    Args:
        tenant_id: Specific tenant to index (None = all)
        correlation_id: Idempotency correlation ID

    Returns:
        dict: Indexing results
    """
    try:
        logger.info(f"Starting people indexing for tenant {tenant_id}")

        service = UnifiedSemanticSearchService()
        indexed_count = len(service._index_people(tenant_id))

        logger.info(f"Successfully indexed {indexed_count} people")

        return {
            'success': True,
            'module': 'people',
            'indexed_count': indexed_count,
            'tenant_id': tenant_id,
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error indexing people: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error indexing people: {e}", exc_info=True)
        return {
            'success': False,
            'module': 'people',
            'error': str(e),
        }


@shared_task(
    base=BaseIdempotentTask,
    bind=True,
    name='search.rebuild_unified_index',
    max_retries=2,
    default_retry_delay=300,
    time_limit=3600,
    soft_time_limit=3300,
)
def search_rebuild_unified_index(
    self,
    tenant_id: Optional[int] = None,
    correlation_id: Optional[str] = None
):
    """
    Full rebuild of unified search index.

    This is a long-running task (up to 1 hour) that rebuilds the entire
    txtai index from scratch. Scheduled to run weekly.

    Args:
        tenant_id: Specific tenant to index (None = all)
        correlation_id: Idempotency correlation ID

    Returns:
        dict: Rebuild results
    """
    try:
        logger.info(f"Starting full index rebuild for tenant {tenant_id}")

        service = UnifiedSemanticSearchService()
        success = service.build_unified_index(tenant_id)

        if success:
            # Clear search cache after rebuild
            cache_pattern = f"{service.cache_prefix}:*"
            cache.delete_pattern(cache_pattern)

            logger.info(f"Successfully rebuilt unified search index")

            return {
                'success': True,
                'operation': 'full_rebuild',
                'tenant_id': tenant_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            }
        else:
            logger.error("Failed to rebuild unified search index", exc_info=True)
            return {
                'success': False,
                'operation': 'full_rebuild',
                'error': 'Index build failed',
            }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error rebuilding index: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300)
    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error rebuilding index: {e}", exc_info=True)
        return {
            'success': False,
            'operation': 'full_rebuild',
            'error': str(e),
        }


@shared_task(
    base=BaseIdempotentTask,
    bind=True,
    name='search.incremental_index_update',
    max_retries=3,
    default_retry_delay=60,
    time_limit=900,
    soft_time_limit=840,
)
def search_incremental_index_update(
    self,
    tenant_id: Optional[int] = None,
    correlation_id: Optional[str] = None
):
    """
    Incremental update of search index.

    Runs every 15 minutes to index new/updated items.
    More efficient than full rebuild for continuous updates.

    Args:
        tenant_id: Specific tenant to index (None = all)
        correlation_id: Idempotency correlation ID

    Returns:
        dict: Update results
    """
    try:
        logger.info(f"Starting incremental index update for tenant {tenant_id}")

        # Run incremental indexing for each module
        results = {}

        # Index tickets
        ticket_result = search_index_tickets.apply(
            kwargs={'tenant_id': tenant_id}
        ).get()
        results['tickets'] = ticket_result

        # Index work orders
        wo_result = search_index_work_orders.apply(
            kwargs={'tenant_id': tenant_id}
        ).get()
        results['work_orders'] = wo_result

        # Index assets
        asset_result = search_index_assets.apply(
            kwargs={'tenant_id': tenant_id}
        ).get()
        results['assets'] = asset_result

        # Index people
        people_result = search_index_people.apply(
            kwargs={'tenant_id': tenant_id}
        ).get()
        results['people'] = people_result

        # Calculate total indexed
        total_indexed = sum(
            r.get('indexed_count', 0)
            for r in results.values()
            if r.get('success')
        )

        logger.info(f"Incremental update complete: {total_indexed} items indexed")

        return {
            'success': True,
            'operation': 'incremental_update',
            'total_indexed': total_indexed,
            'module_results': results,
            'tenant_id': tenant_id,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        }

    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error in incremental index update: {e}", exc_info=True)
        return {
            'success': False,
            'operation': 'incremental_update',
            'error': str(e),
        }


# =============================================================================
# CELERY BEAT SCHEDULE
# =============================================================================

# Add to intelliwiz_config/celery.py beat schedule:
"""
CELERY_BEAT_SCHEDULE = {
    # ... existing tasks ...

    # Incremental search index update every 15 minutes
    'search-incremental-index-update': {
        'task': 'search.incremental_index_update',
        'schedule': crontab(minute='*/15'),
        'options': {
            'queue': 'default',
            'priority': 5,
        },
    },

    # Full search index rebuild weekly (Sunday 2 AM)
    'search-full-index-rebuild': {
        'task': 'search.rebuild_unified_index',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),
        'options': {
            'queue': 'default',
            'priority': 3,
        },
    },
}
"""
