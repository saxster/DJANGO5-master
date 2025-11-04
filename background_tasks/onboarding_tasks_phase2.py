"""
Phase 2 Celery tasks for Enhanced Conversational Onboarding
Advanced orchestration chains with dual-LLM and RAG
"""
import logging
import traceback
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from celery import shared_task, chain, chord, group
from django.conf import settings
from django.db import transaction
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError

# Local imports
from apps.core_onboarding.models import ConversationSession, LLMRecommendation, AuthoritativeKnowledge
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service, get_consensus_engine
from apps.onboarding_api.services.knowledge import get_knowledge_service, get_embedding_generator
from apps.onboarding_api.services.translation import get_conversation_translator

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


# =============================================================================
# PHASE 2: ENHANCED ORCHESTRATION CHAINS
# =============================================================================


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
                'retrieved_at': datetime.now().isoformat()
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
                'generated_at': datetime.now().isoformat()
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
                'validated_at': datetime.now().isoformat()
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
                'computed_at': datetime.now().isoformat()
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
                'processing_completed_at': datetime.now().isoformat(),
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
            'completed_at': datetime.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Notification failed for trace {trace_id}: {str(e)}"
        task_logger.error(error_msg)
        return {'notification_failed': True, 'error': str(e)}


# =============================================================================
# KNOWLEDGE MANAGEMENT TASKS
# =============================================================================


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
                'embedded_at': datetime.now().isoformat()
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
                knowledge = AuthoritativeKnowledge.objects.get(knowledge_id=knowledge_id)
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


# =============================================================================
# MAINTENANCE AND MONITORING TASKS
# =============================================================================


@shared_task(bind=True, name='cleanup_old_traces_task')
def cleanup_old_traces_task(self, days_old: int = 30):
    """
    Clean up old trace data and recommendations
    """
    task_logger.info(f"Cleaning up traces older than {days_old} days")

    try:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)

        # Clean up old recommendations
        old_recommendations = LLMRecommendation.objects.filter(
            cdtz__lt=cutoff_date,
            status__in=[
                LLMRecommendation.StatusChoices.COMPLETED,
                LLMRecommendation.StatusChoices.FAILED
            ]
        )

        recommendation_count = old_recommendations.count()
        old_recommendations.delete()

        task_logger.info(f"Cleaned up {recommendation_count} old recommendations")

        return {
            'status': 'completed',
            'recommendations_deleted': recommendation_count,
            'cleanup_date': cutoff_date.isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error in cleanup task: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@shared_task(bind=True, name='validate_knowledge_freshness_task')
def validate_knowledge_freshness_task(self):
    """
    Validate freshness of knowledge base and flag stale documents
    """
    task_logger.info("Validating knowledge base freshness")

    try:
        from datetime import timedelta

        # Flag documents older than 2 years as potentially stale
        stale_threshold = datetime.now() - timedelta(days=730)

        stale_documents = AuthoritativeKnowledge.objects.filter(
            publication_date__lt=stale_threshold,
            is_current=True
        )

        stale_count = 0
        for doc in stale_documents:
            # Flag for review but don't automatically disable
            doc.content_summary += " [FLAGGED: May need freshness review]"
            doc.save()
            stale_count += 1

        task_logger.info(f"Flagged {stale_count} documents for freshness review")

        return {
            'status': 'completed',
            'documents_flagged': stale_count,
            'review_threshold': stale_threshold.isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Error in freshness validation: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': str(e)
        }


# =============================================================================
# PRODUCTION-GRADE DOCUMENT INGESTION PIPELINE
# =============================================================================


@shared_task(bind=True, name='ingest_document')
def ingest_document(self, job_id: str):
    """
    Complete document ingestion pipeline: fetch→parse→chunk→embed→index
    """
    task_logger.info(f"Starting document ingestion for job {job_id}")

    try:
        from apps.core_onboarding.models import KnowledgeIngestionJob, AuthoritativeKnowledge
        from apps.onboarding_api.services.knowledge import (
            get_document_fetcher,
            get_document_parser,
            get_document_chunker,
            get_embedding_generator,
            get_vector_store
        )

        # Get ingestion job
        job = KnowledgeIngestionJob.objects.get(job_id=job_id)
        start_time = time.time()

        # Stage 1: Fetch document
        task_logger.info(f"Stage 1: Fetching document from {job.source_url}")
        job.update_status(KnowledgeIngestionJob.StatusChoices.FETCHING)

        fetcher = get_document_fetcher()
        fetch_start = time.time()
        fetch_result = fetcher.fetch_document(job.source_url, job.source)
        fetch_time = int((time.time() - fetch_start) * 1000)
        job.record_timing('fetch_ms', fetch_time)

        # Stage 2: Sanitize content (SECURITY CRITICAL)
        task_logger.info(f"Stage 2: Sanitizing content (security validation)")
        from apps.onboarding_api.services.knowledge import ContentSanitizationService

        sanitizer = ContentSanitizationService()
        sanitize_start = time.time()

        try:
            sanitized_content, sanitization_report = sanitizer.sanitize_document_content(
                content=fetch_result['content'],
                mime_type=fetch_result['content_type'],
                source_url=job.source_url
            )
            sanitize_time = int((time.time() - sanitize_start) * 1000)
            job.record_timing('sanitize_ms', sanitize_time)

            task_logger.info(
                f"Content sanitized successfully: {sanitization_report['original_size_bytes']} → "
                f"{sanitization_report['sanitized_size_bytes']} bytes"
            )

            # Use sanitized content for parsing
            fetch_result['content'] = sanitized_content
            fetch_result['metadata']['sanitization_report'] = sanitization_report

        except Exception as sanitize_error:
            task_logger.error(f"Content sanitization failed: {str(sanitize_error)}")
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(sanitize_error))
            job.source.fetch_error_count += 1
            job.source.save()
            raise

        # Stage 3: Parse document
        task_logger.info(f"Stage 3: Parsing document ({fetch_result['content_type']})")
        job.update_status(KnowledgeIngestionJob.StatusChoices.PARSING)

        parser = get_document_parser()
        parse_start = time.time()
        parse_result = parser.parse_document(
            fetch_result['content'],
            fetch_result['content_type'],
            fetch_result['metadata']
        )
        parse_time = int((time.time() - parse_start) * 1000)
        job.record_timing('parse_ms', parse_time)

        # Stage 4: Create knowledge document
        document_info = parse_result.get('document_info', {})
        document = AuthoritativeKnowledge.objects.create(
            source_organization=job.source.name,
            document_title=document_info.get('title', f"Document from {job.source.name}"),
            document_version=document_info.get('version', '1.0'),
            authority_level='medium',  # Default, can be updated later
            content_summary=parse_result['full_text'][:500] + "..." if len(parse_result['full_text']) > 500 else parse_result['full_text'],
            publication_date=datetime.now(),
            source_url=job.source_url,
            doc_checksum=fetch_result['content_hash'],
            jurisdiction=job.source.jurisdiction,
            industry=','.join(job.source.industry_tags) if job.source.industry_tags else '',
            language=job.source.language,
            tags={
                'ingestion_job_id': str(job.job_id),
                'fetch_metadata': fetch_result['metadata'],
                'parse_metadata': parse_result.get('parser_metadata', {}),
                'source_type': job.source.source_type
            },
            ingestion_version=1,
            is_current=False  # SECURITY: Will be set to True ONLY after two-person approval
        )

        # Link document to job
        job.document = document
        job.save()

        # PUBLISH GATE ENFORCEMENT: Create draft review requiring two-person approval
        # This ensures NO document is published without maker-checker review
        from apps.core_onboarding.models import KnowledgeReview
        draft_review = KnowledgeReview.objects.create(
            document=document,
            status='draft',
            notes='Auto-generated review for ingested document. Requires two-person approval before publication.',
            provenance_data={
                'ingestion_job_id': str(job.job_id),
                'ingested_at': datetime.now().isoformat(),
                'ingested_by': job.created_by.email if job.created_by else 'system',
                'source': job.source.name,
                'source_type': job.source.source_type,
                'publish_gate': 'enforced'
            }
        )

        task_logger.info(
            f"PUBLISH GATE: Created draft review {draft_review.review_id} for document {document.knowledge_id}. "
            f"Requires two-person approval before publication."
        )

        # Stage 5: Chunk document
        task_logger.info(f"Stage 5: Chunking document into segments")
        job.update_status(KnowledgeIngestionJob.StatusChoices.CHUNKING)

        chunker = get_document_chunker()
        chunk_start = time.time()

        document_metadata = {
            'title': document.document_title,
            'organization': document.source_organization,
            'authority_level': document.authority_level,
            'version': document.document_version
        }

        chunks = chunker.chunk_document(
            parse_result['full_text'],
            document_metadata,
            parse_result  # Pass parsed data for enhanced chunking
        )
        chunk_time = int((time.time() - chunk_start) * 1000)
        job.record_timing('chunk_ms', chunk_time)

        # Stage 6: Generate embeddings and index
        task_logger.info(f"Stage 6: Generating embeddings for {len(chunks)} chunks")
        job.update_status(KnowledgeIngestionJob.StatusChoices.EMBEDDING)

        embedding_generator = get_embedding_generator()
        vector_store = get_vector_store()
        embed_start = time.time()

        # Generate embeddings for chunks
        embedded_chunks = []
        embeddings_generated = 0

        for i, chunk in enumerate(chunks):
            try:
                # Generate embedding
                vector = embedding_generator.generate_embedding(chunk['text'])
                chunk['vector'] = vector
                embedded_chunks.append(chunk)
                embeddings_generated += 1

                # Update progress periodically
                if (i + 1) % 10 == 0:
                    task_logger.info(f"Generated embeddings for {i + 1}/{len(chunks)} chunks")

            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                task_logger.warning(f"Failed to generate embedding for chunk {i}: {str(e)}")
                chunk['vector'] = None
                embedded_chunks.append(chunk)

        # Store chunks in vector store
        success = vector_store.store_document_chunks(str(document.knowledge_id), embedded_chunks)

        embed_time = int((time.time() - embed_start) * 1000)
        job.record_timing('embed_ms', embed_time)

        if not success:
            raise Exception("Failed to store chunks in vector store")

        # Update job completion
        total_time = int((time.time() - start_time) * 1000)
        job.status = KnowledgeIngestionJob.StatusChoices.READY
        job.chunks_created = len(chunks)
        job.embeddings_generated = embeddings_generated
        job.processing_duration_ms = total_time
        job.save()

        # Update source statistics
        job.source.total_documents_fetched += 1
        job.source.last_successful_fetch = datetime.now()
        job.source.fetch_error_count = 0  # Reset error count on success
        job.source.save()

        task_logger.info(f"Successfully ingested document {document.knowledge_id} in {total_time}ms")

        return {
            'status': 'completed',
            'job_id': str(job.job_id),
            'document_id': str(document.knowledge_id),
            'chunks_created': len(chunks),
            'embeddings_generated': embeddings_generated,
            'processing_time_ms': total_time,
            'completed_at': datetime.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Document ingestion failed for job {job_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # Update job status
        try:
            job = KnowledgeIngestionJob.objects.get(job_id=job_id)
            job.update_status(KnowledgeIngestionJob.StatusChoices.FAILED, str(e))

            # Update source error count
            job.source.fetch_error_count += 1
            job.source.save()

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as update_error:
            task_logger.error(f"Failed to update job status: {str(update_error)}")

        return {
            'status': 'failed',
            'job_id': job_id,
            'error': str(e)
        }


@shared_task(bind=True, name='reembed_document')
def reembed_document(self, knowledge_id: str, processing_config: Dict[str, Any] = None):
    """
    Re-embed existing document with updated embeddings
    """
    task_logger.info(f"Re-embedding document {knowledge_id}")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from apps.onboarding_api.services.knowledge import (
            get_document_chunker,
            get_embedding_generator,
            get_vector_store
        )

        # Get document
        document = AuthoritativeKnowledge.objects.get(knowledge_id=knowledge_id)
        start_time = time.time()

        # Use existing content or fetch fresh content
        content = document.content_summary  # Fallback - would normally fetch full content

        # Re-chunk with potentially updated configuration
        config = processing_config or {}
        chunk_size = config.get('chunk_size', 1000)
        chunk_overlap = config.get('chunk_overlap', 200)

        chunker = get_document_chunker(chunk_size, chunk_overlap)
        document_metadata = {
            'title': document.document_title,
            'organization': document.source_organization,
            'authority_level': document.authority_level,
            'version': document.document_version
        }

        # Re-chunk document
        chunks = chunker.chunk_document(content, document_metadata)

        # Generate new embeddings
        embedding_generator = get_embedding_generator()
        vector_store = get_vector_store()

        embedded_chunks = []
        embeddings_generated = 0

        for chunk in chunks:
            try:
                vector = embedding_generator.generate_embedding(chunk['text'])
                chunk['vector'] = vector
                embedded_chunks.append(chunk)
                embeddings_generated += 1
            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                task_logger.warning(f"Failed to generate embedding for chunk: {str(e)}")
                chunk['vector'] = None
                embedded_chunks.append(chunk)

        # Store new chunks (replaces old ones)
        success = vector_store.store_document_chunks(knowledge_id, embedded_chunks)

        if not success:
            raise Exception("Failed to store re-embedded chunks")

        # Update document metadata
        document.last_verified = datetime.now()
        document.ingestion_version += 1
        document.tags['reembedded_at'] = datetime.now().isoformat()
        document.tags['reembedding_config'] = config
        document.save()

        total_time = int((time.time() - start_time) * 1000)

        task_logger.info(f"Successfully re-embedded document {knowledge_id} in {total_time}ms")

        return {
            'status': 'completed',
            'knowledge_id': knowledge_id,
            'chunks_created': len(chunks),
            'embeddings_generated': embeddings_generated,
            'processing_time_ms': total_time,
            'ingestion_version': document.ingestion_version
        }

    except AuthoritativeKnowledge.DoesNotExist:
        error_msg = f"Document {knowledge_id} not found for re-embedding"
        task_logger.error(error_msg)
        return {'status': 'not_found', 'error': error_msg}

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Re-embedding failed for {knowledge_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='refresh_documents')
def refresh_documents(self, source_ids: List[str] = None, force_refresh: bool = False):
    """
    Refresh documents by checking for updates at source URLs
    """
    task_logger.info(f"Refreshing documents (force={force_refresh})")

    try:
        from apps.core_onboarding.models import KnowledgeSource, AuthoritativeKnowledge
        from apps.onboarding_api.services.knowledge import get_document_fetcher
        from datetime import timedelta

        # Get sources to refresh
        sources = KnowledgeSource.objects.filter(is_active=True)
        if source_ids:
            sources = sources.filter(source_id__in=source_ids)

        # Only check sources that haven't been checked recently (unless forced)
        if not force_refresh:
            recent_threshold = datetime.now() - timedelta(hours=6)
            sources = sources.exclude(last_fetch_attempt__gte=recent_threshold)

        refreshed_count = 0
        updated_count = 0
        error_count = 0

        fetcher = get_document_fetcher()

        for source in sources:
            try:
                # Update last attempt timestamp
                source.last_fetch_attempt = datetime.now()
                source.save()

                # Get documents from this source
                documents = AuthoritativeKnowledge.objects.filter(
                    source_organization=source.name,
                    source_url__isnull=False,
                    is_current=True
                )

                for document in documents:
                    try:
                        # Check if document needs refresh
                        if self._document_needs_refresh(document, force_refresh):
                            # Fetch current version
                            fetch_result = fetcher.fetch_document(document.source_url, source)

                            # Check if content changed
                            if fetch_result['content_hash'] != document.doc_checksum:
                                # Content changed - create new ingestion job
                                job = KnowledgeIngestionJob.objects.create(
                                    source=source,
                                    source_url=document.source_url,
                                    created_by_id=1,  # System user
                                    processing_config={'refresh': True, 'original_doc_id': str(document.knowledge_id)}
                                )

                                # Queue ingestion of updated document
                                ingest_document.delay(str(job.job_id))
                                updated_count += 1

                                task_logger.info(f"Queued refresh for updated document: {document.document_title}")

                            else:
                                # Content unchanged - just update verification timestamp
                                document.last_verified = datetime.now()
                                document.save()

                        refreshed_count += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as doc_error:
                        task_logger.warning(f"Failed to refresh document {document.knowledge_id}: {str(doc_error)}")
                        error_count += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as source_error:
                task_logger.warning(f"Failed to refresh source {source.source_id}: {str(source_error)}")
                error_count += 1

        task_logger.info(f"Document refresh completed: {refreshed_count} checked, {updated_count} updated, {error_count} errors")

        return {
            'status': 'completed',
            'documents_checked': refreshed_count,
            'documents_updated': updated_count,
            'errors': error_count,
            'completed_at': datetime.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Document refresh failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}

    def _document_needs_refresh(self, document: AuthoritativeKnowledge, force: bool = False) -> bool:
        """Check if document needs to be refreshed"""
        if force:
            return True

        # Check if last verified more than 7 days ago
        if document.last_verified:
            from datetime import timedelta
            stale_threshold = datetime.now() - timedelta(days=7)
            return document.last_verified < stale_threshold

        return True  # Never verified, needs refresh


@shared_task(bind=True, name='retire_document')
def retire_document(self, knowledge_id: str, retirement_reason: str = "Manual retirement"):
    """
    Retire a document by marking it as not current and removing embeddings
    """
    task_logger.info(f"Retiring document {knowledge_id}")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from apps.onboarding_api.services.knowledge import get_vector_store

        # Get document
        document = AuthoritativeKnowledge.objects.get(knowledge_id=knowledge_id)

        # Mark as not current
        document.is_current = False
        document.tags['retired_at'] = datetime.now().isoformat()
        document.tags['retirement_reason'] = retirement_reason
        document.save()

        # Retire all chunks
        chunk_count = document.chunks.update(is_current=False)

        # Remove embeddings
        vector_store = get_vector_store()
        vector_store.delete_embedding(knowledge_id)

        task_logger.info(f"Successfully retired document {knowledge_id} with {chunk_count} chunks")

        return {
            'status': 'completed',
            'knowledge_id': knowledge_id,
            'chunks_retired': chunk_count,
            'retirement_reason': retirement_reason,
            'retired_at': datetime.now().isoformat()
        }

    except AuthoritativeKnowledge.DoesNotExist:
        error_msg = f"Document {knowledge_id} not found for retirement"
        task_logger.error(error_msg)
        return {'status': 'not_found', 'error': error_msg}

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Document retirement failed for {knowledge_id}: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='batch_retire_stale_documents')
def batch_retire_stale_documents(self, max_age_days: int = 1095):
    """
    Batch retire documents older than specified age (default 3 years)
    """
    task_logger.info(f"Batch retiring documents older than {max_age_days} days")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Find stale documents
        stale_documents = AuthoritativeKnowledge.objects.filter(
            publication_date__lt=cutoff_date,
            is_current=True
        )

        retired_count = 0
        for document in stale_documents:
            try:
                retire_result = retire_document(
                    str(document.knowledge_id),
                    f"Automatic retirement: older than {max_age_days} days"
                )
                if retire_result.get('status') == 'completed':
                    retired_count += 1
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                task_logger.warning(f"Failed to retire document {document.knowledge_id}: {str(e)}")

        task_logger.info(f"Batch retirement completed: {retired_count} documents retired")

        return {
            'status': 'completed',
            'documents_retired': retired_count,
            'cutoff_date': cutoff_date.isoformat(),
            'max_age_days': max_age_days
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Batch retirement failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


# =============================================================================
# SCHEDULED MAINTENANCE TASKS
# =============================================================================


@shared_task(bind=True, name='nightly_knowledge_maintenance')
def nightly_knowledge_maintenance(self):
    """
    Nightly maintenance: freshness checks, cleanup, metrics
    """
    task_logger.info("Starting nightly knowledge base maintenance")

    try:
        results = {
            'maintenance_started_at': datetime.now().isoformat(),
            'tasks_completed': [],
            'tasks_failed': [],
            'total_duration_ms': 0
        }

        start_time = time.time()

        # Task 1: Validate freshness
        try:
            freshness_result = validate_knowledge_freshness_task()
            results['tasks_completed'].append({
                'task': 'freshness_validation',
                'result': freshness_result
            })
        except (TypeError, ValidationError, ValueError) as e:
            results['tasks_failed'].append({
                'task': 'freshness_validation',
                'error': str(e)
            })

        # Task 2: Cleanup old traces
        try:
            cleanup_result = cleanup_old_traces_task(days_old=30)
            results['tasks_completed'].append({
                'task': 'trace_cleanup',
                'result': cleanup_result
            })
        except (TypeError, ValidationError, ValueError) as e:
            results['tasks_failed'].append({
                'task': 'trace_cleanup',
                'error': str(e)
            })

        # Task 3: Refresh documents (sample)
        try:
            refresh_result = refresh_documents(force_refresh=False)
            results['tasks_completed'].append({
                'task': 'document_refresh',
                'result': refresh_result
            })
        except (TypeError, ValidationError, ValueError) as e:
            results['tasks_failed'].append({
                'task': 'document_refresh',
                'error': str(e)
            })

        results['total_duration_ms'] = int((time.time() - start_time) * 1000)
        results['maintenance_completed_at'] = datetime.now().isoformat()

        task_logger.info(f"Nightly maintenance completed: {len(results['tasks_completed'])} success, {len(results['tasks_failed'])} failed")

        return results

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Nightly maintenance failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='weekly_knowledge_verification')
def weekly_knowledge_verification(self):
    """
    Weekly verification of knowledge sources and re-verification of stale standards
    """
    task_logger.info("Starting weekly knowledge verification")

    try:
        from apps.core_onboarding.models import AuthoritativeKnowledge
        from datetime import timedelta

        # Re-verify documents older than 90 days
        stale_threshold = datetime.now() - timedelta(days=90)
        stale_documents = AuthoritativeKnowledge.objects.filter(
            last_verified__lt=stale_threshold,
            is_current=True
        )

        verification_results = {
            'documents_checked': 0,
            'documents_refreshed': 0,
            'documents_flagged': 0,
            'errors': 0
        }

        for document in stale_documents:
            try:
                verification_results['documents_checked'] += 1

                # Check if document has source URL for refresh
                if document.source_url:
                    # Queue refresh
                    refresh_result = refresh_documents([str(document.knowledge_id)], force_refresh=True)
                    if refresh_result.get('status') == 'completed':
                        verification_results['documents_refreshed'] += 1
                else:
                    # Flag for manual review
                    document.tags['flagged_for_review'] = datetime.now().isoformat()
                    document.tags['flag_reason'] = 'Stale document without source URL'
                    document.save()
                    verification_results['documents_flagged'] += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                task_logger.warning(f"Failed to verify document {document.knowledge_id}: {str(e)}")
                verification_results['errors'] += 1

        task_logger.info(f"Weekly verification completed: {verification_results}")

        return {
            'status': 'completed',
            'verification_results': verification_results,
            'completed_at': datetime.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Weekly verification failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}
