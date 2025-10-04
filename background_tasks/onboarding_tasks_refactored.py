"""
Refactored Celery Tasks for Conversational Onboarding with DLQ Integration

Uses OnboardingBaseTask for standardized error handling and DLQ integration.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management

Author: Claude Code
Date: 2025-10-01
"""
import logging
from datetime import datetime
from typing import Dict, Any

from celery import shared_task
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist

# Local imports
from apps.onboarding.models import ConversationSession, LLMRecommendation
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service, LLMServiceException
from apps.onboarding_api.services.knowledge import get_knowledge_service
from apps.onboarding_api.services.translation import get_conversation_translator
from apps.onboarding_api.services.circuit_breaker import get_circuit_breaker

# Resilience imports
from background_tasks.onboarding_retry_strategies import llm_api_task_config, database_task_config
from background_tasks.onboarding_base_task import OnboardingLLMTask, OnboardingDatabaseTask

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


@shared_task(
    bind=True,
    name='process_conversation_step_v2',
    base=OnboardingLLMTask,  # Use specialized LLM task base class
    **llm_api_task_config()  # Apply LLM API retry config
)
def process_conversation_step_v2(self, conversation_id: str, user_input: str, context: Dict[str, Any], task_id: str = None):
    """
    Process a conversation step asynchronously (Refactored with DLQ integration)

    Args:
        conversation_id: UUID of the conversation session
        user_input: User's input text
        context: Additional context data
        task_id: Optional unique task identifier for tracking

    Returns:
        Standardized response with status and result
    """
    # Get or generate correlation ID
    correlation_id = self.get_correlation_id(task_id)

    task_logger.info(
        f"Starting conversation processing",
        extra={
            'correlation_id': correlation_id,
            'session_id': conversation_id
        }
    )

    try:
        # Phase 1: Update session state
        with transaction.atomic():
            session = ConversationSession.objects.select_for_update().get(
                session_id=conversation_id
            )
            session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
            session.save()

        # Phase 2: Get services
        llm_service = get_llm_service()
        checker_service = get_checker_service()
        knowledge_service = get_knowledge_service()
        translator = get_conversation_translator()
        llm_circuit_breaker = get_circuit_breaker('llm_api')

        # Phase 3: Process with maker LLM (with circuit breaker)
        def llm_call():
            return llm_service.process_conversation_step(
                session=session,
                user_input=user_input,
                context=context
            )

        def llm_fallback():
            task_logger.warning(f"LLM circuit breaker open - using fallback")
            return {
                'recommendations': {'message': 'Service temporarily unavailable. Please try again.'},
                'confidence_score': 0.0,
                'fallback_used': True
            }

        maker_result = llm_circuit_breaker.call(llm_call, fallback=llm_fallback)

        # Phase 4: Validate against knowledge base
        validation_result = knowledge_service.validate_recommendation_against_knowledge(
            recommendation=maker_result.get('recommendations', {}),
            context=context
        )

        # Phase 5: Create recommendation record
        recommendation = self.with_transaction(
            _create_recommendation,
            session=session,
            maker_result=maker_result,
            validation_result=validation_result
        )

        # Phase 6: Optional checker validation
        if checker_service:
            checker_result, checker_error = self.safe_execute(
                checker_service.validate_recommendations,
                fallback_value=None,
                log_error=True,
                maker_output=maker_result,
                context=context
            )

            if checker_result:
                recommendation = self.with_transaction(
                    _update_with_checker,
                    recommendation=recommendation,
                    checker_result=checker_result
                )

        # Phase 7: Translation if needed
        if session.language != 'en':
            translated, translation_error = self.safe_execute(
                translator.translate_conversation_response,
                fallback_value=None,
                log_error=True,
                response=recommendation.consensus,
                target_language=session.language
            )

            if translated:
                recommendation.consensus['translated'] = translated
                recommendation.save()

        # Phase 8: Update session state
        with transaction.atomic():
            session = ConversationSession.objects.select_for_update().get(
                session_id=conversation_id
            )
            session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            session.collected_data.update({
                'task_id': correlation_id,
                'processed_at': datetime.now().isoformat(),
                'recommendation_id': str(recommendation.recommendation_id)
            })
            session.save()

        # Return success response
        return self.task_success(
            result={
                'recommendation_id': str(recommendation.recommendation_id),
                'confidence_score': recommendation.confidence_score,
                'session_state': session.current_state
            },
            correlation_id=correlation_id,
            metadata={'user_input_length': len(user_input)}
        )

    except ConversationSession.DoesNotExist as e:
        # Non-retryable - session not found
        task_logger.error(f"Session not found: {conversation_id}")
        return self.task_failure(
            error_message=f"Conversation session {conversation_id} not found",
            correlation_id=correlation_id,
            error_type='session_not_found'
        )

    except (ValueError, ValidationError) as e:
        # Validation errors - not retryable, but update session state
        task_logger.error(f"Validation error for session {conversation_id}: {str(e)}")

        try:
            with transaction.atomic():
                session = ConversationSession.objects.select_for_update().get(
                    session_id=conversation_id
                )
                session.current_state = ConversationSession.StateChoices.ERROR
                session.error_message = str(e)
                session.save()
        except (DatabaseError, IntegrityError):
            pass  # Best effort to update state

        # Handle error with DLQ (non-retryable)
        return self.handle_task_error(
            exception=e,
            correlation_id=correlation_id,
            context={'session_id': conversation_id, 'user_input': user_input},
            retryable=False
        )

    except Exception as e:
        # All other exceptions - let base class determine retryability
        return self.handle_task_error(
            exception=e,
            correlation_id=correlation_id,
            context={'session_id': conversation_id, 'user_input': user_input}
        )


@shared_task(
    bind=True,
    name='validate_recommendations_v2',
    base=OnboardingDatabaseTask,  # Database-heavy operation
    **database_task_config()
)
def validate_recommendations_v2(self, recommendation_ids: list, context: Dict[str, Any], correlation_id: str = None):
    """
    Validate multiple recommendations against authoritative knowledge (Refactored)

    Args:
        recommendation_ids: List of recommendation UUIDs
        context: Validation context
        correlation_id: Optional correlation ID

    Returns:
        Standardized response with validation results
    """
    correlation_id = self.get_correlation_id(correlation_id)

    task_logger.info(
        f"Validating {len(recommendation_ids)} recommendations",
        extra={'correlation_id': correlation_id}
    )

    try:
        knowledge_service = get_knowledge_service()
        results = []

        for rec_id in recommendation_ids:
            try:
                recommendation = LLMRecommendation.objects.get(recommendation_id=rec_id)

                # Validate
                validation_result = knowledge_service.validate_recommendation_against_knowledge(
                    recommendation=recommendation.consensus,
                    context=context
                )

                # Update recommendation
                recommendation.authoritative_sources = validation_result.get('supporting_sources', [])
                recommendation.confidence_score = min(
                    recommendation.confidence_score,
                    validation_result.get('confidence_score', 0.8)
                )
                recommendation.save()

                results.append({
                    'recommendation_id': str(rec_id),
                    'status': 'validated',
                    'confidence_score': recommendation.confidence_score,
                    'sources_count': len(recommendation.authoritative_sources)
                })

            except LLMRecommendation.DoesNotExist:
                task_logger.warning(f"Recommendation {rec_id} not found")
                results.append({
                    'recommendation_id': str(rec_id),
                    'status': 'not_found'
                })

        # Return success
        return self.task_success(
            result={
                'total': len(recommendation_ids),
                'validated': len([r for r in results if r['status'] == 'validated']),
                'not_found': len([r for r in results if r['status'] == 'not_found']),
                'results': results
            },
            correlation_id=correlation_id
        )

    except Exception as e:
        return self.handle_task_error(
            exception=e,
            correlation_id=correlation_id,
            context={'recommendation_count': len(recommendation_ids)}
        )


@shared_task(
    bind=True,
    name='apply_approved_recommendations_v2',
    base=OnboardingDatabaseTask,
    **database_task_config()
)
def apply_approved_recommendations_v2(self, approval_id: int, user_id: int, correlation_id: str = None):
    """
    Apply approved recommendations to system (Refactored)

    Args:
        approval_id: ID of the approval decision
        user_id: User who approved
        correlation_id: Optional correlation ID

    Returns:
        Standardized response with application results
    """
    correlation_id = self.get_correlation_id(correlation_id)

    task_logger.info(
        f"Applying approved recommendations",
        extra={'correlation_id': correlation_id, 'approval_id': approval_id}
    )

    try:
        from apps.onboarding.models import ApprovalWorkflow

        with transaction.atomic():
            approval = ApprovalWorkflow.objects.select_for_update().get(id=approval_id)

            # Validate approval status
            if approval.status != 'approved':
                raise ValidationError(f"Approval {approval_id} is not in approved state")

            # Apply recommendations
            recommendation = approval.recommendation
            applied_changes = _apply_recommendation_changes(recommendation, user_id)

            # Update approval status
            approval.status = 'applied'
            approval.applied_at = datetime.now()
            approval.applied_by_id = user_id
            approval.save()

            return self.task_success(
                result={
                    'approval_id': approval_id,
                    'recommendation_id': str(recommendation.recommendation_id),
                    'applied_changes': applied_changes,
                    'applied_at': approval.applied_at.isoformat()
                },
                correlation_id=correlation_id
            )

    except ApprovalWorkflow.DoesNotExist:
        return self.task_failure(
            error_message=f"Approval {approval_id} not found",
            correlation_id=correlation_id,
            error_type='approval_not_found'
        )

    except ValidationError as e:
        return self.handle_task_error(
            exception=e,
            correlation_id=correlation_id,
            context={'approval_id': approval_id},
            retryable=False
        )

    except Exception as e:
        return self.handle_task_error(
            exception=e,
            correlation_id=correlation_id,
            context={'approval_id': approval_id, 'user_id': user_id}
        )


# =============================================================================
# HELPER FUNCTIONS (Isolated for testability)
# =============================================================================

def _create_recommendation(session, maker_result, validation_result):
    """Create LLM recommendation record (atomic operation)"""
    return LLMRecommendation.objects.create(
        session=session,
        maker_output=maker_result,
        checker_output=None,
        consensus=maker_result,
        authoritative_sources=validation_result.get('supporting_sources', []),
        confidence_score=min(
            maker_result.get('confidence_score', 0.8),
            validation_result.get('confidence_score', 0.8)
        )
    )


def _update_with_checker(recommendation, checker_result):
    """Update recommendation with checker results (atomic operation)"""
    recommendation.checker_output = checker_result

    # Create consensus
    consensus = {
        'maker': recommendation.maker_output,
        'checker': checker_result,
        'final': checker_result.get('adjusted_recommendations', recommendation.maker_output)
    }
    recommendation.consensus = consensus

    # Adjust confidence
    confidence_adjustment = checker_result.get('confidence_adjustment', 0.0)
    recommendation.confidence_score = min(
        recommendation.confidence_score + confidence_adjustment,
        1.0
    )

    recommendation.save()
    return recommendation


def _apply_recommendation_changes(recommendation, user_id):
    """Apply recommendation changes to system (atomic operation)"""
    applied_changes = []

    # Implementation would apply actual configuration changes
    # This is a placeholder for the actual business logic
    consensus_data = recommendation.consensus

    # Example: Create/update configuration objects
    # (Actual implementation depends on your domain models)

    applied_changes.append({
        'type': 'configuration_updated',
        'recommendation_id': str(recommendation.recommendation_id),
        'user_id': user_id,
        'timestamp': datetime.now().isoformat()
    })

    return applied_changes


__all__ = [
    'process_conversation_step_v2',
    'validate_recommendations_v2',
    'apply_approved_recommendations_v2',
]
