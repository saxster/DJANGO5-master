"""
Distributed cache invalidation using Redis pub/sub.

Coordinates cache invalidation across multiple application servers.
Complies with .claude/rules.md - file < 200 lines, specific exceptions.
"""

import json
import logging
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

__all__ = [
    'DistributedCacheInvalidator',
    'publish_invalidation_event',
    'subscribe_to_invalidation_events',
]


class DistributedCacheInvalidator:
    """
    Coordinates cache invalidation across distributed servers.

    Uses Redis pub/sub to broadcast invalidation events to all app servers.
    """

    CHANNEL_NAME = 'cache:invalidation:events'
    SERVER_ID_KEY = 'cache:server:id'

    def __init__(self):
        self.redis_client = self._get_redis_client()
        self.server_id = self._get_or_create_server_id()
        self.pubsub = None

    def _get_redis_client(self):
        """Get Redis client for pub/sub"""
        try:
            # Check if cache backend has _cache attribute (django-redis specific)
            if not hasattr(cache, '_cache'):
                logger.debug("Cache backend does not support direct Redis client access")
                return None

            # Try to get the master client
            if hasattr(cache._cache, 'get_master_client'):
                from django_redis import get_redis_connection
                return get_redis_connection("default")
            else:
                logger.debug("Cache backend does not have get_master_client method")
                return None
        except (AttributeError, ConnectionError, TypeError) as e:
            logger.error(f"Could not get Redis client: {e}")
            return None

    def _get_or_create_server_id(self) -> str:
        """Generate unique server ID for this instance"""
        import socket
        import os

        hostname = socket.gethostname()
        pid = os.getpid()
        return f"{hostname}:{pid}"

    def publish_invalidation(self, pattern: str, reason: str = 'manual') -> bool:
        """
        Publish cache invalidation event to all servers.

        Args:
            pattern: Cache pattern to invalidate
            reason: Reason for invalidation

        Returns:
            True if published successfully
        """
        try:
            if not self.redis_client:
                logger.warning("Redis client not available for distributed invalidation")
                return False

            event = {
                'pattern': pattern,
                'reason': reason,
                'server_id': self.server_id,
                'timestamp': timezone.now().isoformat()
            }

            message = json.dumps(event)

            self.redis_client.publish(self.CHANNEL_NAME, message)

            logger.info(
                f"Published cache invalidation event: {pattern}",
                extra={'event': event}
            )

            return True

        except (ConnectionError, AttributeError) as e:
            logger.error(f"Error publishing invalidation event: {e}")
            return False

    def subscribe_to_invalidation_events(self, callback):
        """
        Subscribe to cache invalidation events from other servers.

        Args:
            callback: Function to call when event received
        """
        try:
            if not self.redis_client:
                logger.warning("Redis client not available for subscription")
                return

            self.pubsub = self.redis_client.pubsub()
            self.pubsub.subscribe(self.CHANNEL_NAME)

            logger.info(
                f"Subscribed to cache invalidation events (server: {self.server_id})"
            )

            for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        event = json.loads(message['data'])

                        if event.get('server_id') != self.server_id:
                            callback(event)

                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Invalid invalidation event: {e}")

        except (ConnectionError, AttributeError) as e:
            logger.error(f"Error subscribing to invalidation events: {e}")

    def handle_invalidation_event(self, event: Dict[str, Any]):
        """
        Handle received invalidation event from another server.

        Args:
            event: Invalidation event data
        """
        try:
            pattern = event.get('pattern')
            reason = event.get('reason')
            source_server = event.get('server_id')

            if not pattern:
                logger.warning("Received invalidation event without pattern")
                return

            from apps.core.caching.utils import clear_cache_pattern

            result = clear_cache_pattern(pattern)

            if result['success']:
                logger.info(
                    f"Processed distributed cache invalidation from {source_server}: "
                    f"{result['keys_cleared']} keys cleared for pattern {pattern}",
                    extra={
                        'pattern': pattern,
                        'reason': reason,
                        'source_server': source_server,
                        'keys_cleared': result['keys_cleared']
                    }
                )

        except ImportError as e:
            logger.error(f"Error handling invalidation event: {e}")


distributed_invalidator = DistributedCacheInvalidator()


def publish_invalidation_event(pattern: str, reason: str = 'model_change') -> bool:
    """
    Publish cache invalidation event to all servers.

    Args:
        pattern: Cache pattern to invalidate
        reason: Reason for invalidation

    Returns:
        True if published successfully
    """
    return distributed_invalidator.publish_invalidation(pattern, reason)


def subscribe_to_invalidation_events():
    """
    Start listening for cache invalidation events.

    Should be called in a background worker process.
    """
    distributed_invalidator.subscribe_to_invalidation_events(
        distributed_invalidator.handle_invalidation_event
    )