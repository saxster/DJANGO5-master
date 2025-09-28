"""
Refactored Reports Views - Async Operations

This file demonstrates how to refactor the blocking operations in reports views
to use async tasks, providing better performance and user experience.

Key improvements:
- PDF generation moved to background tasks
- External API calls handled asynchronously
- Progress tracking for long-running operations
- Immediate response with task status
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic.base import View

from apps.core.services.async_pdf_service import AsyncPDFGenerationService
from apps.core.services.async_api_service import AsyncExternalAPIService
from apps.core.utils_new.file_utils import secure_file_path
from apps.reports import forms as rp_forms
from apps.reports import utils as rutils


logger = logging.getLogger(__name__)


class AsyncReportGenerationView(LoginRequiredMixin, View):
    """
    Refactored report generation view that handles PDF generation asynchronously.

    Instead of blocking the request with WeasyPrint operations, this view:
    1. Immediately returns a task ID to the user
    2. Generates PDF in background
    3. Provides status endpoint for progress tracking
    4. Serves completed PDF when ready
    """

    def post(self, request, *args, **kwargs):
        """
        Initiate async PDF generation for reports.

        Returns immediate response with task tracking information.
        """
        try:
            # Validate form data
            form = rp_forms.ReportGenerationForm(request.POST)
            if not form.is_valid():
                return JsonResponse({
                    'status': 'error',
                    'errors': form.errors
                }, status=400)

            # Extract report parameters
            report_type = form.cleaned_data['report_type']
            date_range = form.cleaned_data.get('date_range')
            filters = form.cleaned_data.get('filters', {})

            # Prepare template context
            context_data = self._prepare_report_context(
                report_type, date_range, filters, request.user
            )

            # Determine template and filename
            template_name = f'reports/{report_type}_template.html'
            filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            # CSS files for styling
            css_files = [
                'frontend/static/assets/css/local/reports.css'
            ]

            # Initialize PDF service
            pdf_service = AsyncPDFGenerationService()

            # Initiate async PDF generation
            result = pdf_service.initiate_pdf_generation(
                template_name=template_name,
                context_data=context_data,
                user_id=request.user.id,
                filename=filename,
                css_files=css_files,
                output_format='pdf'
            )

            # Log the operation
            logger.info(f"Async PDF generation initiated for user {request.user.id}: {result['task_id']}")

            # Return task information for tracking
            return JsonResponse({
                'status': 'success',
                'task_id': result['task_id'],
                'message': 'Report generation started',
                'progress_url': reverse('reports:task_status', kwargs={'task_id': result['task_id']}),
                'estimated_completion': result['estimated_completion']
            })

        except (TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to initiate report generation: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=500)

    def _prepare_report_context(
        self,
        report_type: str,
        date_range: Optional[tuple],
        filters: Dict[str, Any],
        user
    ) -> Dict[str, Any]:
        """
        Prepare template context for report generation.

        This method prepares all data needed for the report template,
        ensuring data queries are optimized and minimal.
        """
        try:
            base_context = {
                'report_type': report_type,
                'generated_at': timezone.now(),
                'generated_by': user.get_full_name() or user.username,
                'company_info': self._get_company_info(),
                'date_range': date_range,
                'filters': filters
            }

            # Add report-specific data based on type
            if report_type == 'site_visit':
                base_context.update(self._get_site_visit_data(date_range, filters))
            elif report_type == 'attendance':
                base_context.update(self._get_attendance_data(date_range, filters))
            elif report_type == 'asset_maintenance':
                base_context.update(self._get_asset_maintenance_data(date_range, filters))
            else:
                raise ValueError(f"Unsupported report type: {report_type}")

            return base_context

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to prepare report context: {str(e)}")
            raise

    def _get_company_info(self) -> Dict[str, Any]:
        """Get basic company information for report header."""
        # Implementation would fetch company details
        return {
            'name': 'Company Name',
            'address': 'Company Address',
            'logo_url': '/static/images/company_logo.png'
        }

    def _get_site_visit_data(self, date_range: Optional[tuple], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get site visit data for reports."""
        # Implementation would use optimized queries
        # with select_related and prefetch_related
        return {
            'visits': [],
            'total_visits': 0,
            'unique_sites': 0
        }

    def _get_attendance_data(self, date_range: Optional[tuple], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get attendance data for reports."""
        return {
            'attendance_records': [],
            'total_employees': 0,
            'average_attendance': 0
        }

    def _get_asset_maintenance_data(self, date_range: Optional[tuple], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get asset maintenance data for reports."""
        return {
            'maintenance_records': [],
            'total_assets': 0,
            'pending_maintenance': 0
        }


class AsyncExternalDataFetchView(LoginRequiredMixin, View):
    """
    Refactored view for fetching external API data asynchronously.

    Instead of blocking requests with external API calls, this view:
    1. Queues API calls as background tasks
    2. Returns immediate response with task tracking
    3. Provides status endpoints for monitoring
    4. Caches successful responses for performance
    """

    def post(self, request, *args, **kwargs):
        """
        Initiate async external API data fetch.
        """
        try:
            # Extract API call parameters
            api_url = request.POST.get('api_url')
            method = request.POST.get('method', 'GET')
            timeout = int(request.POST.get('timeout', 30))

            # Validate parameters
            if not api_url:
                return JsonResponse({
                    'status': 'error',
                    'message': 'API URL is required'
                }, status=400)

            # Prepare headers (exclude sensitive ones)
            headers = {
                'User-Agent': 'IntelliWiz-Reports/1.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }

            # Initialize API service
            api_service = AsyncExternalAPIService()

            # Initiate async API call
            result = api_service.initiate_api_call(
                url=api_url,
                method=method,
                headers=headers,
                timeout=timeout,
                user_id=request.user.id,
                priority='normal'
            )

            logger.info(f"Async API call initiated for user {request.user.id}: {result['task_id']}")

            return JsonResponse({
                'status': 'success',
                'task_id': result['task_id'],
                'message': 'API call queued successfully',
                'status_url': reverse('reports:api_task_status', kwargs={'task_id': result['task_id']}),
                'estimated_completion': result['estimated_completion']
            })

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Failed to initiate API call: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=500)


class TaskStatusView(LoginRequiredMixin, View):
    """
    Endpoint for checking PDF generation task status.

    Provides real-time updates on task progress and completion.
    """

    def get(self, request, task_id, *args, **kwargs):
        """Get current status of PDF generation task."""
        try:
            pdf_service = AsyncPDFGenerationService()
            status = pdf_service.get_task_status(task_id)

            # Add download URL if completed
            if status.get('status') == 'completed' and status.get('file_path'):
                status['download_url'] = reverse(
                    'reports:download_pdf',
                    kwargs={'task_id': task_id}
                )

            return JsonResponse(status)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class APITaskStatusView(LoginRequiredMixin, View):
    """
    Endpoint for checking external API call task status.
    """

    def get(self, request, task_id, *args, **kwargs):
        """Get current status of API call task."""
        try:
            api_service = AsyncExternalAPIService()
            status = api_service.get_task_status(task_id)

            return JsonResponse(status)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to get API task status: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class DownloadPDFView(LoginRequiredMixin, View):
    """
    Secure PDF download endpoint.

    Serves completed PDF files with proper access control.
    """

    def get(self, request, task_id, *args, **kwargs):
        """Download completed PDF file."""
        try:
            pdf_service = AsyncPDFGenerationService()
            status = pdf_service.get_task_status(task_id)

            if status.get('status') != 'completed':
                return JsonResponse({
                    'status': 'error',
                    'message': 'PDF not ready for download'
                }, status=404)

            file_path = status.get('file_path')
            if not file_path:
                return JsonResponse({
                    'status': 'error',
                    'message': 'File not found'
                }, status=404)

            # Serve file securely
            from django.core.files.storage import default_storage

            if default_storage.exists(file_path):
                file_obj = default_storage.open(file_path, 'rb')
                response = FileResponse(
                    file_obj,
                    content_type='application/pdf',
                    as_attachment=True,
                    filename=file_path.split('/')[-1]
                )

                logger.info(f"PDF downloaded by user {request.user.id}: {task_id}")
                return response
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'File not found'
                }, status=404)

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to download PDF: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class BulkAPICallView(LoginRequiredMixin, View):
    """
    Handle multiple external API calls in parallel.

    Demonstrates how to efficiently handle bulk operations
    without blocking the request cycle.
    """

    def post(self, request, *args, **kwargs):
        """Initiate bulk API calls."""
        try:
            import json

            # Parse bulk request data
            try:
                requests_data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid JSON data'
                }, status=400)

            api_requests = requests_data.get('requests', [])

            if not api_requests or len(api_requests) > 50:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid request count (max 50)'
                }, status=400)

            # Initialize API service
            api_service = AsyncExternalAPIService()

            # Initiate bulk API calls
            result = api_service.bulk_api_calls(
                requests=api_requests,
                user_id=request.user.id,
                priority='normal'
            )

            logger.info(f"Bulk API calls initiated for user {request.user.id}: {result['batch_id']}")

            return JsonResponse({
                'status': 'success',
                'batch_id': result['batch_id'],
                'task_ids': result['task_ids'],
                'total_requests': result['total_requests'],
                'message': 'Bulk API calls queued successfully'
            })

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            error_msg = f"Failed to initiate bulk API calls: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=500)


class TaskCancellationView(LoginRequiredMixin, View):
    """
    Allow users to cancel pending tasks.
    """

    def post(self, request, task_id, *args, **kwargs):
        """Cancel a pending task."""
        try:
            # Try PDF service first
            pdf_service = AsyncPDFGenerationService()
            pdf_status = pdf_service.get_task_status(task_id)

            if pdf_status.get('status') != 'not_found':
                # Handle PDF task cancellation
                # Implementation would cancel Celery task
                return JsonResponse({
                    'status': 'success',
                    'message': 'PDF generation task cancelled'
                })

            # Try API service
            api_service = AsyncExternalAPIService()
            result = api_service.cancel_task(task_id)

            return JsonResponse(result)

        except (DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to cancel task: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


@login_required
def async_reports_dashboard(request):
    """
    Dashboard view showing async report generation capabilities.

    Provides interface for users to:
    - Generate reports asynchronously
    - Track task progress
    - Download completed reports
    - View task history
    """
    context = {
        'available_reports': [
            'site_visit',
            'attendance',
            'asset_maintenance',
            'security_logs'
        ],
        'recent_tasks': _get_user_recent_tasks(request.user.id),
        'performance_stats': _get_performance_stats()
    }

    return render(request, 'reports/async_dashboard.html', context)


def _get_user_recent_tasks(user_id: int) -> list:
    """Get recent tasks for user."""
    # Implementation would fetch recent task history
    return []


def _get_performance_stats() -> Dict[str, Any]:
    """Get performance statistics."""
    return {
        'avg_generation_time': '45 seconds',
        'success_rate': '98.5%',
        'active_tasks': 0
    }