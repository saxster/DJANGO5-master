"""
Task Sync Views for Mobile REST API

Provides sync and delta pull endpoints for JobNeed (Task) records.

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

from apps.activity.services.task_sync_service import TaskSyncService
from apps.activity.serializers.task_sync_serializers import TaskSyncSerializer
from apps.core.serializers.sync_base_serializers import (
    SyncRequestSerializer,
    SyncResponseSerializer,
    DeltaSyncRequestSerializer,
)
from apps.core.services.sync.idempotency_service import IdempotencyService

logger = logging.getLogger(__name__)


class TaskSyncView(APIView):
    """
    POST /api/v1/activity/sync/

    Bulk upsert tasks from mobile client with idempotency support.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Process bulk task sync from mobile client."""
        try:
            idempotency_key = request.headers.get('Idempotency-Key')

            if idempotency_key:
                cached_response = IdempotencyService.check_duplicate(idempotency_key)
                if cached_response:
                    logger.info(f"Returning cached response for {idempotency_key[:16]}...")
                    return Response(cached_response, status=status.HTTP_200_OK)

            request_serializer = SyncRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=True)

            sync_service = TaskSyncService()
            result = sync_service.sync_tasks(
                user=request.user,
                sync_data=request_serializer.validated_data,
                serializer_class=TaskSyncSerializer
            )

            if idempotency_key:
                IdempotencyService.store_response(
                    idempotency_key=idempotency_key,
                    request_hash=idempotency_key,
                    response_data=result,
                    user_id=str(request.user.id),
                    device_id=request_serializer.validated_data.get('client_id'),
                    endpoint='/api/v1/activity/sync/'
                )

            return Response(result, status=status.HTTP_200_OK)

        except ValidationError as e:
            logger.warning(f"Validation error in task sync: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error in task sync: {e}", exc_info=True)
            return Response(
                {'error': 'Database unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class TaskChangesView(APIView):
    """
    GET /api/v1/activity/changes/?since=<timestamp>&limit=100

    Delta sync: Get tasks changed since timestamp.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get task changes for delta sync."""
        try:
            request_serializer = DeltaSyncRequestSerializer(data=request.query_params)
            request_serializer.is_valid(raise_exception=True)

            sync_service = TaskSyncService()
            result = sync_service.get_task_changes(
                user=request.user,
                timestamp=request_serializer.validated_data.get('since'),
                limit=request_serializer.validated_data.get('limit', 100)
            )

            serialized_items = TaskSyncSerializer(result['items'], many=True).data

            return Response({
                'items': serialized_items,
                'has_more': result['has_more'],
                'next_timestamp': result['next_timestamp']
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            logger.warning(f"Validation error in task changes: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error in task changes: {e}", exc_info=True)
            return Response(
                {'error': 'Database unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )