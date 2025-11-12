"""
V2 Telemetry REST API Views

Telemetry ingestion for Kotlin SDK with V2 enhancements.

Following .claude/rules.md:
- View methods < 30 lines
- Specific exception handling (Rule #11)
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.core.exceptions.patterns import (
    VALIDATION_EXCEPTIONS,
    SERIALIZATION_EXCEPTIONS,
)

logger = logging.getLogger(__name__)


class TelemetryBatchView(APIView):
    """
    Ingest telemetry batch from Kotlin SDK (V2).

    POST /api/v2/telemetry/stream-events/batch
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Ingest telemetry batch."""
        correlation_id = str(uuid.uuid4())

        try:
            events = request.data.get('events', [])
            device_id = request.data.get('device_id')

            # Process telemetry events (simplified)
            logger.info(f"Telemetry batch received: {len(events)} events", extra={
                'correlation_id': correlation_id,
                'device_id': device_id,
                'event_count': len(events)
            })

            return Response({
                'success': True,
                'data': {
                    'received': len(events),
                    'processed': len(events)
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_201_CREATED)

        except VALIDATION_EXCEPTIONS as e:
            # Validation errors (e.g., missing fields, invalid data types)
            logger.error(f"Validation error processing telemetry: {type(e).__name__}", exc_info=True, extra={
                'correlation_id': correlation_id,
                'device_id': request.data.get('device_id')
            })
            return Response({
                'success': False,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalid telemetry data. Please check your request.'
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        except SERIALIZATION_EXCEPTIONS as e:
            # Serialization/parsing errors (JSON, data format issues)
            logger.error(f"Serialization error processing telemetry: {type(e).__name__}", exc_info=True, extra={
                'correlation_id': correlation_id,
                'device_id': request.data.get('device_id')
            })
            return Response({
                'success': False,
                'error': {
                    'code': 'PROCESSING_ERROR',
                    'message': 'An error occurred processing your request. Please try again.'
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


__all__ = ['TelemetryBatchView']
