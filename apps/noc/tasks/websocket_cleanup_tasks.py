"""
Celery tasks for WebSocket connection cleanup.

Tasks:
- cleanup_stale_websocket_connections: Remove connections idle >24 hours

Following CLAUDE.md:
- Celery Configuration Guide: IdempotentTask pattern
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from apps.core.tasks.base import IdempotentTask
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('noc.websocket')


@shared_task(base=IdempotentTask, bind=True)
class CleanupStaleWebSocketConnectionsTask(IdempotentTask):
    """
    Periodic cleanup of stale WebSocket connections.

    Problem: If disconnect() signal never fires (client crash, network loss),
    connection records persist indefinitely, causing:
    - Inaccurate NOC dashboard metrics (inflated connection counts)
    - Memory leaks in connection tracking dictionaries
    - Misleading SLA reports (shows connections that don't exist)

    Solution: Remove connections idle >24 hours

    Schedule: Every 15 minutes (see celery_config.py beat schedule)
    """

    name = 'noc.websocket.cleanup_stale_connections'
    idempotency_ttl = 900  # 15 minutes (matches schedule frequency)

    def run(self):
        """Execute stale WebSocket connection cleanup."""
        try:
            from apps.noc.models.websocket_connection import WebSocketConnection
        except ImportError:
            logger.warning("WebSocketConnection model not available")
            return {'success': False, 'reason': 'model_not_found'}

        try:
            # Define "stale" as idle >24 hours
            stale_threshold_hours = 24
            cutoff_time = timezone.now() - timedelta(hours=stale_threshold_hours)

            # Find stale connections
            stale_connections = WebSocketConnection.objects.filter(
                connected_at__lt=cutoff_time
            )

            # Get details before deleting (for logging)
            stale_count = stale_connections.count()

            if stale_count > 0:
                # Group by consumer type for analytics
                from django.db.models import Count
                stale_by_type = list(
                    stale_connections.values('consumer_type')
                    .annotate(count=Count('id'))
                    .order_by('-count')
                )

                # Delete stale connections
                stale_connections.delete()

                logger.info(
                    "websocket_stale_cleanup_complete",
                    extra={
                        'deleted_count': stale_count,
                        'stale_threshold_hours': stale_threshold_hours,
                        'cutoff_time': cutoff_time.isoformat(),
                        'stale_by_type': stale_by_type
                    }
                )

                return {
                    'success': True,
                    'deleted_count': stale_count,
                    'stale_threshold_hours': stale_threshold_hours,
                    'stale_by_type': stale_by_type
                }
            else:
                logger.debug("No stale WebSocket connections found")
                return {
                    'success': True,
                    'deleted_count': 0,
                    'message': 'No stale connections'
                }

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to cleanup stale WebSocket connections: {e}",
                exc_info=True
            )
            # Re-raise for Celery retry mechanism
            raise


# Convenience function for manual cleanup
cleanup_stale_websocket_connections = CleanupStaleWebSocketConnectionsTask()
