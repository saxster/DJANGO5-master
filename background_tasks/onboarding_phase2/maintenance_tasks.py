"""
Maintenance and Monitoring Tasks
Knowledge base maintenance, cleanup, and verification
"""
import logging
import traceback
import time
from datetime import timedelta

from celery import shared_task
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


@shared_task(bind=True, name='cleanup_old_traces_task')
def cleanup_old_traces_task(self, days_old: int = 30):
    """
    Clean up old trace data and recommendations
    """
    task_logger.info(f"Cleaning up traces older than {days_old} days")

    try:
        from apps.core_onboarding.models import LLMRecommendation

        cutoff_date = timezone.now() - timedelta(days=days_old)

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
        from apps.core_onboarding.models import AuthoritativeKnowledge

        # Flag documents older than 2 years as potentially stale
        stale_threshold = timezone.now() - timedelta(days=730)

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


@shared_task(bind=True, name='nightly_knowledge_maintenance')
def nightly_knowledge_maintenance(self):
    """
    Nightly maintenance: freshness checks, cleanup, metrics
    """
    task_logger.info("Starting nightly knowledge base maintenance")

    try:
        from background_tasks.onboarding_phase2.document_ingestion import refresh_documents

        results = {
            'maintenance_started_at': timezone.now().isoformat(),
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
        results['maintenance_completed_at'] = timezone.now().isoformat()

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
        from background_tasks.onboarding_phase2.document_ingestion import refresh_documents

        # Re-verify documents older than 90 days
        stale_threshold = timezone.now() - timedelta(days=90)
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
                    document.tags['flagged_for_review'] = timezone.now().isoformat()
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
            'completed_at': timezone.now().isoformat()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        error_msg = f"Weekly verification failed: {str(e)}"
        task_logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}


# Define exception classes for imports
class IntegrationException(Exception):
    """Integration exception placeholder"""
    pass


class LLMServiceException(Exception):
    """LLM service exception placeholder"""
    pass
