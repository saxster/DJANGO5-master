"""
Knowledge Management Tasks
Document embedding and knowledge base management
"""
import logging
import traceback
import uuid
from typing import List

from celery import shared_task, group
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

# Local imports
from apps.core_onboarding.models import AuthoritativeKnowledge
from apps.onboarding_api.services.knowledge import get_knowledge_service

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


def _validate_knowledge_id(knowledge_id: str) -> str:
    """
    Validate that knowledge_id is a valid UUID format.

    Args:
        knowledge_id: ID to validate

    Returns:
        Validated knowledge_id

    Raises:
        ValidationError: If knowledge_id is not a valid UUID
    """
    if not knowledge_id:
        raise ValidationError("knowledge_id cannot be empty")

    try:
        # Attempt to parse as UUID
        uuid.UUID(str(knowledge_id))
        return knowledge_id
    except (ValueError, AttributeError) as e:
        raise ValidationError(
            f"Invalid knowledge_id format: '{knowledge_id}'. Must be a valid UUID."
        )


@shared_task(bind=True, name='embed_knowledge_document_task')
def embed_knowledge_document_task(self, knowledge_id: str, full_content: str, task_id: str):
    """
    Embed knowledge document with chunking
    """
    task_logger.info(f"Embedding knowledge document {knowledge_id} (task {task_id})")

    try:
        knowledge_service = get_knowledge_service()

        success = knowledge_service.embed_existing_knowledge(knowledge_id, full_content)

        if success:
            task_logger.info(f"Successfully embedded knowledge {knowledge_id}")
            return {
                'status': 'completed',
                'knowledge_id': knowledge_id,
                'embedded_at': timezone.now().isoformat()
            }
        else:
            task_logger.error(f"Failed to embed knowledge {knowledge_id}")
            return {
                'status': 'failed',
                'knowledge_id': knowledge_id,
                'error': 'Embedding process failed'
            }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error embedding knowledge {knowledge_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'knowledge_id': knowledge_id,
            'error': str(e)
        }


@shared_task(bind=True, name='batch_embed_documents_task')
def batch_embed_documents_task(self, knowledge_ids: List[str]):
    """
    Batch embed multiple documents in parallel
    """
    task_logger.info(f"Starting batch embedding for {len(knowledge_ids)} documents")

    try:
        # Create parallel tasks for each document
        embed_tasks = []
        for knowledge_id in knowledge_ids:
            try:
                # SECURITY: Validate UUID format
                validated_id = _validate_knowledge_id(knowledge_id)
                knowledge = AuthoritativeKnowledge.objects.get(knowledge_id=validated_id)
                content = knowledge.content_summary  # Fallback to summary if full content not provided

                embed_task = embed_knowledge_document_task.si(
                    knowledge_id, content, str(uuid.uuid4())
                )
                embed_tasks.append(embed_task)
            except AuthoritativeKnowledge.DoesNotExist:
                task_logger.warning(f"Knowledge {knowledge_id} not found for batch embedding")

        # Execute tasks in parallel using group
        if embed_tasks:
            job = group(embed_tasks)
            result = job.apply_async()

            return {
                'status': 'batch_started',
                'document_count': len(embed_tasks),
                'group_id': result.id
            }
        else:
            return {
                'status': 'no_documents',
                'document_count': 0
            }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error in batch embedding: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'batch_failed',
            'error': str(e)
        }


# Define exception classes for imports
class IntegrationException(Exception):
    """Integration exception placeholder"""
    pass


class LLMServiceException(Exception):
    """LLM service exception placeholder"""
    pass
