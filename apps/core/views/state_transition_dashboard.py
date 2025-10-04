"""
State Transition Monitoring Dashboard

Provides comprehensive visibility into state machine operations:
- Performance metrics and trends
- Failure analysis and debugging
- Audit trail exploration
- Real-time monitoring

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #17: Secure data access

Key Features:
- Real-time state transition metrics
- Performance trend analysis
- Error pattern detection
- Audit trail search
- Entity-specific transition history
"""

import logging
from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.utils import timezone
from django.db.models import Count, Avg, Q, F
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.models.state_transition_audit import StateTransitionAudit

logger = logging.getLogger(__name__)


@login_required
@permission_required('core.view_statetransitionaudit', raise_exception=True)
def state_transition_dashboard(request):
    """
    Main state transition monitoring dashboard.

    Displays:
    - Key metrics (success rate, avg execution time, etc.)
    - Recent transitions
    - Performance trends
    - Top errors
    """
    # Time range filter (default: last 24 hours)
    hours = int(request.GET.get('hours', 24))
    start_time = timezone.now() - timedelta(hours=hours)

    # Calculate key metrics
    metrics = _calculate_dashboard_metrics(start_time)

    # Recent transitions
    recent_transitions = StateTransitionAudit.objects.filter(
        timestamp__gte=start_time
    ).select_related('user').order_by('-timestamp')[:50]

    # Top errors
    top_errors = _get_top_errors(start_time, limit=10)

    # Performance by entity type
    entity_performance = _get_entity_performance(start_time)

    context = {
        'metrics': metrics,
        'recent_transitions': recent_transitions,
        'top_errors': top_errors,
        'entity_performance': entity_performance,
        'time_range_hours': hours,
    }

    return render(request, 'core/state_transition_dashboard.html', context)


@login_required
@permission_required('core.view_statetransitionaudit', raise_exception=True)
def entity_transition_history(request, entity_type, entity_id):
    """
    View complete transition history for a specific entity.

    Shows chronological transitions with context and performance data.
    """
    transitions = StateTransitionAudit.objects.filter(
        entity_type=entity_type,
        entity_id=entity_id
    ).select_related('user').order_by('-timestamp')

    # Pagination
    paginator = Paginator(transitions, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'entity_type': entity_type,
        'entity_id': entity_id,
        'transitions': page_obj,
        'total_transitions': transitions.count(),
    }

    return render(request, 'core/entity_transition_history.html', context)


@login_required
@permission_required('core.view_statetransitionaudit', raise_exception=True)
def transition_failure_analysis(request):
    """
    Analyze failed transitions for patterns and debugging.

    Groups failures by error type, entity type, and time.
    """
    hours = int(request.GET.get('hours', 24))
    start_time = timezone.now() - timedelta(hours=hours)

    # Failed transitions only
    failures = StateTransitionAudit.objects.filter(
        timestamp__gte=start_time,
        success=False
    ).select_related('user').order_by('-timestamp')

    # Group by error message
    error_groups = failures.values('error_message').annotate(
        count=Count('id'),
        avg_execution_ms=Avg('execution_time_ms')
    ).order_by('-count')[:20]

    # Group by entity type
    entity_groups = failures.values('entity_type').annotate(
        count=Count('id')
    ).order_by('-count')

    # Pagination for detailed failures
    paginator = Paginator(failures, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'error_groups': error_groups,
        'entity_groups': entity_groups,
        'failures': page_obj,
        'total_failures': failures.count(),
        'time_range_hours': hours,
    }

    return render(request, 'core/transition_failure_analysis.html', context)


@login_required
@permission_required('core.view_statetransitionaudit', raise_exception=True)
@require_http_methods(["GET"])
def transition_metrics_api(request):
    """
    JSON API for real-time metrics (for AJAX updates).

    Returns:
        - Current success rate
        - Average execution time
        - Transitions per minute
        - Lock contention metrics
    """
    hours = int(request.GET.get('hours', 1))
    start_time = timezone.now() - timedelta(hours=hours)

    metrics = _calculate_dashboard_metrics(start_time)

    return JsonResponse({
        'success': True,
        'metrics': metrics,
        'timestamp': timezone.now().isoformat()
    })


@login_required
@permission_required('core.view_statetransitionaudit', raise_exception=True)
def performance_trends(request):
    """
    Analyze performance trends over time.

    Shows:
    - Execution time trends
    - Lock acquisition time trends
    - Retry patterns
    - Throughput metrics
    """
    days = int(request.GET.get('days', 7))
    start_time = timezone.now() - timedelta(days=days)

    # Daily aggregates
    daily_stats = StateTransitionAudit.objects.filter(
        timestamp__gte=start_time
    ).extra(
        select={'day': 'date(timestamp)'}
    ).values('day').annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(success=True)),
        avg_execution_ms=Avg('execution_time_ms'),
        avg_lock_ms=Avg('lock_acquisition_time_ms'),
        avg_retries=Avg('retry_attempt')
    ).order_by('day')

    # Entity type breakdown
    entity_trends = StateTransitionAudit.objects.filter(
        timestamp__gte=start_time
    ).values('entity_type').annotate(
        total=Count('id'),
        avg_execution_ms=Avg('execution_time_ms')
    ).order_by('-total')

    context = {
        'daily_stats': list(daily_stats),
        'entity_trends': list(entity_trends),
        'time_range_days': days,
    }

    return render(request, 'core/performance_trends.html', context)


# Helper functions

def _calculate_dashboard_metrics(start_time):
    """Calculate key dashboard metrics for time range"""
    transitions = StateTransitionAudit.objects.filter(
        timestamp__gte=start_time
    )

    total_count = transitions.count()
    success_count = transitions.filter(success=True).count()

    metrics = {
        'total_transitions': total_count,
        'success_count': success_count,
        'failure_count': total_count - success_count,
        'success_rate': (success_count / total_count * 100) if total_count > 0 else 0,
    }

    # Performance metrics (only for successful transitions)
    successful = transitions.filter(success=True)

    if successful.exists():
        perf_stats = successful.aggregate(
            avg_execution=Avg('execution_time_ms'),
            avg_lock=Avg('lock_acquisition_time_ms'),
            avg_retries=Avg('retry_attempt')
        )
        metrics.update({
            'avg_execution_ms': round(perf_stats['avg_execution'] or 0, 2),
            'avg_lock_ms': round(perf_stats['avg_lock'] or 0, 2),
            'avg_retries': round(perf_stats['avg_retries'] or 0, 2),
        })
    else:
        metrics.update({
            'avg_execution_ms': 0,
            'avg_lock_ms': 0,
            'avg_retries': 0,
        })

    # Lock contention (retries > 0)
    contention_count = transitions.filter(retry_attempt__gt=0).count()
    metrics['lock_contention_rate'] = (
        (contention_count / total_count * 100) if total_count > 0 else 0
    )

    return metrics


def _get_top_errors(start_time, limit=10):
    """Get most common error messages"""
    return StateTransitionAudit.objects.filter(
        timestamp__gte=start_time,
        success=False
    ).values('error_message').annotate(
        count=Count('id')
    ).order_by('-count')[:limit]


def _get_entity_performance(start_time):
    """Get performance metrics by entity type"""
    return StateTransitionAudit.objects.filter(
        timestamp__gte=start_time
    ).values('entity_type').annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(success=True)),
        avg_execution_ms=Avg('execution_time_ms'),
        avg_lock_ms=Avg('lock_acquisition_time_ms')
    ).order_by('-total')
