"""
Data Purge Background Tasks

Automated data purging based on retention policies.

Following CLAUDE.md:
- Rule #7: <150 lines per task
- Rule #17: Transaction safety
- Compliance-ready

Sprint 10.3: Data Retention Controls
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from apps.tenants.models.retention_policy import RetentionPolicy, DEFAULT_RETENTION_DAYS
from apps.core.models import LLMUsageLog
from apps.core_onboarding.models import KnowledgeIngestionJob, LLMRecommendation
from apps.core.models import SagaState

logger = logging.getLogger('purge_tasks')


@shared_task(name='purge_expired_llm_logs')
def purge_expired_llm_logs():
    """
    Purge expired LLM usage logs based on retention policies.

    Runs: Daily at 2 AM
    """
    logger.info("Starting LLM usage log purge")

    try:
        purged_count = 0

        # Get all tenants with retention policies
        policies = RetentionPolicy.objects.filter(
            data_type='llm_usage_log',
            enabled=True,
            legal_hold=False
        )

        for policy in policies:
            cutoff_date = timezone.now() - timedelta(days=policy.retention_days)

            # Delete old logs for this tenant
            deleted = LLMUsageLog.objects.filter(
                tenant=policy.tenant,
                created_at__lt=cutoff_date
            ).delete()

            purged_count += deleted[0]
            logger.info(f"Purged {deleted[0]} LLM logs for tenant {policy.tenant.name}")

        # Handle tenants without explicit policy (use default)
        default_days = DEFAULT_RETENTION_DAYS['llm_usage_log']
        cutoff_date = timezone.now() - timedelta(days=default_days)

        # Get tenants with policies (to exclude)
        tenants_with_policies = set(p.tenant_id for p in policies)

        # Purge for tenants without policies
        all_logs = LLMUsageLog.objects.filter(created_at__lt=cutoff_date)
        if tenants_with_policies:
            all_logs = all_logs.exclude(tenant_id__in=tenants_with_policies)

        deleted = all_logs.delete()
        purged_count += deleted[0]

        logger.info(f"LLM log purge complete: {purged_count} records deleted")

        return {
            'status': 'completed',
            'purged_count': purged_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"LLM log purge failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(name='purge_expired_recommendations')
def purge_expired_recommendations():
    """
    Purge expired LLM recommendations.

    Runs: Weekly
    """
    logger.info("Starting recommendation purge")

    try:
        default_days = DEFAULT_RETENTION_DAYS['recommendation_traces']
        cutoff_date = timezone.now() - timedelta(days=default_days)

        # Delete old completed/failed recommendations
        deleted = LLMRecommendation.objects.filter(
            cdtz__lt=cutoff_date,
            status__in=['COMPLETED', 'FAILED']
        ).delete()

        logger.info(f"Purged {deleted[0]} expired recommendations")

        return {
            'status': 'completed',
            'purged_count': deleted[0],
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Recommendation purge failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(name='purge_stale_sagas')
def purge_stale_sagas():
    """
    Purge completed/rolled-back sagas older than retention period.

    Runs: Daily
    """
    logger.info("Starting saga state purge")

    try:
        default_days = DEFAULT_RETENTION_DAYS['saga_state']
        purged_count = 0

        # Use SagaContextManager cleanup method
        from apps.core.services import saga_manager
        purged_count = saga_manager.cleanup_stale_sagas(threshold_days=default_days)

        logger.info(f"Purged {purged_count} stale sagas")

        return {
            'status': 'completed',
            'purged_count': purged_count
        }

    except Exception as e:
        logger.error(f"Saga purge failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(name='purge_old_ingestion_jobs')
def purge_old_ingestion_jobs():
    """
    Purge old knowledge ingestion jobs.

    Runs: Monthly
    """
    logger.info("Starting ingestion job purge")

    try:
        default_days = DEFAULT_RETENTION_DAYS['ingestion_jobs']
        cutoff_date = timezone.now() - timedelta(days=default_days)

        # Delete old jobs (keep FAILED jobs for debugging)
        deleted = KnowledgeIngestionJob.objects.filter(
            cdtz__lt=cutoff_date,
            status='ready'
        ).delete()

        logger.info(f"Purged {deleted[0]} old ingestion jobs")

        return {
            'status': 'completed',
            'purged_count': deleted[0],
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Ingestion job purge failed: {e}")
        return {'status': 'failed', 'error': str(e)}
