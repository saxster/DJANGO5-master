"""
V2 Telemetry REST API Views

Telemetry ingestion for Kotlin SDK with V2 enhancements.

Following .claude/rules.md:
- View methods < 30 lines
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

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

        except Exception as e:
            logger.error(f"Error processing telemetry: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': {
                    'code': 'PROCESSING_ERROR',
                    'message': str(e)
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


__all__ = ['TelemetryBatchView']
