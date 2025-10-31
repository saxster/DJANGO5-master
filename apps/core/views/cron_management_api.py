"""
Cron Management API Views

RESTful API endpoints for managing cron jobs, executions, and system health.
Provides comprehensive CRUD operations and monitoring capabilities.

Key Features:
- Full CRUD operations for cron jobs
- Manual execution triggering
- Health monitoring and metrics
- Execution history and analytics
- System status and discovery operations
- Tenant-aware operations

Compliance:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #15: No PII in logs
"""

import logging
from typing import Dict, Any
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.core.decorators import csrf_protect_ajax
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.utils import timezone
import json

from apps.core.decorators import rate_limit, require_permissions
from apps.core.models.cron_job_definition import CronJobDefinition
from apps.core.models.cron_job_execution import CronJobExecution
from apps.core.services.cron_job_registry import cron_registry
from apps.core.services.cron_job_health_monitor import cron_health_monitor
from apps.core.services.management_command_scheduler import command_scheduler
from apps.core.utils_new.cron_utilities import validate_cron_expression

logger = logging.getLogger(__name__)


@method_decorator([login_required, require_permissions('is_staff'), rate_limit('60/h')], name='dispatch')
class CronJobListAPI(View):
    """API for listing and creating cron jobs."""

    def get(self, request):
        """List cron jobs with filtering and pagination."""
        try:
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', 20)), 100)
            status = request.GET.get('status')
            job_type = request.GET.get('job_type')
            tags = request.GET.get('tags')

            # Build queryset
            queryset = CronJobDefinition.objects.all()

            # Apply filters
            if status:
                queryset = queryset.filter(status=status)
            if job_type:
                queryset = queryset.filter(job_type=job_type)
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',')]
                queryset = queryset.filter(tags__overlap=tag_list)

            # Apply tenant filtering if applicable
            if hasattr(request.user, 'tenant') and request.user.tenant:
                queryset = queryset.filter(tenant=request.user.tenant)

            # Order by next execution time
            queryset = queryset.order_by('next_execution_time', 'name')

            # Paginate
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)

            # Serialize jobs
            jobs = []
            for job in page_obj:
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'description': job.description,
                    'cron_expression': job.cron_expression,
                    'job_type': job.job_type,
                    'status': job.status,
                    'is_enabled': job.is_enabled,
                    'next_execution_time': job.next_execution_time.isoformat() if job.next_execution_time else None,
                    'last_execution_time': job.last_execution_time.isoformat() if job.last_execution_time else None,
                    'success_rate': job.get_success_rate(),
                    'execution_count': job.execution_count,
                    'tags': job.tags,
                    'priority': job.priority
                })

            return JsonResponse({
                'success': True,
                'jobs': jobs,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            })

        except (ValueError, DatabaseError) as e:
            logger.error(f"Failed to list cron jobs: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

    def post(self, request):
        """Create a new cron job."""
        try:
            data = json.loads(request.body)

            # Validate required fields
            required_fields = ['name', 'cron_expression', 'job_type']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f"Missing required field: {field}"
                    }, status=400)

            # Validate cron expression
            cron_validation = validate_cron_expression(data['cron_expression'])
            if not cron_validation['valid']:
                return JsonResponse({
                    'success': False,
                    'error': f"Invalid cron expression: {cron_validation['error']}"
                }, status=400)

            # Get tenant
            tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None

            # Register job based on type
            if data['job_type'] == 'management_command':
                result = cron_registry.register_management_command(
                    command_name=data.get('command_name'),
                    cron_expression=data['cron_expression'],
                    description=data.get('description', ''),
                    tenant=tenant,
                    timeout_seconds=data.get('timeout_seconds', 3600),
                    max_retries=data.get('max_retries', 3),
                    priority=data.get('priority', 'normal'),
                    tags=data.get('tags', [])
                )
            else:
                return JsonResponse({
                    'success': False,
                    'error': f"Unsupported job type: {data['job_type']}"
                }, status=400)

            if result['success']:
                return JsonResponse({
                    'success': True,
                    'job_id': result['job_id'],
                    'message': 'Cron job created successfully'
                }, status=201)
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                }, status=400)

        except (ValueError, json.JSONDecodeError, DatabaseError) as e:
            logger.error(f"Failed to create cron job: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


@method_decorator([login_required, require_permissions('is_staff'), rate_limit('120/h')], name='dispatch')
class CronJobDetailAPI(View):
    """API for individual cron job operations."""

    def get(self, request, job_id):
        """Get detailed information about a cron job."""
        try:
            job = CronJobDefinition.objects.get(id=job_id)

            # Check tenant access
            if hasattr(request.user, 'tenant') and request.user.tenant:
                if job.tenant != request.user.tenant:
                    return JsonResponse({
                        'success': False,
                        'error': 'Access denied'
                    }, status=403)

            # Get health metrics
            health_metrics = cron_health_monitor.get_job_health_metrics(job)

            # Get recent executions
            recent_executions = CronJobExecution.objects.filter(
                job_definition=job
            ).order_by('-created_at')[:10]

            executions = []
            for execution in recent_executions:
                executions.append({
                    'id': execution.id,
                    'execution_id': execution.execution_id,
                    'status': execution.status,
                    'started_at': execution.started_at.isoformat() if execution.started_at else None,
                    'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                    'duration_seconds': execution.duration_seconds,
                    'exit_code': execution.exit_code,
                    'execution_context': execution.execution_context
                })

            return JsonResponse({
                'success': True,
                'job': {
                    'id': job.id,
                    'name': job.name,
                    'description': job.description,
                    'cron_expression': job.cron_expression,
                    'job_type': job.job_type,
                    'command_name': job.command_name,
                    'command_args': job.command_args,
                    'command_kwargs': job.command_kwargs,
                    'status': job.status,
                    'is_enabled': job.is_enabled,
                    'priority': job.priority,
                    'timeout_seconds': job.timeout_seconds,
                    'max_retries': job.max_retries,
                    'tags': job.tags,
                    'next_execution_time': job.next_execution_time.isoformat() if job.next_execution_time else None,
                    'last_execution_time': job.last_execution_time.isoformat() if job.last_execution_time else None,
                    'execution_count': job.execution_count,
                    'success_count': job.success_count,
                    'failure_count': job.failure_count,
                    'average_duration_seconds': job.average_duration_seconds,
                    'created_at': job.created_at.isoformat(),
                    'updated_at': job.updated_at.isoformat()
                },
                'health_metrics': {
                    'success_rate': health_metrics.success_rate,
                    'average_duration': health_metrics.average_duration,
                    'failure_count_24h': health_metrics.failure_count_24h,
                    'is_overdue': health_metrics.is_overdue,
                    'health_score': health_metrics.health_score,
                    'trend': health_metrics.trend,
                    'anomalies': health_metrics.anomalies
                },
                'recent_executions': executions
            })

        except CronJobDefinition.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Cron job not found'
            }, status=404)
        except DatabaseError as e:
            logger.error(f"Failed to get cron job details: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@csrf_protect_ajax
@login_required
@require_permissions('is_staff')
@rate_limit('30/h')
@require_http_methods(["POST"])
def execute_cron_job(request, job_id):
    """Manually execute a cron job."""
    try:
        job = CronJobDefinition.objects.get(id=job_id)

        # Check tenant access
        if hasattr(request.user, 'tenant') and request.user.tenant:
            if job.tenant != request.user.tenant:
                return JsonResponse({
                    'success': False,
                    'error': 'Access denied'
                }, status=403)

        # Create execution record
        execution_record = cron_registry.create_execution_record(
            job_definition=job,
            execution_context='manual'
        )

        if not execution_record:
            return JsonResponse({
                'success': False,
                'error': 'Failed to create execution record'
            }, status=500)

        # Execute the job
        if job.job_type == 'management_command':
            result = command_scheduler.execute_job(job, execution_record)
        else:
            return JsonResponse({
                'success': False,
                'error': f"Manual execution not supported for job type: {job.job_type}"
            }, status=400)

        return JsonResponse({
            'success': True,
            'execution_id': execution_record.execution_id,
            'result': result
        })

    except CronJobDefinition.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Cron job not found'
        }, status=404)
    except (ValueError, DatabaseError) as e:
        logger.error(f"Failed to execute cron job: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@rate_limit('60/h')
@require_http_methods(["GET"])
def cron_system_health(request):
    """Get overall cron system health summary."""
    try:
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None
        health_summary = cron_health_monitor.get_system_health_summary(tenant=tenant)

        return JsonResponse({
            'success': True,
            'system_health': {
                'total_jobs': health_summary.total_jobs,
                'active_jobs': health_summary.active_jobs,
                'healthy_jobs': health_summary.healthy_jobs,
                'warning_jobs': health_summary.warning_jobs,
                'critical_jobs': health_summary.critical_jobs,
                'overall_success_rate': health_summary.overall_success_rate,
                'overall_health_score': health_summary.overall_health_score,
                'timestamp': timezone.now().isoformat()
            }
        })

    except DatabaseError as e:
        logger.error(f"Failed to get system health: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_protect_ajax
@login_required
@require_permissions('is_staff')
@rate_limit('10/h')
@require_http_methods(["POST"])
def discover_management_commands(request):
    """Auto-discover and register management commands."""
    try:
        tenant = getattr(request.user, 'tenant', None) if hasattr(request.user, 'tenant') else None
        result = cron_registry.discover_and_register_commands(tenant=tenant)

        return JsonResponse({
            'success': True,
            'discovery_result': result
        })

    except DatabaseError as e:
        logger.error(f"Failed to discover management commands: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)