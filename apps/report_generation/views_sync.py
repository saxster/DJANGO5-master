"""
Report Sync Views for Mobile API

Provides sync endpoints for Kotlin Android app following established patterns.

Endpoints:
- POST /api/v1/reports/sync/ - Bulk upsert reports from mobile
- GET  /api/v1/reports/changes/ - Delta sync (get server changes)

Following .claude/rules.md:
- Rule #7: View <30 lines per method
- Rule #11: Specific exception handling
- Rule #12: Rate limiting
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from apps.report_generation.services.report_sync_service import ReportSyncService
from apps.core.services.sync.idempotency_service import IdempotencyService

logger = logging.getLogger(__name__)


class ReportSyncView(APIView):
    """
    POST /api/v1/reports/sync/
    
    Bulk upsert reports from Kotlin mobile client with idempotency.
    
    Request:
    {
        "entries": [
            {
                "mobile_id": "temp-uuid-001",
                "template_id": 1,
                "title": "Pump failure incident",
                "report_data": {...},
                "created_at": "2025-11-07T10:15:00Z",
                "status": "draft"
            }
        ],
        "attachments": [
            {
                "mobile_id": "attach-001",
                "report_mobile_id": "temp-uuid-001",
                "file_base64": "...",
                "filename": "pump_damage.jpg",
                "metadata": {...}
            }
        ],
        "last_sync_timestamp": "2025-11-07T09:00:00Z",
        "client_id": "android-device-uuid"
    }
    
    Response:
    {
        "synced_reports": [
            {
                "mobile_id": "temp-uuid-001",
                "server_id": 456,
                "status": "created",
                "ai_analysis_queued": true
            }
        ],
        "synced_attachments": [...],
        "conflicts": [],
        "errors": [],
        "next_sync_timestamp": "2025-11-07T14:30:00Z"
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Process bulk report sync from mobile client."""
        try:
            idempotency_key = request.headers.get('Idempotency-Key')
            
            # Check for duplicate request
            if idempotency_key:
                cached_response = IdempotencyService.check_duplicate(idempotency_key)
                if cached_response:
                    logger.info(f"Returning cached response for {idempotency_key[:16]}...")
                    return Response(cached_response, status=status.HTTP_200_OK)
            
            # Validate request
            if not request.data.get('entries'):
                return Response(
                    {'error': 'No entries provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process reports
            sync_service = ReportSyncService()
            
            from apps.report_generation.serializers import ReportSyncSerializer
            report_result = sync_service.sync_reports(
                user=request.user,
                sync_data=request.data,
                serializer_class=ReportSyncSerializer
            )
            
            # Process attachments
            attachment_result = {'processed': 0, 'failed': []}
            if request.data.get('attachments'):
                attachment_result = sync_service.sync_attachments(
                    user=request.user,
                    attachment_data=request.data['attachments']
                )
            
            # Combined result
            result = {
                **report_result,
                'synced_attachments': attachment_result['processed'],
                'attachment_errors': attachment_result['failed'],
                'next_sync_timestamp': timezone.now().isoformat()
            }
            
            # Cache response for idempotency
            if idempotency_key:
                IdempotencyService.store_response(
                    idempotency_key=idempotency_key,
                    request_hash=idempotency_key,
                    response_data=result,
                    user_id=str(request.user.id),
                    device_id=request.data.get('client_id'),
                    endpoint='/api/v1/reports/sync/'
                )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            logger.warning(f"Validation error in report sync: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error in report sync: {e}", exc_info=True)
            return Response(
                {'error': 'Database unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class ReportChangesView(APIView):
    """
    GET /api/v1/reports/changes/?since=<timestamp>&limit=100
    
    Delta sync: Get reports changed since timestamp.
    Allows Kotlin app to pull supervisor edits/approvals.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get report changes for delta sync."""
        from django.utils.dateparse import parse_datetime
        
        since_param = request.query_params.get('since')
        limit = int(request.query_params.get('limit', 100))
        
        if not since_param:
            return Response(
                {'error': 'since parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            since = parse_datetime(since_param)
            if not since:
                raise ValueError("Invalid datetime format")
            
            # Get changed reports (only ones user has access to)
            changed_reports = GeneratedReport.objects.filter(
                tenant=request.user.tenant,
                updated_at__gt=since
            ).filter(
                Q(author=request.user) | Q(reviewed_by=request.user)
            ).select_related('template', 'reviewed_by').order_by('updated_at')[:limit]
            
            from apps.report_generation.serializers import ReportSyncSerializer
            serializer = ReportSyncSerializer(changed_reports, many=True)
            
            has_more = GeneratedReport.objects.filter(
                tenant=request.user.tenant,
                updated_at__gt=since
            ).count() > limit
            
            return Response({
                'changes': serializer.data,
                'has_more': has_more,
                'next_timestamp': timezone.now().isoformat(),
                'count': len(serializer.data)
            })
            
        except (ValueError, ValidationError) as e:
            return Response(
                {'error': f'Invalid parameters: {e}'},
                status=status.HTTP_400_BAD_REQUEST
            )


from django.utils import timezone
from django.db.models import Q
