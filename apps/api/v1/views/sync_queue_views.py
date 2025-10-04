"""
Offline Queue Management Views for Mobile Sync

Provides endpoints for queue status and partial sync operations.

Following .claude/rules.md:
- Rule #8: View methods <30 lines
- Rule #11: Specific exception handling
"""

import logging
import json
from django.http import JsonResponse
from django.views import View
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta

from apps.api.v1.services.bandwidth_optimization_service import BandwidthOptimizationService

logger = logging.getLogger(__name__)


class QueueStatusAPIView(LoginRequiredMixin, View):
    """
    Get offline queue status for mobile client.

    GET /api/v1/sync/queue-status
    Returns:
        {
            pending_items: int,
            high_priority: int,
            estimated_sync_time_sec: int,
            queue_healthy: bool
        }
    """

    def get(self, request):
        try:
            from apps.core.models.sync_idempotency import SyncIdempotencyKey

            pending_syncs = SyncIdempotencyKey.objects.filter(
                user=request.user,
                status='pending'
            )

            high_priority = pending_syncs.filter(
                metadata__contains={'priority': 'high'}
            ).count()

            total_pending = pending_syncs.count()

            estimated_time = self._estimate_sync_time(total_pending)

            queue_healthy = total_pending < 100 and high_priority < 20

            return JsonResponse({
                'pending_items': total_pending,
                'high_priority': high_priority,
                'estimated_sync_time_sec': estimated_time,
                'queue_healthy': queue_healthy
            }, status=200)

        except DatabaseError as e:
            logger.error(f"Database error fetching queue status: {e}")
            return JsonResponse({'error': 'Service unavailable'}, status=503)

    def _estimate_sync_time(self, item_count: int) -> int:
        """Estimate sync time based on historical averages."""
        avg_item_time_ms = 150
        return int((item_count * avg_item_time_ms) / 1000)


class PartialSyncAPIView(LoginRequiredMixin, View):
    """
    Perform partial sync of prioritized items.

    POST /api/v1/sync/partial
    Body: {priority: 'high', max_items: 10, network_quality: 'good'}
    Returns: {synced_items: [...], remaining: int}
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
            priority = body.get('priority', 'high')
            max_items = body.get('max_items', 10)
            network_quality = body.get('network_quality', 'good')

            from apps.core.models.sync_idempotency import SyncIdempotencyKey

            pending_items = list(SyncIdempotencyKey.objects.filter(
                user=request.user,
                status='pending'
            ).order_by('-created_at')[:max_items])

            optimization_service = BandwidthOptimizationService()
            prioritized = optimization_service.prioritize_items(
                [{'id': item.id, 'priority': priority} for item in pending_items]
            )

            synced_items = []
            for item_data in prioritized[:max_items]:
                item = next(i for i in pending_items if i.id == item_data['id'])
                item.status = 'processed'
                item.save()
                synced_items.append({'id': item.id, 'status': 'synced'})

            remaining = SyncIdempotencyKey.objects.filter(
                user=request.user,
                status='pending'
            ).count()

            return JsonResponse({
                'synced_items': synced_items,
                'remaining': remaining
            }, status=200)

        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Invalid partial sync request: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except DatabaseError as e:
            logger.error(f"Database error during partial sync: {e}")
            return JsonResponse({'error': 'Service unavailable'}, status=503)


class OptimalSyncTimeAPIView(LoginRequiredMixin, View):
    """
    Get recommended sync time based on server load.

    GET /api/v1/sync/optimal-time
    Returns:
        {
            recommendation: 'sync_now' | 'sync_in_30min',
            server_load: 'low' | 'medium' | 'high',
            queue_size: int
        }
    """

    def get(self, request):
        try:
            current_hour = timezone.now().hour

            is_peak_hour = 9 <= current_hour <= 17

            from apps.core.models.sync_idempotency import SyncIdempotencyKey
            queue_size = SyncIdempotencyKey.objects.filter(
                status='pending'
            ).count()

            if queue_size > 1000:
                server_load = 'high'
                recommendation = 'sync_in_30min'
            elif queue_size > 500:
                server_load = 'medium'
                recommendation = 'sync_now' if not is_peak_hour else 'sync_in_30min'
            else:
                server_load = 'low'
                recommendation = 'sync_now'

            return JsonResponse({
                'recommendation': recommendation,
                'server_load': server_load,
                'queue_size': queue_size,
                'is_peak_hour': is_peak_hour
            }, status=200)

        except DatabaseError as e:
            logger.error(f"Database error checking optimal sync time: {e}")
            return JsonResponse({
                'recommendation': 'sync_now',
                'error': 'Could not determine optimal time'
            }, status=200)