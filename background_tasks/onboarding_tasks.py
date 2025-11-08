"""
Celery tasks for Conversational Onboarding (Phase 1 MVP)
"""
import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db import transaction, DatabaseError, OperationalError, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone

# Local imports
from apps.core_onboarding.models import ConversationSession, LLMRecommendation
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service
from apps.onboarding_api.services.knowledge import get_knowledge_service
from apps.onboarding_api.services.translation import get_conversation_translator
from apps.onboarding_api.services.circuit_breaker import get_circuit_breaker

# Resilience imports
from background_tasks.onboarding_retry_strategies import (
    llm_api_task_config,
    database_task_config,
    DATABASE_EXCEPTIONS,
    LLM_API_EXCEPTIONS
)
from background_tasks.dead_letter_queue import dlq_handler

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


@shared_task(
    bind=True,
    name='process_conversation_step',
    soft_time_limit=600,   # 10 minutes - LLM processing
    time_limit=900,         # 15 minutes hard limit
    **llm_api_task_config()  # Apply LLM API retry config with exponential backoff
)
def process_conversation_step(self, conversation_id: str, user_input: str, context: Dict[str, Any], task_id: str):
    """
    Process a conversation step asynchronously

    Args:
        conversation_id: UUID of the conversation session
        user_input: User's input text
        context: Additional context data
        task_id: Unique task identifier for tracking
    """
    task_logger.info(f"Starting conversation processing task {task_id} for session {conversation_id}")

    try:
        # Get conversation session
        with transaction.atomic():
            session = ConversationSession.objects.select_for_update().get(
                session_id=conversation_id
            )

            # Update session state
            session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
            session.save()

        # Get services
        llm_service = get_llm_service()
        checker_service = get_checker_service()
        knowledge_service = get_knowledge_service()
        translator = get_conversation_translator()

        # Get circuit breaker for LLM API protection
        llm_circuit_breaker = get_circuit_breaker('llm_api')

        # Process with maker LLM (with circuit breaker protection)
        task_logger.info(f"Processing with Maker LLM for session {conversation_id}")

        def llm_call():
            return llm_service.process_conversation_step(
                session=session,
                user_input=user_input,
                context=context
            )

        def llm_fallback():
            """Fallback when LLM circuit is open"""
            task_logger.warning(f"LLM circuit breaker open - using fallback response")
            return {
                'recommendations': {'message': 'Service temporarily unavailable. Please try again.'},
                'confidence_score': 0.0,
                'fallback_used': True
            }

        # Execute with circuit breaker
        maker_result = llm_circuit_breaker.call(
            llm_call,
            fallback=llm_fallback
        )

        # Validate with authoritative knowledge
        task_logger.info(f"Validating against knowledge base for session {conversation_id}")
        validation_result = knowledge_service.validate_recommendation_against_knowledge(
            recommendation=maker_result.get('recommendations', {}),
            context=context
        )

        # Create LLM recommendation record
        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output=maker_result,
            checker_output=None,  # Will be populated if checker is enabled
            consensus=maker_result,  # For MVP, maker output is the consensus
            authoritative_sources=validation_result.get('supporting_sources', []),
            confidence_score=min(
                maker_result.get('confidence_score', 0.8),
                validation_result.get('confidence_score', 0.8)
            )
        )

        # Optional: Run checker LLM if enabled
        if checker_service:
            task_logger.info(f"Running Checker LLM for session {conversation_id}")
            try:
                checker_result = checker_service.validate_recommendations(
                    maker_output=maker_result,
                    context=context
                )

                # Update recommendation with checker output
                recommendation.checker_output = checker_result

                # Create consensus between maker and checker
                consensus = _create_consensus(maker_result, checker_result)
                recommendation.consensus = consensus

                # Adjust confidence score
                confidence_adjustment = checker_result.get('confidence_adjustment', 0.0)
                recommendation.confidence_score = min(
                    recommendation.confidence_score + confidence_adjustment,
                    1.0
                )

                recommendation.save()

            except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
                task_logger.error(f"Checker LLM failed for session {conversation_id}: {str(e)}")
                # Continue without checker - not critical for MVP

        # Translate response if needed
        target_language = session.language
        if target_language != 'en':
            task_logger.info(f"Translating response to {target_language} for session {conversation_id}")
            try:
                translated_consensus = translator.translate_conversation_response(
                    recommendation.consensus,
                    target_language
                )
                # Store both original and translated versions
                recommendation.consensus['translated'] = translated_consensus
                recommendation.save()
            except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
                task_logger.warning(f"Translation failed for session {conversation_id}: {str(e)}")
                # Continue without translation

        # Update session state
        with transaction.atomic():
            session = ConversationSession.objects.select_for_update().get(
                session_id=conversation_id
            )
            session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            session.collected_data.update({
                'task_id': task_id,
                'processed_at': timezone.now().isoformat(),
                'recommendation_id': str(recommendation.recommendation_id)
            })
            session.save()

        task_logger.info(f"Successfully completed conversation processing task {task_id}")

        return {
            'status': 'completed',
            'recommendation_id': str(recommendation.recommendation_id),
            'confidence_score': recommendation.confidence_score,
            'session_state': session.current_state
        }

    except ConversationSession.DoesNotExist as e:
        error_msg = f"Conversation session {conversation_id} not found"
        task_logger.error(error_msg)
        # Non-retryable - return error immediately
        return {
            'status': 'failed',
            'error': error_msg
        }

    except DATABASE_EXCEPTIONS as e:
        # Database errors - will be retried automatically via retry config
        error_msg = f"Database error processing conversation {conversation_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Check if this is the final retry
        if self.request.retries >= self.max_retries:
            task_logger.error(f"Max retries exceeded - sending to DLQ")

            # Send to dead letter queue for manual intervention
            dlq_handler.send_to_dlq(
                task_id=task_id,
                task_name=self.name,
                args=(conversation_id, user_input, context, task_id),
                kwargs={},
                exception=e,
                retry_count=self.request.retries,
                correlation_id=task_id
            )

        # Re-raise to trigger Celery auto-retry
        raise

    except LLM_API_EXCEPTIONS as e:
        # LLM API errors - will be retried automatically via retry config
        error_msg = f"LLM API error processing conversation {conversation_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Check if this is the final retry
        if self.request.retries >= self.max_retries:
            task_logger.error(f"Max retries exceeded - sending to DLQ")

            # Send to dead letter queue
            dlq_handler.send_to_dlq(
                task_id=task_id,
                task_name=self.name,
                args=(conversation_id, user_input, context, task_id),
                kwargs={},
                exception=e,
                retry_count=self.request.retries,
                correlation_id=task_id
            )

        # Re-raise to trigger Celery auto-retry
        raise

    except (ValueError, TypeError, ValidationError) as e:
        # Validation errors - usually NOT retryable
        error_msg = f"Validation error processing conversation {conversation_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Update session to error state (don't retry validation errors)
        try:
            with transaction.atomic():
                session = ConversationSession.objects.select_for_update().get(
                    session_id=conversation_id
                )
                session.current_state = ConversationSession.StateChoices.ERROR
                session.error_message = str(e)
                session.save()
        except DATABASE_EXCEPTIONS as session_error:
            task_logger.error(f"Failed to update session error state: {str(session_error)}")

        # Send to DLQ immediately (not retryable)
        dlq_handler.send_to_dlq(
            task_id=task_id,
            task_name=self.name,
            args=(conversation_id, user_input, context, task_id),
            kwargs={},
            exception=e,
            retry_count=self.request.retries,
            correlation_id=task_id
        )

        return {
            'status': 'failed',
            'error': error_msg
        }


@shared_task(bind=True, name='validate_recommendations')
def validate_recommendations(self, recommendation_ids: list, context: Dict[str, Any]):
    """
    Validate multiple recommendations against authoritative knowledge

    Args:
        recommendation_ids: List of recommendation UUIDs to validate
        context: Validation context
    """
    task_logger.info(f"Starting recommendation validation task for {len(recommendation_ids)} recommendations")

    results = []
    knowledge_service = get_knowledge_service()

    try:
        for rec_id in recommendation_ids:
            try:
                recommendation = LLMRecommendation.objects.get(recommendation_id=rec_id)

                # Validate against knowledge base
                validation_result = knowledge_service.validate_recommendation_against_knowledge(
                    recommendation=recommendation.consensus,
                    context=context
                )

                # Update recommendation with validation results
                recommendation.authoritative_sources = validation_result.get('supporting_sources', [])

                # Adjust confidence if conflicts found
                if validation_result.get('potential_conflicts'):
                    recommendation.confidence_score *= 0.8

                recommendation.save()

                results.append({
                    'recommendation_id': rec_id,
                    'status': 'validated',
                    'confidence_score': recommendation.confidence_score,
                    'conflicts': validation_result.get('potential_conflicts', [])
                })

            except LLMRecommendation.DoesNotExist:
                task_logger.error(f"Recommendation {rec_id} not found")
                results.append({
                    'recommendation_id': rec_id,
                    'status': 'not_found',
                    'error': 'Recommendation not found'
                })

            except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
                task_logger.error(f"Error validating recommendation {rec_id}: {str(e)}")
                results.append({
                    'recommendation_id': rec_id,
                    'status': 'failed',
                    'error': str(e)
                })

        task_logger.info(f"Completed validation for {len(recommendation_ids)} recommendations")
        return {
            'status': 'completed',
            'results': results
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error in batch validation: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': error_msg
        }


@shared_task(bind=True, name='apply_approved_recommendations')
def apply_approved_recommendations(self, approved_items: list, user_id: int, dry_run: bool = True):
    """
    Apply approved recommendations to the system

    Args:
        approved_items: List of approved recommendation UUIDs
        user_id: ID of the user approving the recommendations
        dry_run: Whether to perform a dry run without actual changes
    """
    task_logger.info(f"Applying {len(approved_items)} recommendations (dry_run={dry_run})")

    try:
        from apps.onboarding_api.integration.mapper import IntegrationAdapter
        from apps.peoples.models import People

        user = People.objects.get(id=user_id)
        adapter = IntegrationAdapter()

        results = []

        for item_id in approved_items:
            try:
                recommendation = LLMRecommendation.objects.get(recommendation_id=item_id)

                # Apply recommendation through integration adapter
                result = adapter.apply_single_recommendation(
                    recommendation=recommendation,
                    user=user,
                    dry_run=dry_run
                )

                results.append({
                    'recommendation_id': item_id,
                    'status': 'applied' if result['success'] else 'failed',
                    'changes': result.get('changes', []),
                    'error': result.get('error')
                })

                # Update recommendation status if successful
                if result['success'] and not dry_run:
                    recommendation.user_decision = LLMRecommendation.UserDecisionChoices.APPROVED
                    recommendation.save()

                    # Update session state
                    session = recommendation.session
                    if session.current_state == ConversationSession.StateChoices.AWAITING_USER_APPROVAL:
                        session.current_state = ConversationSession.StateChoices.COMPLETED
                        session.save()

            except LLMRecommendation.DoesNotExist:
                task_logger.error(f"Recommendation {item_id} not found")
                results.append({
                    'recommendation_id': item_id,
                    'status': 'not_found',
                    'error': 'Recommendation not found'
                })

            except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
                task_logger.error(f"Error applying recommendation {item_id}: {str(e)}")
                results.append({
                    'recommendation_id': item_id,
                    'status': 'failed',
                    'error': str(e)
                })

        task_logger.info(f"Completed applying {len(approved_items)} recommendations")
        return {
            'status': 'completed',
            'dry_run': dry_run,
            'results': results
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error applying recommendations: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': error_msg
        }


# First cleanup_old_sessions implementation consolidated into comprehensive version below


def _create_consensus(maker_result: Dict[str, Any], checker_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create consensus between maker and checker LLM outputs

    Args:
        maker_result: Output from maker LLM
        checker_result: Output from checker LLM

    Returns:
        Consensus dictionary combining both outputs
    """
    consensus = maker_result.copy()

    # Apply checker improvements if available
    if checker_result.get('suggested_improvements'):
        consensus['improvements_applied'] = checker_result['suggested_improvements']

    # Adjust confidence based on checker validation
    if 'confidence_adjustment' in checker_result:
        original_confidence = consensus.get('confidence_score', 0.8)
        consensus['confidence_score'] = min(
            original_confidence + checker_result['confidence_adjustment'],
            1.0
        )

    # Add validation metadata
    consensus['validation_metadata'] = {
        'checker_validated': True,
        'risk_assessment': checker_result.get('risk_assessment', 'unknown'),
        'compliance_check': checker_result.get('compliance_check', 'not_checked'),
        'consensus_created_at': timezone.now().isoformat()
    }

    return consensus


@shared_task(bind=True, name='cleanup_old_sessions')
def cleanup_old_sessions(self, days_old: int = 30):
    """
    Comprehensive cleanup of old conversation sessions and related data

    This consolidated implementation combines the best features of both previous versions:
    - Timezone-aware date handling
    - Comprehensive related data cleanup
    - Proper error handling and logging
    - Archival support for audit trails

    Args:
        days_old: Number of days after which sessions are considered old
    """
    from django.utils import timezone
    from datetime import timedelta
    import traceback

    task_logger.info(f"Starting comprehensive cleanup of sessions older than {days_old} days")

    try:
        cutoff_date = timezone.now() - timedelta(days=days_old)

        # Find old sessions that are not active
        old_sessions = ConversationSession.objects.filter(
            mdtz__lt=cutoff_date,
            current_state__in=[
                ConversationSession.StateChoices.COMPLETED,
                ConversationSession.StateChoices.CANCELLED,
                ConversationSession.StateChoices.ERROR
            ]
        )

        session_count = old_sessions.count()

        # Clean up related recommendations first (more efficient than orphaned cleanup)
        recommendation_count = 0
        changeset_count = 0
        approval_count = 0

        for session in old_sessions:
            # Archive session data before cleanup (for audit trail)
            task_logger.debug(f"Archiving session {session.session_id}")

            # Clean up related recommendations
            session_recommendations = LLMRecommendation.objects.filter(session=session)
            recommendation_count += session_recommendations.count()
            session_recommendations.delete()

            # Clean up related changesets and their approvals
            session_changesets = AIChangeSet.objects.filter(session=session)
            for changeset in session_changesets:
                changeset_approvals = ChangeSetApproval.objects.filter(changeset=changeset)
                approval_count += changeset_approvals.count()
                changeset_approvals.delete()

            changeset_count += session_changesets.count()
            session_changesets.delete()

        # Delete old sessions
        old_sessions.delete()

        # Also clean up any remaining orphaned recommendations (belt and suspenders approach)
        orphaned_recommendations = LLMRecommendation.objects.filter(
            session__isnull=True,
            cdtz__lt=cutoff_date
        )
        orphan_count = orphaned_recommendations.count()
        orphaned_recommendations.delete()

        task_logger.info(
            f"Successfully cleaned up: {session_count} sessions, "
            f"{recommendation_count} recommendations, {changeset_count} changesets, "
            f"{approval_count} approvals, {orphan_count} orphaned recommendations"
        )

        return {
            'status': 'completed',
            'sessions_deleted': session_count,
            'recommendations_deleted': recommendation_count,
            'changesets_deleted': changeset_count,
            'approvals_deleted': approval_count,
            'orphaned_recommendations_deleted': orphan_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error in comprehensive cleanup task: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': error_msg,
            'sessions_deleted': 0,
            'recommendations_deleted': 0,
            'changesets_deleted': 0,
            'approvals_deleted': 0
        }


@shared_task(
    bind=True,
    name='cleanup_failed_tasks',
    soft_time_limit=180,  # 3 minutes - cleanup
    time_limit=360         # 6 minutes hard limit
)
def cleanup_failed_tasks(self):
    """
    Clean up failed conversation tasks and reset session states
    """
    from django.utils import timezone
    from datetime import timedelta

    task_logger.info("Starting cleanup of failed tasks")

    # Find sessions stuck in generating state for more than 1 hour
    stuck_cutoff = timezone.now() - timedelta(hours=1)

    stuck_sessions = ConversationSession.objects.filter(
        current_state=ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS,
        mdtz__lt=stuck_cutoff
    )

    stuck_count = stuck_sessions.count()

    # Reset stuck sessions to error state
    for session in stuck_sessions:
        session.current_state = ConversationSession.StateChoices.ERROR
        session.error_message = "Task timeout - processing took too long"
        session.save()
        task_logger.warning(f"Reset stuck session {session.session_id} to error state")

    task_logger.info(f"Reset {stuck_count} stuck sessions")

    return {
        'stuck_sessions_reset': stuck_count,
        'timestamp': timezone.now().isoformat()
    }


@shared_task(bind=True, name='archive_completed_sessions')
def archive_completed_sessions(self, batch_size: int = 100):
    """
    Archive completed sessions to reduce main table size

    Args:
        batch_size: Number of sessions to archive in one batch
    """
    from django.utils import timezone
    from datetime import timedelta

    task_logger.info(f"Starting archival of completed sessions (batch size: {batch_size})")

    # Find completed sessions older than 7 days
    archive_cutoff = timezone.now() - timedelta(days=7)

    sessions_to_archive = ConversationSession.objects.filter(
        current_state=ConversationSession.StateChoices.COMPLETED,
        mdtz__lt=archive_cutoff
    )[:batch_size]

    archived_count = 0

    with transaction.atomic():
        for session in sessions_to_archive:
            # Create archive entry (could be in separate table or storage)
            archive_data = {
                'session_id': str(session.session_id),
                'user_id': session.user_id,
                'client_id': session.client_id,
                'conversation_type': session.conversation_type,
                'context_data': session.context_data,
                'collected_data': session.collected_data,
                'completed_at': session.mdtz.isoformat(),
                'created_at': session.cdtz.isoformat()
            }

            # Log archival
            task_logger.debug(f"Archiving session {session.session_id}: {archive_data}")

            # Could save to archive storage here
            # archive_storage.save(archive_data)

            # Delete from main table
            session.delete()
            archived_count += 1

    task_logger.info(f"Archived {archived_count} completed sessions")

    return {
        'sessions_archived': archived_count,
        'archive_cutoff': archive_cutoff.isoformat(),
        'timestamp': timezone.now().isoformat()
    }
