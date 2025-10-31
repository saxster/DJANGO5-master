"""
Event Bus for Agent Communications

Redis-based publish-subscribe event bus for real-time agent updates.
Enables WebSocket notifications for dashboard recommendations.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Integration with existing Redis infrastructure

Dashboard Agent Intelligence - Phase 3.1
"""

import logging
import json
from typing import Dict, Any, List, Callable
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RedisEventBus:
    """
    Redis-based event bus for agent recommendations.

    Provides:
    - Publish recommendations to subscribers
    - Subscribe to recommendation events
    - WebSocket integration for real-time dashboard updates
    """

    # Redis channel prefixes
    CHANNEL_PREFIX = 'agent:events'
    RECOMMENDATION_CHANNEL = f'{CHANNEL_PREFIX}:recommendations'
    ACTION_CHANNEL = f'{CHANNEL_PREFIX}:actions'

    def __init__(self):
        """Initialize event bus"""
        try:
            # Get Redis connection from cache backend
            self.redis_client = cache._cache.get_client()
            self.pubsub = None
            logger.info("RedisEventBus initialized successfully")
        except (AttributeError, ConnectionError) as e:
            logger.error(f"Failed to initialize RedisEventBus: {e}", exc_info=True)
            self.redis_client = None
            self.pubsub = None

    def publish_recommendation(self, recommendation: Dict[str, Any]):
        """
        Publish recommendation to subscribers.

        Args:
            recommendation: Recommendation dictionary (from to_dict())

        Returns:
            Number of subscribers that received the message
        """
        if not self.redis_client:
            logger.warning("Redis client not available - skipping publish")
            return 0

        try:
            # Serialize recommendation
            message = json.dumps({
                'type': 'recommendation_created',
                'data': recommendation,
                'timestamp': recommendation.get('created_at'),
            })

            # Publish to channel
            subscribers = self.redis_client.publish(
                self.RECOMMENDATION_CHANNEL,
                message
            )

            logger.debug(
                f"Published recommendation {recommendation.get('id')} to {subscribers} subscribers"
            )

            return subscribers

        except (ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Failed to publish recommendation: {e}", exc_info=True)
            return 0

    def publish_recommendations(self, recommendations: List[Dict[str, Any]]):
        """
        Publish multiple recommendations.

        Args:
            recommendations: List of recommendation dictionaries
        """
        for rec in recommendations:
            self.publish_recommendation(rec)

    def publish_action_executed(self, recommendation_id: int, action_type: str, result: Dict[str, Any]):
        """
        Publish action execution event.

        Args:
            recommendation_id: Recommendation ID
            action_type: Action type executed
            result: Execution result
        """
        if not self.redis_client:
            return

        try:
            message = json.dumps({
                'type': 'action_executed',
                'recommendation_id': recommendation_id,
                'action_type': action_type,
                'result': result,
                'timestamp': timezone.now().isoformat(),
            })

            self.redis_client.publish(self.ACTION_CHANNEL, message)
            logger.debug(f"Published action execution for recommendation {recommendation_id}")

        except (ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Failed to publish action event: {e}", exc_info=True)

    def subscribe_to_recommendations(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to recommendation events.

        Args:
            callback: Function to call when recommendation received
        """
        if not self.redis_client:
            logger.warning("Redis client not available - cannot subscribe")
            return

        try:
            if not self.pubsub:
                self.pubsub = self.redis_client.pubsub()

            self.pubsub.subscribe(self.RECOMMENDATION_CHANNEL)
            logger.info("Subscribed to recommendation channel")

            # Listen for messages
            for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        callback(data)
                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        logger.error(f"Invalid message format: {e}")

        except (ConnectionError, AttributeError) as e:
            logger.error(f"Subscription failed: {e}", exc_info=True)

    def close(self):
        """Close pub/sub connection"""
        if self.pubsub:
            try:
                self.pubsub.close()
                logger.info("Event bus closed")
            except (ConnectionError, AttributeError) as e:
                logger.error(f"Error closing event bus: {e}")
