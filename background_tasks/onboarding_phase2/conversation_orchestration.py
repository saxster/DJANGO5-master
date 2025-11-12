"""
Conversation Orchestration Tasks
Enhanced conversational onboarding with dual-LLM chain orchestration
"""
import logging
import traceback
import time
from typing import Dict, Any

from celery import shared_task, chain
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

# Local imports
from apps.core_onboarding.models import ConversationSession, LLMRecommendation
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service, get_consensus_engine
from apps.onboarding_api.services.knowledge import get_knowledge_service
from apps.onboarding_api.services.translation import get_conversation_translator

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


@shared_task(bind=True, name='process_conversation_step_enhanced')
def process_conversation_step_enhanced(
    self,
    conversation_id: str,
    user_input: str,
    context: Dict[str, Any],
    trace_id: str,
    user_id: int
):
    """
    Phase 2 Enhanced conversation processing with full orchestration chain
    Chain: retrieve_knowledge → maker_generate → checker_validate → consensus → persist → notify
    """
    task_logger.info(f"Starting enhanced conversation processing {trace_id} for session {conversation_id}")

    try:
        # Build orchestration chain
        workflow = chain(
            retrieve_knowledge_task.si(conversation_id, user_input, context, trace_id),
            maker_generate_task.s(conversation_id, user_input, context, trace_id),
            checker_validate_task.s(conversation_id, context, trace_id),
            compute_consensus_task.s(conversation_id, context, trace_id),
            persist_recommendations_task.s(conversation_id, trace_id, user_id),
            notify_completion_task.s(conversation_id, trace_id)
        )

        # Execute the chain
        result = workflow.apply_async()

        return {
            'status': 'chain_started',
            'trace_id': trace_id,
            'chain_id': result.id
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error starting enhanced processing chain {trace_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Update session to error state
        try:
            with transaction.atomic():
                session = ConversationSession.objects.select_for_update().get(
                    session_id=conversation_id
                )
                session.current_state = ConversationSession.StateChoices.ERROR
                session.error_message = str(e)
                session.save()
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as session_error:
            task_logger.error(f"Failed to update session error state: {str(session_error)}")

        return {
            'status': 'chain_failed',
            'error': error_msg,
            'trace_id': trace_id
        }


@shared_task(bind=True, name='retrieve_knowledge_task')
def retrieve_knowledge_task(self, conversation_id: str, user_input: str, context: Dict[str, Any], trace_id: str):
    """
    Step 1: Retrieve relevant knowledge for grounding
    """
    task_logger.info(f"Retrieving knowledge for trace {trace_id}")

    try:
        knowledge_service = get_knowledge_service()

        # Enhanced knowledge retrieval with filtering
        authority_filter = context.get('authority_filter', ['high', 'official'])
        top_k = context.get('knowledge_top_k', 8)

        knowledge_hits = knowledge_service.search_with_reranking(
            query=user_input,
            top_k=top_k,
            authority_filter=authority_filter
        )

        task_logger.info(f"Retrieved {len(knowledge_hits)} knowledge hits for trace {trace_id}")

        return {
            'knowledge_hits': knowledge_hits,
            'retrieval_metadata': {
                'query': user_input,
                'hits_count': len(knowledge_hits),
                'authority_filter': authority_filter,
                'retrieved_at': timezone.now().isoformat()
            }
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Knowledge retrieval failed for trace {trace_id}: {str(e)}"
        task_logger.error(error_msg)
        return {
            'knowledge_hits': [],
            'retrieval_metadata': {'error': str(e)},
            'retrieval_failed': True
        }


@shared_task(bind=True, name='maker_generate_task')
def maker_generate_task(
    self,
    retrieval_result: Dict[str, Any],
    conversation_id: str,
    user_input: str,
    context: Dict[str, Any],
    trace_id: str
):
    """
    Step 2: Generate recommendations with Maker LLM using retrieved knowledge
    """
    task_logger.info(f"Generating with Maker LLM for trace {trace_id}")

    try:
        # Get session
        session = ConversationSession.objects.get(session_id=conversation_id)

        # Update state
        session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
        session.save()

        # Get services
        llm_service = get_llm_service()

        # Enhance context with retrieved knowledge
        enhanced_context = context.copy()
        enhanced_context['knowledge_grounding'] = retrieval_result.get('knowledge_hits', [])

        # Generate with maker LLM
        start_time = time.time()
        maker_result = llm_service.process_conversation_step(
            session=session,
            user_input=user_input,
            context=enhanced_context
        )
        generation_time = int((time.time() - start_time) * 1000)

        task_logger.info(f"Maker LLM completed for trace {trace_id} in {generation_time}ms")

        return {
            'maker_output': maker_result,
            'knowledge_hits': retrieval_result.get('knowledge_hits', []),
            'maker_metadata': {
                'generation_time_ms': generation_time,
                'confidence_score': maker_result.get('confidence_score', 0.0),
                'generated_at': timezone.now().isoformat()
            }
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Maker LLM failed for trace {trace_id}: {str(e)}"
        task_logger.error(error_msg)
        return {
            'maker_output': {'error': str(e)},
            'knowledge_hits': retrieval_result.get('knowledge_hits', []),
            'maker_failed': True
        }


@shared_task(bind=True, name='checker_validate_task')
def checker_validate_task(
    self,
    maker_result: Dict[str, Any],
    conversation_id: str,
    context: Dict[str, Any],
    trace_id: str
):
    """
    Step 3: Validate recommendations with Checker LLM
    """
    task_logger.info(f"Validating with Checker LLM for trace {trace_id}")

    try:
        checker_service = get_checker_service()

        if not checker_service:
            task_logger.info(f"Checker LLM not enabled for trace {trace_id}")
            return {
                'maker_output': maker_result.get('maker_output', {}),
                'checker_output': None,
                'knowledge_hits': maker_result.get('knowledge_hits', []),
                'checker_skipped': True
            }

        # Validate with checker LLM
        start_time = time.time()
        checker_result = checker_service.validate_recommendations(
            maker_output=maker_result.get('maker_output', {}),
            context=context
        )
        validation_time = int((time.time() - start_time) * 1000)

        task_logger.info(f"Checker LLM completed for trace {trace_id} in {validation_time}ms")

        return {
            'maker_output': maker_result.get('maker_output', {}),
            'checker_output': checker_result,
            'knowledge_hits': maker_result.get('knowledge_hits', []),
            'checker_metadata': {
                'validation_time_ms': validation_time,
                'is_valid': checker_result.get('is_valid', True),
                'validated_at': timezone.now().isoformat()
            }
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Checker LLM failed for trace {trace_id}: {str(e)}"
        task_logger.error(error_msg)
        return {
            'maker_output': maker_result.get('maker_output', {}),
            'checker_output': {'error': str(e)},
            'knowledge_hits': maker_result.get('knowledge_hits', []),
            'checker_failed': True
        }


@shared_task(bind=True, name='compute_consensus_task')
def compute_consensus_task(
    self,
    validation_result: Dict[str, Any],
    conversation_id: str,
    context: Dict[str, Any],
    trace_id: str
):
    """
    Step 4: Compute consensus between maker and checker with knowledge grounding
    """
    task_logger.info(f"Computing consensus for trace {trace_id}")

    try:
        consensus_engine = get_consensus_engine()

        # Extract components
        maker_output = validation_result.get('maker_output', {})
        checker_output = validation_result.get('checker_output', {})
        knowledge_hits = validation_result.get('knowledge_hits', [])

        # Compute consensus
        start_time = time.time()
        consensus = consensus_engine.create_consensus(
            maker_output=maker_output,
            checker_output=checker_output,
            knowledge_hits=knowledge_hits,
            context=context
        )
        consensus_time = int((time.time() - start_time) * 1000)

        task_logger.info(f"Consensus computed for trace {trace_id} in {consensus_time}ms")

        return {
            'maker_output': maker_output,
            'checker_output': checker_output,
            'consensus': consensus,
            'knowledge_hits': knowledge_hits,
            'consensus_metadata': {
                'computation_time_ms': consensus_time,
                'decision': consensus.get('decision', 'needs_review'),
                'confidence': consensus.get('consensus_confidence', 0.0),
                'computed_at': timezone.now().isoformat()
            }
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Consensus computation failed for trace {trace_id}: {str(e)}"
        task_logger.error(error_msg)
        return {
            'maker_output': validation_result.get('maker_output', {}),
            'checker_output': validation_result.get('checker_output', {}),
            'consensus': {'error': str(e), 'decision': 'escalate'},
            'knowledge_hits': validation_result.get('knowledge_hits', []),
            'consensus_failed': True
        }


@shared_task(bind=True, name='persist_recommendations_task')
def persist_recommendations_task(
    self,
    consensus_result: Dict[str, Any],
    conversation_id: str,
    trace_id: str,
    user_id: int
):
    """
    Step 5: Persist recommendations to database with full metadata
    """
    task_logger.info(f"Persisting recommendations for trace {trace_id}")

    try:
        with transaction.atomic():
            # Get session
            session = ConversationSession.objects.select_for_update().get(
                session_id=conversation_id
            )

            # Calculate total processing time
            total_times = [
                consensus_result.get('consensus_metadata', {}).get('computation_time_ms', 0),
                consensus_result.get('checker_metadata', {}).get('validation_time_ms', 0),
                consensus_result.get('maker_metadata', {}).get('generation_time_ms', 0)
            ]
            total_latency = sum(filter(None, total_times))

            # Determine final status based on consensus decision
            decision = consensus_result.get('consensus', {}).get('decision', 'needs_review')
            final_status = {
                'approve': LLMRecommendation.StatusChoices.COMPLETED,
                'modify': LLMRecommendation.StatusChoices.NEEDS_REVIEW,
                'escalate': LLMRecommendation.StatusChoices.NEEDS_REVIEW,
                'needs_review': LLMRecommendation.StatusChoices.NEEDS_REVIEW
            }.get(decision, LLMRecommendation.StatusChoices.NEEDS_REVIEW)

            # Create comprehensive recommendation record
            recommendation = LLMRecommendation.objects.create(
                session=session,
                maker_output=consensus_result.get('maker_output', {}),
                checker_output=consensus_result.get('checker_output', {}),
                consensus=consensus_result.get('consensus', {}),
                authoritative_sources=consensus_result.get('knowledge_hits', []),
                confidence_score=consensus_result.get('consensus', {}).get('consensus_confidence', 0.0),
                status=final_status,
                latency_ms=total_latency,
                trace_id=trace_id,
                eval_scores={
                    'maker_confidence': consensus_result.get('maker_metadata', {}).get('confidence_score', 0.0),
                    'checker_valid': consensus_result.get('checker_metadata', {}).get('is_valid', True),
                    'consensus_confidence': consensus_result.get('consensus', {}).get('consensus_confidence', 0.0),
                    'knowledge_sources': len(consensus_result.get('knowledge_hits', [])),
                    'processing_steps': {
                        'knowledge_retrieval': not consensus_result.get('retrieval_failed', False),
                        'maker_generation': not consensus_result.get('maker_failed', False),
                        'checker_validation': not consensus_result.get('checker_failed', False),
                        'consensus_computation': not consensus_result.get('consensus_failed', False)
                    }
                }
            )

            # Update session state
            if decision == 'approve':
                session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            elif decision in ['modify', 'needs_review']:
                session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            else:  # escalate
                session.current_state = ConversationSession.StateChoices.ERROR
                session.error_message = "Escalation required based on consensus analysis"

            # Update session data
            session.collected_data.update({
                'trace_id': trace_id,
                'recommendation_id': str(recommendation.recommendation_id),
                'final_decision': decision,
                'processing_completed_at': timezone.now().isoformat(),
                'total_latency_ms': total_latency
            })
            session.save()

        task_logger.info(f"Successfully persisted recommendation {recommendation.recommendation_id} for trace {trace_id}")

        return {
            'recommendation_id': str(recommendation.recommendation_id),
            'session_state': session.current_state,
            'final_decision': decision,
            'confidence_score': recommendation.confidence_score,
            'total_latency_ms': total_latency
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Failed to persist recommendations for trace {trace_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Update session to error state
        try:
            with transaction.atomic():
                session = ConversationSession.objects.select_for_update().get(
                    session_id=conversation_id
                )
                session.current_state = ConversationSession.StateChoices.ERROR
                session.error_message = str(e)
                session.save()
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as session_error:
            task_logger.error(f"Failed to update session error state: {str(session_error)}")

        return {'error': error_msg, 'persist_failed': True}


@shared_task(bind=True, name='notify_completion_task')
def notify_completion_task(self, persist_result: Dict[str, Any], conversation_id: str, trace_id: str):
    """
    Step 6: Notify completion and perform any post-processing
    """
    task_logger.info(f"Notifying completion for trace {trace_id}")

    try:
        if persist_result.get('persist_failed'):
            task_logger.error(f"Cannot notify completion - persistence failed for trace {trace_id}")
            return {'notification_skipped': True, 'reason': 'persistence_failed'}

        # Get final recommendation
        recommendation_id = persist_result.get('recommendation_id')
        if recommendation_id:
            recommendation = LLMRecommendation.objects.get(recommendation_id=recommendation_id)

            # Translate if needed
            try:
                session = recommendation.session
                if session.language != 'en':
                    translator = get_conversation_translator()
                    translated_consensus = translator.translate_conversation_response(
                        recommendation.consensus,
                        session.language
                    )
                    recommendation.consensus['translated'] = translated_consensus
                    recommendation.save()
            except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
                task_logger.warning(f"Translation failed for trace {trace_id}: {str(e)}")

        # Future: Send notifications, webhooks, etc.
        # For Phase 2, just log completion
        task_logger.info(f"Processing chain completed successfully for trace {trace_id}")

        return {
            'status': 'completed',
            'recommendation_id': recommendation_id,
            'final_state': persist_result.get('session_state'),
            'completed_at': timezone.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Notification failed for trace {trace_id}: {str(e)}"
        task_logger.error(error_msg)
        return {'notification_failed': True, 'error': str(e)}


# Define exception classes for imports
class IntegrationException(Exception):
    """Integration exception placeholder"""
    pass


class LLMServiceException(Exception):
    """LLM service exception placeholder"""
    pass
