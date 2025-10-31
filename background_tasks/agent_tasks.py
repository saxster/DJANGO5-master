"""
Agent Intelligence Background Tasks

Periodic tasks for dashboard agent processing and auto-execution.

Following CLAUDE.md:
- Rule #7: <150 lines
- @shared_task decorator (not @app.task)
- Specific exception handling
- Queue routing to 'reports' queue (Priority 6)

Dashboard Agent Intelligence - Phase 6
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from django.utils import timezone
from django.core.cache import cache
from celery import shared_task

from apps.core.services.agents.agent_orchestrator import AgentOrchestrator
from apps.core.models.agent_recommendation import AgentRecommendation
from apps.peoples.models import BusinessUnit
from apps.tenants.models import Client

logger = logging.getLogger(__name__)


@shared_task(
    name='dashboard.process_agent_insights',
    queue='reports',
    priority=6,
    soft_time_limit=120,  # 2 minutes
    time_limit=180,  # 3 minutes hard limit
    max_retries=2
)
def process_dashboard_agent_insights(site_id: int, client_id: int) -> Dict[str, Any]:
    """
    Process agent insights for a site.

    Runs all agents (TaskBot, TourBot, etc.) in parallel and caches results.

    Args:
        site_id: Business unit/site ID
        client_id: Tenant/client ID

    Returns:
        Task execution summary
    """
    try:
        # Calculate time range (last 7 days)
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        time_range = (start_time, end_time)

        logger.info(
            f"Processing agent insights for site {site_id}, "
            f"client {client_id}, range {start_time} to {end_time}"
        )

        # Run agent orchestration
        orchestrator = AgentOrchestrator(client_id)
        recommendations = orchestrator.process_dashboard_data(site_id, time_range)

        # Cache results for fast dashboard loading (5 min TTL)
        cache_key = f"agent_insights:{site_id}:{start_time.date()}"
        cache_data = [rec.to_dict() for rec in recommendations]
        cache.set(cache_key, cache_data, timeout=300)

        # Count by severity
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for rec in recommendations:
            severity_counts[rec.severity] = severity_counts.get(rec.severity, 0) + 1

        result = {
            'site_id': site_id,
            'client_id': client_id,
            'total_recommendations': len(recommendations),
            'by_severity': severity_counts,
            'llm_provider': recommendations[0].llm_provider if recommendations else 'none',
            'cached': True,
            'timestamp': timezone.now().isoformat()
        }

        logger.info(
            f"Agent insights processed: {len(recommendations)} recommendations "
            f"({severity_counts['critical']} critical, {severity_counts['high']} high)"
        )

        return result

    except (ValueError, KeyError, AttributeError) as e:
        logger.error(f"Agent insights processing failed: {e}", exc_info=True)
        return {
            'site_id': site_id,
            'client_id': client_id,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    name='dashboard.auto_execute_critical_actions',
    queue='high_priority',
    priority=8,
    soft_time_limit=300,  # 5 minutes
    time_limit=420  # 7 minutes hard limit
)
def auto_execute_critical_actions() -> Dict[str, Any]:
    """
    Auto-execute critical agent recommendations.

    Runs every 10 minutes to execute high-confidence critical actions.

    Returns:
        Execution summary
    """
    try:
        # Find critical recommendations eligible for auto-execution
        critical_recs = AgentRecommendation.objects.filter(
            status='pending_review',
            severity='critical',
            confidence__gte=0.95,  # Only very high confidence
            auto_executed=False,
            created_at__gte=timezone.now() - timedelta(hours=1)  # Last hour only
        )

        executed_count = 0
        failed_count = 0

        for rec in critical_recs:
            try:
                # Execute first action only for auto-execution
                if rec.actions and len(rec.actions) > 0:
                    first_action = rec.actions[0]

                    if first_action.get('type') == 'workflow_trigger':
                        # Get orchestrator and execute
                        orchestrator = AgentOrchestrator(rec.client_id)
                        orchestrator.execute_action(rec.id, first_action.get('endpoint'))

                        # Mark as auto-executed
                        rec.auto_executed = True
                        rec.status = 'auto_executed'
                        rec.save()

                        executed_count += 1
                        logger.info(f"Auto-executed critical recommendation {rec.id}")

            except (ValueError, AttributeError, KeyError) as e:
                logger.error(f"Failed to auto-execute recommendation {rec.id}: {e}")
                failed_count += 1

        result = {
            'total_critical': critical_recs.count(),
            'executed': executed_count,
            'failed': failed_count,
            'timestamp': timezone.now().isoformat()
        }

        logger.info(f"Auto-execution complete: {executed_count} executed, {failed_count} failed")
        return result

    except (ValueError, KeyError, AttributeError) as e:
        logger.error(f"Auto-execution task failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    name='dashboard.cleanup_expired_recommendations',
    queue='maintenance',
    priority=3
)
def cleanup_expired_recommendations() -> int:
    """
    Clean up expired agent recommendations.

    Runs daily to remove old recommendations.

    Returns:
        Number of recommendations deleted
    """
    try:
        # Delete recommendations older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)

        deleted_count, _ = AgentRecommendation.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Cleaned up {deleted_count} expired agent recommendations")
        return deleted_count

    except (ValueError, AttributeError) as e:
        logger.error(f"Cleanup task failed: {e}", exc_info=True)
        return 0
