"""
Celery tasks for HelpBot background processing.

Tasks:
- update_txtai_index_task: Incremental txtai index updates (Nov 2025)

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
    name='helpbot.update_txtai_index',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=180,  # 3 minutes
    soft_time_limit=150,  # 2.5 minutes
    ignore_result=False,
)
def update_txtai_index_task(self, knowledge_id, operation='update'):
    """
    Update txtai index for a single knowledge article (async task).

    Args:
        knowledge_id: HelpBotKnowledge ID
        operation: 'add', 'update', or 'delete'

    Returns:
        dict: {'success': bool, 'knowledge_id': str, 'operation': str}

    Performance:
    - Batched via countdown=5 in signal (aggregates rapid updates)
    - Non-blocking (signal fires async task, doesn't wait)
    - Failure doesn't break CRUD operations (separate concern)
    """
    try:
        from apps.helpbot.models import HelpBotKnowledge
        from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService

        knowledge_service = HelpBotKnowledgeService()

        # Only proceed if txtai enabled
        if not knowledge_service.txtai_enabled:
            logger.debug(
                f"txtai not enabled, skipping index update for {knowledge_id}"
            )
            return {
                'success': True,
                'knowledge_id': knowledge_id,
                'operation': operation,
                'skipped': True,
                'reason': 'txtai_disabled'
            }

        # Handle different operations
        if operation == 'delete':
            # Remove from index (knowledge already deleted from DB)
            success = knowledge_service.remove_from_index(knowledge_id)

            logger.info(
                "txtai_index_delete",
                extra={'knowledge_id': knowledge_id}
            )

        else:  # 'add' or 'update'
            # Get knowledge article
            try:
                knowledge = HelpBotKnowledge.objects.get(knowledge_id=knowledge_id)
            except ObjectDoesNotExist:
                logger.warning(f"Knowledge {knowledge_id} not found for index update")
                return {
                    'success': False,
                    'knowledge_id': knowledge_id,
                    'error': 'Knowledge not found'
                }

            # Add/update in index
            success = knowledge_service.update_index_document(knowledge)

            logger.info(
                "txtai_index_update",
                extra={
                    'knowledge_id': knowledge_id,
                    'title': knowledge.title,
                    'operation': operation
                }
            )

        return {
            'success': success,
            'knowledge_id': knowledge_id,
            'operation': operation,
            'updated_at': timezone.now().isoformat()
        }

    except ObjectDoesNotExist as e:
        logger.error(f"Knowledge {knowledge_id} not found: {e}")
        return {'success': False, 'error': 'Knowledge not found'}

    except NETWORK_EXCEPTIONS as e:
        logger.error(
            f"Network error updating txtai index for {knowledge_id}: {e}"
        )
        # Retry on network errors
        raise self.retry(exc=e)

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Database error updating txtai index for {knowledge_id}: {e}"
        )
        # Don't retry database errors (likely permanent)
        return {'success': False, 'error': 'Database error'}

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Unexpected error updating txtai index for {knowledge_id}: {e}",
            exc_info=True
        )
        return {'success': False, 'error': str(e)}
