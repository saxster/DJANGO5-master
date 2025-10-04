"""
Attendance Sync Views for Mobile REST API

Provides sync and delta pull endpoints for Tracking (Attendance) records.

Following .claude/rules.md:
- Rule #7: View <30 lines per method
- Rule #11: Specific exception handling
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from apps.attendance.services.attendance_sync_service import AttendanceSyncService
from apps.attendance.serializers.attendance_sync_serializers import AttendanceSyncSerializer
from apps.api.v1.serializers.sync_base_serializers import (
    SyncRequestSerializer,
    DeltaSyncRequestSerializer,
)
from apps.api.v1.services.idempotency_service import IdempotencyService

logger = logging.getLogger(__name__)


class AttendanceSyncView(APIView):
    """POST /api/v1/attendance/sync/ - Bulk upsert attendance records."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Process bulk attendance sync from mobile client."""
        try:
            idempotency_key = request.headers.get('Idempotency-Key')

            if idempotency_key:
                cached_response = IdempotencyService.check_duplicate(idempotency_key)
                if cached_response:
                    return Response(cached_response, status=status.HTTP_200_OK)

            request_serializer = SyncRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=True)

            sync_service = AttendanceSyncService()
            result = sync_service.sync_attendance(
                user=request.user,
                sync_data=request_serializer.validated_data,
                serializer_class=AttendanceSyncSerializer
            )

            if idempotency_key:
                IdempotencyService.store_response(
                    idempotency_key=idempotency_key,
                    request_hash=idempotency_key,
                    response_data=result,
                    user_id=str(request.user.id),
                    device_id=request_serializer.validated_data.get('client_id'),
                    endpoint='/api/v1/attendance/sync/'
                )

            return Response(result, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response({'error': 'Database unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class AttendanceChangesView(APIView):
    """GET /api/v1/attendance/changes/ - Delta sync for attendance records."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get attendance changes for delta sync."""
        try:
            request_serializer = DeltaSyncRequestSerializer(data=request.query_params)
            request_serializer.is_valid(raise_exception=True)

            sync_service = AttendanceSyncService()
            result = sync_service.get_attendance_changes(
                user=request.user,
                timestamp=request_serializer.validated_data.get('since'),
                date_from=request.query_params.get('date_from'),
                limit=request_serializer.validated_data.get('limit', 100)
            )

            serialized_items = AttendanceSyncSerializer(result['items'], many=True).data

            return Response({
                'items': serialized_items,
                'has_more': result['has_more'],
                'next_timestamp': result['next_timestamp']
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response({'error': 'Database unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)