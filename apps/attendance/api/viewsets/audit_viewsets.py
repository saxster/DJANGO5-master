"""
Audit Log API ViewSets

REST API endpoints for accessing and analyzing audit logs.

Permissions:
- Admin only (requires 'view_audit_log' permission)
- Filtered by tenant automatically

Endpoints:
- GET /api/v1/attendance/audit-logs/ - List audit logs
- GET /api/v1/attendance/audit-logs/{id}/ - Retrieve specific log
- GET /api/v1/attendance/audit-logs/statistics/ - Access statistics
- GET /api/v1/attendance/audit-logs/user-activity/{user_id}/ - User activity
- GET /api/v1/attendance/audit-logs/record-history/{record_id}/ - Record access history
- GET /api/v1/attendance/audit-logs/compliance-report/ - Generate compliance report
- POST /api/v1/attendance/audit-logs/investigate/ - Investigate user
- GET /api/v1/attendance/audit-logs/export/ - Export to CSV
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import HttpResponse
from typing import Optional

from apps.attendance.models.audit_log import AttendanceAccessLog
from apps.attendance.api.serializers.audit_serializers import (
    AttendanceAccessLogSerializer,
    AuditLogFilterSerializer,
    ComplianceReportRequestSerializer,
    InvestigationRequestSerializer,
)
from apps.attendance.services.audit_service import (
    AuditQueryService,
    AuditAnalyticsService,
    AuditReportService,
    AuditInvestigationService,
)
from apps.core.permissions import TenantIsolationPermission
import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class AttendanceAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for attendance audit logs.

    Provides read-only access to audit logs with advanced filtering,
    analytics, and reporting capabilities.

    Permissions:
    - Must be authenticated
    - Must have 'view_audit_log' permission
    - Automatic tenant isolation
    """

    queryset = AttendanceAccessLog.objects.all()
    serializer_class = AttendanceAccessLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]

    # Filterable fields
    filterset_fields = {
        'user': ['exact'],
        'action': ['exact', 'in'],
        'resource_type': ['exact', 'in'],
        'status_code': ['exact', 'gte', 'lte'],
        'is_suspicious': ['exact'],
        'timestamp': ['gte', 'lte', 'exact'],
        'ip_address': ['exact'],
    }

    # Orderable fields
    ordering_fields = ['timestamp', 'duration_ms', 'risk_score', 'status_code']
    ordering = ['-timestamp']  # Default ordering

    # Searchable fields
    search_fields = ['user__username', 'ip_address', 'correlation_id', 'notes']

    def get_queryset(self):
        """
        Filter queryset by tenant and permissions.

        Optimized with select_related for performance.
        """
        queryset = super().get_queryset()

        # Apply tenant filtering (handled by TenantIsolationPermission)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(tenant=self.request.user.client_id)

        # Optimize queries
        queryset = queryset.select_related('user', 'attendance_record', 'impersonated_by')

        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get access statistics for the specified period.

        Query Parameters:
        - days: Number of days to analyze (default: 30)

        Returns:
            Access statistics including counts, averages, and breakdowns
        """
        days = int(request.query_params.get('days', 30))

        try:
            stats = AuditAnalyticsService.get_access_statistics(days)
            return Response(stats)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to get audit statistics: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to generate statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='user-activity/(?P<user_id>[0-9]+)')
    def user_activity(self, request, user_id=None):
        """
        Get activity for a specific user.

        Query Parameters:
        - days: Number of days to look back (default: 30)

        Returns:
            List of audit logs for the user
        """
        days = int(request.query_params.get('days', 30))

        try:
            logs = AuditQueryService.get_user_activity(int(user_id), days)
            serializer = self.get_serializer(logs, many=True)
            return Response(serializer.data)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to get user activity: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to retrieve user activity'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='record-history/(?P<record_id>[0-9]+)')
    def record_history(self, request, record_id=None):
        """
        Get complete access history for an attendance record.

        Returns:
            Detailed access history and analysis
        """
        try:
            history = AuditInvestigationService.trace_data_access(int(record_id))
            return Response(history)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to get record history: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to retrieve record history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def failed_attempts(self, request):
        """
        Get all failed access attempts.

        Query Parameters:
        - hours: Number of hours to look back (default: 24)

        Returns:
            List of failed access attempts
        """
        hours = int(request.query_params.get('hours', 24))

        try:
            logs = AuditQueryService.get_failed_access_attempts(hours)
            serializer = self.get_serializer(logs, many=True)
            return Response(serializer.data)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to get failed attempts: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to retrieve failed attempts'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def most_accessed(self, request):
        """
        Get most frequently accessed attendance records.

        Query Parameters:
        - days: Number of days to analyze (default: 30)
        - limit: Number of records to return (default: 10)

        Returns:
            List of most accessed records
        """
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))

        try:
            records = AuditAnalyticsService.get_most_accessed_records(days, limit)
            return Response(records)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to get most accessed records: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to retrieve most accessed records'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def compliance_report(self, request):
        """
        Generate compliance audit report.

        Request Body:
        {
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "tenant": "optional-tenant-id"
        }

        Returns:
            Comprehensive compliance report
        """
        serializer = ComplianceReportRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']
            tenant = serializer.validated_data.get('tenant')

            report = AuditReportService.generate_compliance_report(
                start_date, end_date, tenant
            )

            return Response(report)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to generate compliance report: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to generate compliance report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def investigate(self, request):
        """
        Investigate a user's access patterns.

        Request Body:
        {
            "user_id": 123,
            "days": 90
        }

        Returns:
            Comprehensive investigation report
        """
        serializer = InvestigationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_id = serializer.validated_data['user_id']
            days = serializer.validated_data.get('days', 90)

            investigation = AuditInvestigationService.investigate_user(user_id, days)

            return Response(investigation)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to investigate user: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to complete investigation'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export audit logs to CSV.

        Query Parameters:
        - Same as list endpoint (supports all filters)
        - Format: CSV

        Returns:
            CSV file download
        """
        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        try:
            # Generate temporary filename
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/tmp/audit_logs_{timestamp}.csv'

            # Export to CSV
            AuditReportService.export_to_csv(queryset, filename)

            # Read file and return as HTTP response
            with open(filename, 'rb') as f:
                response = HttpResponse(f.read(), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="audit_logs_{timestamp}.csv"'
                return response

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to export audit logs: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to export audit logs'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='user-patterns/(?P<user_id>[0-9]+)')
    def user_patterns(self, request, user_id=None):
        """
        Analyze access patterns for a specific user.

        Query Parameters:
        - days: Number of days to analyze (default: 30)

        Returns:
            Detailed access pattern analysis
        """
        days = int(request.query_params.get('days', 30))

        try:
            patterns = AuditAnalyticsService.get_user_access_patterns(int(user_id), days)
            return Response(patterns)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to analyze user patterns: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to analyze access patterns'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='detect-anomalies/(?P<user_id>[0-9]+)')
    def detect_anomalies(self, request, user_id=None):
        """
        Detect anomalous access patterns for a user.

        Query Parameters:
        - days: Number of days to analyze (default: 30)

        Returns:
            List of detected anomalies
        """
        days = int(request.query_params.get('days', 30))

        try:
            anomalies = AuditAnalyticsService.detect_anomalies(int(user_id), days)
            return Response({'anomalies': anomalies})
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Failed to detect anomalies: {e}", exc_info=True, exc_info=True)
            return Response(
                {'error': 'Failed to detect anomalies'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
