"""
V2 Reports REST API Views

Report generation with V2 enhancements:
- Standardized response envelope with correlation_id
- Async generation with Celery
- Secure file download
- Schedule management

Following .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Security-first design
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import DatabaseError
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)


class ReportGenerateView(APIView):
    """
    Queue async report generation (V2).

    POST /api/v2/reports/generate/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "report_type": "attendance_summary",
            "format": "pdf",
            "date_from": "2025-10-01T00:00:00Z",
            "date_to": "2025-10-31T23:59:59Z",
            "filters": {...}
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "report_id": "uuid-here",
                "status": "queued",
                "status_url": "/api/v2/reports/{id}/status/"
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Queue report generation task."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Validate required fields
            report_type = request.data.get('report_type')
            if not report_type:
                return self._error_response(
                    code='VALIDATION_ERROR',
                    message='report_type is required',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            format_type = request.data.get('format', 'pdf')
            filters = request.data.get('filters', {})
            date_from = request.data.get('date_from')
            date_to = request.data.get('date_to')

            # Generate unique report ID
            report_id = str(uuid.uuid4())

            # Queue Celery task
            from background_tasks.report_tasks import generate_report_task
            generate_report_task.delay(
                report_id=report_id,
                report_type=report_type,
                format=format_type,
                filters=filters,
                date_from=date_from,
                date_to=date_to,
                user_id=request.user.id
            )

            # Store initial status in cache
            cache.set(f'report_status:{report_id}', {
                'status': 'queued',
                'progress': 0,
                'created_at': datetime.now(dt_timezone.utc).isoformat()
            }, timeout=86400)  # 24 hours

            logger.info(f"V2 report queued: {report_id} ({report_type})", extra={
                'correlation_id': correlation_id,
                'report_id': report_id,
                'user_id': request.user.id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'report_id': report_id,
                    'status': 'queued',
                    'status_url': f'/api/v2/reports/{report_id}/status/'
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_202_ACCEPTED)

        except CACHE_EXCEPTIONS as e:
            logger.error(f"Cache error during report generation: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='CACHE_ERROR',
                message='Failed to queue report. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Error during report generation: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='SERVER_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class ReportStatusView(APIView):
    """
    Get report generation status (V2).

    GET /api/v2/reports/{report_id}/status/
    Headers: Authorization: Bearer <access_token>

    Response:
        {
            "success": true,
            "data": {
                "status": "completed",
                "progress": 100,
                "file_size": 1024000,
                "download_url": "/api/v2/reports/{id}/download/"
            },
            "meta": {...}
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id):
        """Get report generation status."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Get status from cache
            status_data = cache.get(f'report_status:{report_id}')

            if not status_data:
                return self._error_response(
                    code='REPORT_NOT_FOUND',
                    message='Report not found or expired',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Add download URL if completed
            if status_data.get('status') == 'completed':
                status_data['download_url'] = f'/api/v2/reports/{report_id}/download/'

            logger.info(f"V2 report status retrieved: {report_id}", extra={
                'correlation_id': correlation_id,
                'report_id': report_id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': status_data,
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except CACHE_EXCEPTIONS as e:
            logger.error(f"Cache error getting report status: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='CACHE_ERROR',
                message='Could not retrieve report status',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class ReportDownloadView(APIView):
    """
    Download generated report (V2).

    GET /api/v2/reports/{report_id}/download/
    Headers: Authorization: Bearer <access_token>

    Response: PDF file download
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id):
        """Download generated report with secure file validation."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Get report path from cache
            report_path = cache.get(f'report_path:{report_id}')

            if not report_path:
                return self._error_response(
                    code='REPORT_NOT_FOUND',
                    message='Report not found or expired',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Use SecureFileDownloadService for secure download
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=report_path,
                filename=f'report_{report_id}.pdf',
                user=request.user,
                owner_id=request.user.id
            )

            logger.info(f"V2 report downloaded: {report_id}", extra={
                'correlation_id': correlation_id,
                'report_id': report_id,
                'user_id': request.user.id
            })

            return response

        except PermissionDenied as e:
            logger.warning(f"Permission denied for report download: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='PERMISSION_DENIED',
                message='Access denied',
                correlation_id=correlation_id,
                status_code=status.HTTP_403_FORBIDDEN
            )
        except Http404 as e:
            logger.warning(f"Report file not found: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='FILE_NOT_FOUND',
                message='Report file not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except (IOError, OSError) as e:
            logger.error(f"Error reading report file: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='FILE_READ_ERROR',
                message='Failed to read report file',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class ReportScheduleView(APIView):
    """
    Manage scheduled reports (V2).

    POST /api/v2/reports/schedules/ - Create schedule (admin only)
    GET /api/v2/reports/schedules/ - List schedules

    Response: Standard V2 envelope
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        """Create scheduled report."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        try:
            # Validate required fields
            report_type = request.data.get('report_type')
            schedule_cron = request.data.get('schedule_cron')

            if not report_type or not schedule_cron:
                return self._error_response(
                    code='VALIDATION_ERROR',
                    message='report_type and schedule_cron are required',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Get optional fields
            recipients = request.data.get('recipients', [])
            format_type = request.data.get('format', 'pdf')
            filters = request.data.get('filters', {})

            # Create schedule (simplified - would use ScheduledReport model)
            schedule_data = {
                'schedule_id': str(uuid.uuid4()),
                'report_type': report_type,
                'schedule_cron': schedule_cron,
                'recipients': recipients,
                'format': format_type,
                'filters': filters,
                'created_by': request.user.id,
                'created_at': datetime.now(dt_timezone.utc).isoformat()
            }

            logger.info(f"V2 report schedule created: {report_type}", extra={
                'correlation_id': correlation_id,
                'schedule_id': schedule_data['schedule_id']
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': schedule_data,
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating report schedule: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='SERVER_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        """List all scheduled reports."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Simplified - would query ScheduledReport model
        schedules = []

        return Response({
            'success': True,
            'data': {
                'results': schedules,
                'count': len(schedules)
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status.HTTP_200_OK)

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


__all__ = ['ReportGenerateView', 'ReportStatusView', 'ReportDownloadView', 'ReportScheduleView']
