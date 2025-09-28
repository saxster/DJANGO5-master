"""
Stream Testbench Dashboard Views
Real-time monitoring dashboards with HTMX integration
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.http import JsonResponse
from apps.core.decorators import csrf_protect_htmx, rate_limit

from .models import TestScenario, TestRun, StreamEvent
from ..issue_tracker.models import AnomalySignature, AnomalyOccurrence
from .services.event_capture import stream_event_capture
from ..issue_tracker.services.anomaly_detector import anomaly_detector
from ..ai_testing.dashboard_integration import get_ai_insights_summary, get_ai_insights_for_htmx


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


@user_passes_test(is_staff_or_superuser)
def dashboard_home(request):
    """Main dashboard view"""
    # Get recent test runs
    recent_runs = TestRun.objects.select_related('scenario').order_by('-started_at')[:10]

    # Get active test runs
    active_runs = TestRun.objects.filter(status='running').select_related('scenario')

    # Get recent anomalies
    recent_anomalies = AnomalyOccurrence.objects.select_related('signature').filter(
        created_at__gte=timezone.now() - timedelta(hours=24),
        status__in=['new', 'investigating']
    ).order_by('-created_at')[:10]

    # Get system stats
    stats = get_dashboard_stats()

    # Get AI insights for dashboard
    try:
        ai_insights = get_ai_insights_summary()
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        # Graceful fallback if AI insights are not available
        ai_insights = None
        print(f"AI Insights unavailable: {e}")

    context = {
        'recent_runs': recent_runs,
        'active_runs': active_runs,
        'recent_anomalies': recent_anomalies,
        'stats': stats,
        'ai_insights': ai_insights,
    }

    return render(request, 'streamlab/dashboard.html', context)


@user_passes_test(is_staff_or_superuser)
def live_metrics(request):
    """Live metrics endpoint for HTMX updates"""
    # Get real-time metrics for active runs
    active_runs = TestRun.objects.filter(status='running').select_related('scenario')

    metrics = []
    for run in active_runs:
        # Get recent events for this run
        recent_events = StreamEvent.objects.filter(
            run=run,
            timestamp__gte=timezone.now() - timedelta(minutes=5)
        ).order_by('-timestamp')[:100]

        if recent_events:
            avg_latency = sum(e.latency_ms for e in recent_events) / len(recent_events)
            error_count = sum(1 for e in recent_events if e.outcome == 'error')
            error_rate = error_count / len(recent_events) if recent_events else 0
        else:
            avg_latency = 0
            error_rate = 0

        metrics.append({
            'run_id': str(run.id),
            'scenario_name': run.scenario.name,
            'avg_latency_ms': round(avg_latency, 2),
            'error_rate': round(error_rate * 100, 2),
            'total_events': run.total_events,
            'successful_events': run.successful_events,
            'duration_seconds': run.duration_seconds or 0
        })

    return render(request, 'streamlab/partials/live_metrics.html', {
        'metrics': metrics
    })


@user_passes_test(is_staff_or_superuser)
def scenario_detail(request, scenario_id):
    """Detailed view of a test scenario"""
    scenario = get_object_or_404(TestScenario, id=scenario_id)

    # Get runs for this scenario
    runs = scenario.runs.order_by('-started_at')[:20]

    # Get performance trends
    trends = get_scenario_trends(scenario)

    context = {
        'scenario': scenario,
        'runs': runs,
        'trends': trends,
    }

    return render(request, 'streamlab/scenario_detail.html', context)


@user_passes_test(is_staff_or_superuser)
def run_detail(request, run_id):
    """Detailed view of a test run"""
    run = get_object_or_404(TestRun, id=run_id)

    # Get events for this run
    events = run.events.order_by('-timestamp')[:100]

    # Get anomalies for this run
    anomalies = AnomalyOccurrence.objects.filter(
        test_run_id=run.id
    ).select_related('signature').order_by('-created_at')

    # Calculate detailed metrics
    metrics = calculate_run_metrics(run)

    context = {
        'run': run,
        'events': events,
        'anomalies': anomalies,
        'metrics': metrics,
    }

    return render(request, 'streamlab/run_detail.html', context)


@user_passes_test(is_staff_or_superuser)
def anomalies_dashboard(request):
    """Anomaly tracking dashboard"""
    # Get active anomalies
    active_anomalies = AnomalySignature.objects.filter(
        status='active'
    ).order_by('-last_seen')

    # Get recent occurrences
    recent_occurrences = AnomalyOccurrence.objects.select_related('signature').filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-created_at')[:20]

    # Get anomaly stats
    anomaly_stats = anomaly_detector.get_anomaly_stats()

    context = {
        'active_anomalies': active_anomalies,
        'recent_occurrences': recent_occurrences,
        'stats': anomaly_stats,
    }

    return render(request, 'streamlab/anomalies.html', context)


@user_passes_test(is_staff_or_superuser)
@require_http_methods(["POST"])
@csrf_protect_htmx
@rate_limit(max_requests=30, window_seconds=300)
def start_scenario(request, scenario_id):
    """Start a test scenario via HTMX"""
    scenario = get_object_or_404(TestScenario, id=scenario_id)

    try:
        # Create new test run
        test_run = TestRun.objects.create(
            scenario=scenario,
            started_by=request.user,
            runtime_config={
                'started_from': 'dashboard',
                'user_id': request.user.id
            }
        )

        # Start event capture
        import asyncio
        asyncio.create_task(
            stream_event_capture.start_test_run_capture(str(test_run.id))
        )

        return JsonResponse({
            'success': True,
            'run_id': str(test_run.id),
            'message': f'Started test run for {scenario.name}'
        })

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError) as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@user_passes_test(is_staff_or_superuser)
@require_http_methods(["POST"])
@csrf_protect_htmx
@rate_limit(max_requests=30, window_seconds=300)
def stop_scenario(request, run_id):
    """Stop a running test scenario"""
    run = get_object_or_404(TestRun, id=run_id)

    if run.status != 'running':
        return JsonResponse({
            'success': False,
            'error': 'Test run is not currently running'
        }, status=400)

    try:
        # Stop event capture
        import asyncio
        asyncio.create_task(
            stream_event_capture.stop_test_run_capture(str(run.id))
        )

        return JsonResponse({
            'success': True,
            'message': f'Stopped test run {run.scenario.name}'
        })

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError) as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@user_passes_test(is_staff_or_superuser)
def metrics_api(request):
    """API endpoint for real-time metrics (for Chart.js)"""
    hours = int(request.GET.get('hours', 24))
    since = timezone.now() - timedelta(hours=hours)

    # Get throughput data
    throughput_data = StreamEvent.objects.filter(
        timestamp__gte=since
    ).extra({
        'hour': "DATE_TRUNC('hour', timestamp)"
    }).values('hour').annotate(
        count=Count('id'),
        avg_latency=Avg('latency_ms')
    ).order_by('hour')

    # Get error rate data
    error_data = StreamEvent.objects.filter(
        timestamp__gte=since
    ).extra({
        'hour': "DATE_TRUNC('hour', timestamp)"
    }).values('hour').annotate(
        total=Count('id'),
        errors=Count('id', filter={'outcome': 'error'})
    ).order_by('hour')

    # Format data for Chart.js
    throughput_chart = {
        'labels': [item['hour'].strftime('%H:%M') for item in throughput_data],
        'datasets': [{
            'label': 'Messages/Hour',
            'data': [item['count'] for item in throughput_data],
            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }

    latency_chart = {
        'labels': [item['hour'].strftime('%H:%M') for item in throughput_data],
        'datasets': [{
            'label': 'Avg Latency (ms)',
            'data': [round(item['avg_latency'] or 0, 2) for item in throughput_data],
            'backgroundColor': 'rgba(255, 99, 132, 0.2)',
            'borderColor': 'rgba(255, 99, 132, 1)',
            'borderWidth': 1
        }]
    }

    error_rate_chart = {
        'labels': [item['hour'].strftime('%H:%M') for item in error_data],
        'datasets': [{
            'label': 'Error Rate (%)',
            'data': [
                round((item['errors'] / item['total'] * 100) if item['total'] > 0 else 0, 2)
                for item in error_data
            ],
            'backgroundColor': 'rgba(255, 206, 86, 0.2)',
            'borderColor': 'rgba(255, 206, 86, 1)',
            'borderWidth': 1
        }]
    }

    return JsonResponse({
        'throughput': throughput_chart,
        'latency': latency_chart,
        'error_rate': error_rate_chart
    })


@user_passes_test(is_staff_or_superuser)
def ai_insights_partial(request):
    """AI insights partial view for HTMX updates"""
    try:
        ai_insights = get_ai_insights_for_htmx()
    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError) as e:
        # Fallback if AI insights are not available
        ai_insights = {
            'health_score': 0,
            'critical_gaps': 0,
            'regression_risk': 0,
            'alert_level': 'warning',
            'last_updated': timezone.now()
        }
        print(f"AI Insights partial unavailable: {e}")

    return render(request, 'ai_testing/partials/ai_insights.html', {
        'ai_insights': ai_insights
    })


def get_dashboard_stats():
    """Calculate dashboard statistics"""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    return {
        'total_scenarios': TestScenario.objects.filter(is_active=True).count(),
        'active_runs': TestRun.objects.filter(status='running').count(),
        'runs_24h': TestRun.objects.filter(started_at__gte=last_24h).count(),
        'runs_7d': TestRun.objects.filter(started_at__gte=last_7d).count(),
        'events_24h': StreamEvent.objects.filter(timestamp__gte=last_24h).count(),
        'events_7d': StreamEvent.objects.filter(timestamp__gte=last_7d).count(),
        'anomalies_24h': AnomalyOccurrence.objects.filter(created_at__gte=last_24h).count(),
        'active_anomalies': AnomalySignature.objects.filter(status='active').count(),
    }


def get_scenario_trends(scenario):
    """Get performance trends for a scenario"""
    runs = scenario.runs.filter(
        status='completed',
        p95_latency_ms__isnull=False
    ).order_by('-started_at')[:20]

    if not runs:
        return None

    return {
        'dates': [run.started_at.strftime('%m-%d %H:%M') for run in reversed(runs)],
        'latencies': [run.p95_latency_ms for run in reversed(runs)],
        'throughput': [run.throughput_qps or 0 for run in reversed(runs)],
        'error_rates': [(run.error_rate or 0) * 100 for run in reversed(runs)],
    }


def calculate_run_metrics(run):
    """Calculate detailed metrics for a test run"""
    events = run.events.all()

    if not events:
        return {}

    latencies = [e.latency_ms for e in events if e.latency_ms is not None]

    return {
        'total_events': events.count(),
        'success_events': events.filter(outcome='success').count(),
        'error_events': events.filter(outcome='error').count(),
        'timeout_events': events.filter(outcome='timeout').count(),
        'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
        'min_latency': min(latencies) if latencies else 0,
        'max_latency': max(latencies) if latencies else 0,
        'events_by_endpoint': dict(
            events.values('endpoint').annotate(count=Count('id')).values_list('endpoint', 'count')
        ),
        'events_by_outcome': dict(
            events.values('outcome').annotate(count=Count('id')).values_list('outcome', 'count')
        ),
    }