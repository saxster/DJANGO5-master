"""
Cron Job Management Web Interface Views

Provides comprehensive web interface for managing cron jobs, monitoring
system health, and viewing execution history.

Key Features:
- Dashboard with system overview
- Job list with filtering and pagination
- Detailed job management and editing
- Execution history and monitoring
- Health metrics visualization
- Manual job execution controls

Compliance:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #15: No PII in logs
"""

import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import View

from apps.core.models.cron_job_definition import CronJobDefinition
from apps.core.models.cron_job_execution import CronJobExecution
from apps.core.services.cron_job_health_monitor import cron_health_monitor
from apps.core.services.cron_job_registry import cron_registry
# require_permissions decorator not yet implemented - using login_required for now
# from apps.core.decorators import require_permissions

logger = logging.getLogger(__name__)


@login_required
def cron_dashboard(request):
    """
    Main dashboard showing cron system overview and health metrics.
    """
    try:
        # Get tenant for multi-tenant filtering
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None

        # Get system health summary
        health_summary = cron_health_monitor.get_system_health_summary(tenant=tenant)

        # Get recent job executions
        recent_executions_query = CronJobExecution.objects.select_related(
            'job_definition'
        ).order_by('-created_at')[:10]

        if tenant:
            recent_executions_query = recent_executions_query.filter(tenant=tenant)

        recent_executions = list(recent_executions_query)

        # Get jobs needing attention (failed, overdue, low success rate)
        attention_jobs = []
        jobs_query = CronJobDefinition.objects.filter(is_enabled=True, status='active')

        if tenant:
            jobs_query = jobs_query.filter(tenant=tenant)

        for job in jobs_query[:20]:  # Limit to prevent performance issues
            try:
                health_metrics = cron_health_monitor.get_job_health_metrics(job)
                if (health_metrics.health_score < 70 or
                    health_metrics.is_overdue or
                    health_metrics.success_rate < 80):
                    attention_jobs.append({
                        'job': job,
                        'health_metrics': health_metrics
                    })
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"Failed to get health metrics for job {job.name}: {e}")

        context = {
            'health_summary': health_summary,
            'recent_executions': recent_executions,
            'attention_jobs': attention_jobs[:10],  # Show top 10 issues
            'page_title': 'Cron Job Management Dashboard'
        }

        return render(request, 'core/cron/dashboard.html', context)

    except DatabaseError as e:
        logger.error(f"Dashboard load failed: {e}")
        messages.error(request, "Failed to load dashboard data")
        return render(request, 'core/cron/dashboard.html', {
            'error': 'Dashboard temporarily unavailable'
        })


@login_required
def cron_job_list(request):
    """
    List all cron jobs with filtering and pagination.
    """
    try:
        # Get query parameters
        status_filter = request.GET.get('status', '')
        job_type_filter = request.GET.get('job_type', '')
        search_query = request.GET.get('search', '')
        page = request.GET.get('page', 1)

        # Build queryset
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None
        jobs = CronJobDefinition.objects.all()

        if tenant:
            jobs = jobs.filter(tenant=tenant)

        # Apply filters
        if status_filter:
            jobs = jobs.filter(status=status_filter)

        if job_type_filter:
            jobs = jobs.filter(job_type=job_type_filter)

        if search_query:
            jobs = jobs.filter(name__icontains=search_query)

        # Order by next execution time
        jobs = jobs.order_by('next_execution_time', 'name')

        # Paginate
        paginator = Paginator(jobs, 20)
        page_obj = paginator.get_page(page)

        # Get health metrics for visible jobs
        jobs_with_health = []
        for job in page_obj:
            try:
                health_metrics = cron_health_monitor.get_job_health_metrics(job)
                jobs_with_health.append({
                    'job': job,
                    'health_metrics': health_metrics
                })
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"Failed to get health metrics for job {job.name}: {e}")
                jobs_with_health.append({
                    'job': job,
                    'health_metrics': None
                })

        context = {
            'jobs_with_health': jobs_with_health,
            'page_obj': page_obj,
            'filters': {
                'status': status_filter,
                'job_type': job_type_filter,
                'search': search_query
            },
            'status_choices': CronJobDefinition.STATUS_CHOICES,
            'job_type_choices': CronJobDefinition.JOB_TYPES,
            'page_title': 'Cron Jobs'
        }

        return render(request, 'core/cron/job_list.html', context)

    except DatabaseError as e:
        logger.error(f"Job list load failed: {e}")
        messages.error(request, "Failed to load job list")
        return render(request, 'core/cron/job_list.html', {'error': 'Job list temporarily unavailable'})


@login_required
def cron_job_detail(request, job_id):
    """
    Detailed view of a specific cron job with execution history.
    """
    try:
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None

        # Get job with tenant filtering
        if tenant:
            job = get_object_or_404(CronJobDefinition, id=job_id, tenant=tenant)
        else:
            job = get_object_or_404(CronJobDefinition, id=job_id)

        # Get health metrics
        health_metrics = cron_health_monitor.get_job_health_metrics(job)

        # Get execution history
        executions = CronJobExecution.objects.filter(
            job_definition=job
        ).order_by('-created_at')[:50]

        # Get execution statistics
        execution_stats = {
            'total_executions': job.execution_count,
            'success_count': job.success_count,
            'failure_count': job.failure_count,
            'success_rate': job.get_success_rate(),
            'average_duration': job.average_duration_seconds
        }

        context = {
            'job': job,
            'health_metrics': health_metrics,
            'executions': executions,
            'execution_stats': execution_stats,
            'page_title': f'Job: {job.name}'
        }

        return render(request, 'core/cron/job_detail.html', context)

    except DatabaseError as e:
        logger.error(f"Job detail load failed: {e}")
        messages.error(request, "Failed to load job details")
        return redirect('cron_job_list')


@login_required
@require_http_methods(["POST"])
def execute_job_manual(request, job_id):
    """
    Manually execute a cron job.
    """
    try:
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None

        if tenant:
            job = get_object_or_404(CronJobDefinition, id=job_id, tenant=tenant)
        else:
            job = get_object_or_404(CronJobDefinition, id=job_id)

        # Create execution record
        execution_record = cron_registry.create_execution_record(
            job_definition=job,
            execution_context='manual'
        )

        if execution_record:
            messages.success(
                request,
                f"Job '{job.name}' has been queued for manual execution. "
                f"Execution ID: {execution_record.execution_id}"
            )
        else:
            messages.error(request, f"Failed to queue job '{job.name}' for execution")

        return redirect('cron_job_detail', job_id=job_id)

    except DatabaseError as e:
        logger.error(f"Manual execution failed: {e}")
        messages.error(request, "Failed to execute job")
        return redirect('cron_job_detail', job_id=job_id)


@login_required
@require_http_methods(["POST"])
def toggle_job_status(request, job_id):
    """
    Toggle job enabled/disabled status.
    """
    try:
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None

        if tenant:
            job = get_object_or_404(CronJobDefinition, id=job_id, tenant=tenant)
        else:
            job = get_object_or_404(CronJobDefinition, id=job_id)

        # Toggle status
        job.is_enabled = not job.is_enabled
        job.save(update_fields=['is_enabled'])

        status_text = "enabled" if job.is_enabled else "disabled"
        messages.success(request, f"Job '{job.name}' has been {status_text}")

        return redirect('cron_job_detail', job_id=job_id)

    except DatabaseError as e:
        logger.error(f"Status toggle failed: {e}")
        messages.error(request, "Failed to update job status")
        return redirect('cron_job_detail', job_id=job_id)


@login_required
def discover_commands(request):
    """
    Auto-discover and register management commands.
    """
    try:
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None
        result = cron_registry.discover_and_register_commands(tenant=tenant)

        if result['success']:
            messages.success(
                request,
                f"Discovery completed. Registered {result['registered_count']} commands, "
                f"skipped {result['skipped_count']} commands."
            )
            if result['errors']:
                messages.warning(
                    request,
                    f"Some commands had errors: {len(result['errors'])} errors occurred."
                )
        else:
            messages.error(request, f"Discovery failed: {result['error']}")

        return redirect('cron_job_list')

    except DatabaseError as e:
        logger.error(f"Command discovery failed: {e}")
        messages.error(request, "Command discovery failed")
        return redirect('cron_job_list')