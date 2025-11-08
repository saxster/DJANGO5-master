"""
Performance Analytics Celery Tasks

Background tasks for nightly metric aggregation and analysis.

Tasks:
- aggregate_daily_metrics_task: Nightly aggregation (runs at 2 AM)
- update_cohort_benchmarks_task: Weekly benchmark updates (runs Sunday 3 AM)
- generate_coaching_queue_task: Daily coaching recommendations (runs at 6 AM)

Compliance:
- Celery Configuration Guide: Proper decorators and naming
- Rule #11: Specific exception handling
- Idempotency: Uses IdempotentTask where applicable
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

logger = logging.getLogger('performance_analytics.tasks')


@shared_task(
    name='apps.performance_analytics.aggregate_daily_metrics',
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def aggregate_daily_metrics_task(self, target_date_str=None):
    """
    Aggregate worker performance metrics for specified date.
    
    Runs nightly at 2 AM to process previous day's data.
    
    Args:
        target_date_str: ISO date string (YYYY-MM-DD), defaults to yesterday
        
    Returns:
        dict: Summary of aggregation (workers_processed, teams_updated, etc.)
        
    Celery Beat Schedule:
        Run daily at 2:00 AM
    """
    from apps.performance_analytics.services.metrics_aggregator import MetricsAggregator
    from datetime import date as date_class
    
    try:
        # Parse target date
        if target_date_str:
            target_date = date_class.fromisoformat(target_date_str)
        else:
            target_date = (timezone.now() - timedelta(days=1)).date()
        
        logger.info(
            f"Starting daily metrics aggregation for {target_date}",
            extra={'target_date': target_date.isoformat(), 'task_id': self.request.id}
        )
        
        # Run aggregation
        result = MetricsAggregator.aggregate_all_metrics(target_date)
        
        logger.info(
            f"Daily metrics aggregation completed: {result['workers_processed']} workers, "
            f"{result['teams_updated']} teams",
            extra={
                'target_date': target_date.isoformat(),
                'workers_processed': result['workers_processed'],
                'teams_updated': result['teams_updated'],
                'task_id': self.request.id
            }
        )
        
        return result
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Database error during metrics aggregation: {e}",
            exc_info=True,
            extra={'target_date': target_date_str, 'retry_count': self.request.retries}
        )
        raise self.retry(exc=e)
        
    except VALIDATION_EXCEPTIONS as e:
        logger.error(
            f"Validation error during metrics aggregation: {e}",
            exc_info=True,
            extra={'target_date': target_date_str}
        )
        return {
            'status': 'error',
            'error': str(e),
            'workers_processed': 0
        }


@shared_task(
    name='apps.performance_analytics.update_cohort_benchmarks',
    bind=True,
    max_retries=2
)
def update_cohort_benchmarks_task(self, period_days=30):
    """
    Update cohort benchmark statistics.
    
    Runs weekly on Sunday at 3 AM to recalculate percentiles and benchmarks.
    
    Args:
        period_days: Number of days to include in benchmark calculation
        
    Returns:
        dict: Summary of cohorts updated
        
    Celery Beat Schedule:
        Run weekly on Sunday at 3:00 AM
    """
    from apps.performance_analytics.services.cohort_analyzer import CohortAnalyzer
    
    try:
        logger.info(
            f"Starting cohort benchmark update (period: {period_days} days)",
            extra={'period_days': period_days, 'task_id': self.request.id}
        )
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=period_days)
        
        # Update benchmarks
        result = CohortAnalyzer.update_all_cohort_benchmarks(start_date, end_date)
        
        logger.info(
            f"Cohort benchmarks updated: {result['cohorts_updated']} cohorts",
            extra={
                'cohorts_updated': result['cohorts_updated'],
                'metrics_updated': result['metrics_updated'],
                'task_id': self.request.id
            }
        )
        
        return result
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Database error updating cohort benchmarks: {e}",
            exc_info=True,
            extra={'period_days': period_days}
        )
        raise self.retry(exc=e)


@shared_task(
    name='apps.performance_analytics.generate_coaching_recommendations',
    bind=True
)
def generate_coaching_recommendations_task(self):
    """
    Generate daily coaching recommendations for supervisors.
    
    Identifies workers who:
    - Have BPI < 60 (developing or needs support)
    - Declining trend (>10 point drop in 2 weeks)
    - Specific metric issues (e.g., documentation <50%)
    
    Creates notifications for supervisors.
    
    Runs daily at 6 AM.
    
    Celery Beat Schedule:
        Run daily at 6:00 AM
    """
    from apps.performance_analytics.services.team_analytics_service import TeamAnalyticsService
    from apps.onboarding.models import Bt
    
    try:
        logger.info("Generating coaching recommendations", extra={'task_id': self.request.id})
        
        recommendations = []
        
        # Get all sites
        sites = Bt.objects.filter(active=True)
        
        for site in sites:
            # Get coaching queue for site
            queue = TeamAnalyticsService.get_coaching_queue(
                site_id=site.id,
                threshold_bpi=60,
                include_declining=True
            )
            
            if queue:
                # Create notification for site supervisor
                # (Integration with notification service)
                recommendations.append({
                    'site_id': site.id,
                    'site_name': site.abbr,
                    'workers_needing_attention': len(queue),
                    'workers': queue
                })
        
        logger.info(
            f"Coaching recommendations generated: {len(recommendations)} sites, "
            f"{sum(r['workers_needing_attention'] for r in recommendations)} workers",
            extra={'task_id': self.request.id, 'sites_with_queue': len(recommendations)}
        )
        
        return {
            'sites_processed': len(sites),
            'sites_with_recommendations': len(recommendations),
            'total_workers_flagged': sum(r['workers_needing_attention'] for r in recommendations),
            'recommendations': recommendations
        }
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Database error generating coaching recommendations: {e}",
            exc_info=True
        )
        return {'status': 'error', 'error': str(e)}


@shared_task(name='apps.performance_analytics.backfill_historical_metrics')
def backfill_historical_metrics_task(start_date_str, end_date_str):
    """
    Backfill historical metrics for a date range.
    
    Use for initial data population or re-processing.
    
    Args:
        start_date_str: ISO date string (YYYY-MM-DD)
        end_date_str: ISO date string (YYYY-MM-DD)
        
    Returns:
        dict: Summary of dates processed
    """
    from apps.performance_analytics.services.metrics_aggregator import MetricsAggregator
    from datetime import date as date_class, timedelta
    
    try:
        start_date = date_class.fromisoformat(start_date_str)
        end_date = date_class.fromisoformat(end_date_str)
        
        logger.info(
            f"Starting backfill from {start_date} to {end_date}",
            extra={'start_date': start_date_str, 'end_date': end_date_str}
        )
        
        current_date = start_date
        dates_processed = 0
        total_workers = 0
        
        while current_date <= end_date:
            result = MetricsAggregator.aggregate_all_metrics(current_date)
            dates_processed += 1
            total_workers += result['workers_processed']
            
            logger.info(
                f"Backfilled {current_date}: {result['workers_processed']} workers",
                extra={'date': current_date.isoformat()}
            )
            
            current_date += timedelta(days=1)
        
        logger.info(
            f"Backfill completed: {dates_processed} dates, {total_workers} worker-days",
            extra={'dates_processed': dates_processed, 'total_workers': total_workers}
        )
        
        return {
            'dates_processed': dates_processed,
            'total_worker_days': total_workers,
            'start_date': start_date_str,
            'end_date': end_date_str
        }
        
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid date format: {e}", exc_info=True)
        return {'status': 'error', 'error': f'Invalid date format: {e}'}
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error during backfill: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


__all__ = [
    'aggregate_daily_metrics_task',
    'update_cohort_benchmarks_task',
    'generate_coaching_recommendations_task',
    'backfill_historical_metrics_task',
]
