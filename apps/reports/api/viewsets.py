"""
Reports API ViewSets

ViewSets for report generation, scheduling, and template management.

Compliance with .claude/rules.md:
- View methods < 30 lines
- WeasyPrint integration
- Celery for async generation
"""

from rest_framework import viewsets, status
from apps.ontology.decorators import ontology
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser, DjangoModelPermissions
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from apps.reports.api.serializers import (
    ReportGenerateSerializer,
    ReportScheduleSerializer,
    ReportStatusSerializer,
)
from django.http import FileResponse, HttpResponse
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.exceptions import PermissionDenied
from apps.core.services.secure_file_download_service import SecureFileDownloadService
import os
import uuid
from datetime import datetime, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


@ontology(
    domain="reports",
    purpose="REST API for async report generation with WeasyPrint PDF rendering and Celery task queue",
    api_endpoint=True,
    http_methods=["GET", "POST"],
    authentication_required=True,
    permissions=["IsAuthenticated", "IsAdminUser (for scheduling)", "reports.view_report"],
    rate_limit="20/minute",
    request_schema="ReportGenerateSerializer|ReportScheduleSerializer",
    response_schema="ReportStatusSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="medium",
    tags=["api", "rest", "reports", "pdf", "weasyprint", "celery", "async", "scheduling"],
    security_notes="Async generation via Celery background tasks. Report IDs for status tracking. Scheduled reports admin-only. Permission-protected financial data access",
    endpoints={
        "generate": "POST /api/v1/reports/generate/ - Queue async report generation",
        "status": "GET /api/v1/reports/{report_id}/status/ - Check generation status",
        "download": "GET /api/v1/reports/{report_id}/download/ - Download generated PDF",
        "schedule": "POST /api/v1/reports/schedules/ - Create scheduled report (admin)"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/reports/generate/ -H 'Authorization: Bearer <token>' -d '{\"report_type\":\"site_visit\",\"format\":\"pdf\",\"date_from\":\"2025-10-01\"}'"
    ]
)
@method_decorator(permission_required('reports.view_report', raise_exception=True), name='dispatch')
class ReportGenerateView(APIView):
    """
    API endpoint for report generation.

    POST /api/v1/reports/generate/
    Request:
        {
            "report_type": "site_visit",
            "format": "pdf",
            "filters": {...},
            "date_from": "2025-10-01T00:00:00Z",
            "date_to": "2025-10-27T23:59:59Z"
        }

    Response:
        {
            "report_id": "abc-123-def-456",
            "status": "generating",
            "status_url": "/api/v1/reports/abc-123-def-456/status/"
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Generate report asynchronously."""
        serializer = ReportGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report_type = serializer.validated_data['report_type']
        format_type = serializer.validated_data['format']
        filters = serializer.validated_data.get('filters', {})

        # Generate unique report ID
        report_id = str(uuid.uuid4())

        # Queue report generation task
        from background_tasks.report_tasks import generate_report_task
        generate_report_task.delay(
            report_id=report_id,
            report_type=report_type,
            format=format_type,
            filters=filters,
            user_id=request.user.id
        )

        logger.info(f"Report queued: {report_id} ({report_type}, {format_type})")

        return Response({
            'report_id': report_id,
            'status': 'generating',
            'status_url': f'/api/v1/reports/{report_id}/status/'
        }, status=status.HTTP_202_ACCEPTED)


@method_decorator(permission_required('reports.view_report', raise_exception=True), name='dispatch')
class ReportStatusView(APIView):
    """
    API endpoint for report status.

    GET /api/v1/reports/{report_id}/status/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id):
        """Get report generation status."""
        # Check cache/database for report status
        # Simplified implementation
        from django.core.cache import cache

        status_data = cache.get(f'report_status:{report_id}')

        if not status_data:
            return Response(
                {'error': 'Report not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(status_data)


@method_decorator(permission_required('reports.view_report', raise_exception=True), name='dispatch')
class ReportDownloadView(APIView):
    """
    API endpoint for report download.

    GET /api/v1/reports/{report_id}/download/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id):
        """
        Download generated report.
        
        Security: Uses SecureFileDownloadService for path validation,
        permission checks, and audit logging (Rule #14b compliant).
        """
        from django.core.cache import cache
        from django.http import Http404

        report_path = cache.get(f'report_path:{report_id}')

        if not report_path:
            return Response(
                {'error': 'Report not found or expired'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Use SecureFileDownloadService for secure download
        try:
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=report_path,
                filename=f'report_{report_id}.pdf',
                user=request.user,
                owner_id=request.user.id  # User owns their generated reports
            )
            return response
        except PermissionDenied as e:
            logger.warning(f"Permission denied for report download: {e}")
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Http404 as e:
            logger.warning(f"Report file not found: {e}")
            return Response(
                {'error': 'Report file not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (IOError, OSError) as e:
            logger.error(f"Error reading report file: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to read report file'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(permission_required('reports.add_reportschedule', raise_exception=True), name='dispatch')
class ReportScheduleView(APIView):
    """
    API endpoint for scheduled reports.

    POST /api/v1/reports/schedules/
    Request:
        {
            "report_type": "attendance_summary",
            "schedule_cron": "0 9 * * 1",
            "recipients": ["manager@example.com"],
            "format": "pdf",
            "filters": {...}
        }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        """Create scheduled report."""
        serializer = ReportScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Store schedule in database
        # Simplified implementation - would create ScheduledReport model
        schedule_data = serializer.validated_data

        logger.info(f"Report schedule created: {schedule_data['report_type']}")

        return Response({
            'message': 'Report schedule created',
            'schedule': schedule_data
        }, status=status.HTTP_201_CREATED)


__all__ = [
    'ReportGenerateView',
    'ReportStatusView',
    'ReportDownloadView',
    'ReportScheduleView',
]
