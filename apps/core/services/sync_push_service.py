"""
Real-time Sync Push Service

Server→client push notifications for data updates, sync triggers, and system notifications.

Features:
- Push to specific user/device
- Broadcast to tenant
- Selective push with filters
- Rate limiting (prevent push storms)
- Offline message queueing (1 hour)

Follows .claude/rules.md:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger('sync.push')


class SyncPushService:
    """Real-time push service for server→client updates."""

    PUSH_RATE_LIMIT = 10
    PUSH_RATE_WINDOW = 60
    OFFLINE_QUEUE_TTL = 3600

    @classmethod
    async def push_to_user(cls, user_id: int, data: Dict[str, Any],
                          priority: str = 'normal') -> bool:
        """
        Push data update to all user's devices.

        Args:
            user_id: Target user ID
            data: Data to push
            priority: normal, high, critical

        Returns:
            True if pushed successfully
        """
        try:
            if not cls._check_rate_limit(f"user_{user_id}"):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return False

            channel_layer = get_channel_layer()

            await channel_layer.group_send(
                f"mobile_user_{user_id}",
                {
                    'type': 'push_update',
                    'data': data,
                    'priority': priority,
                    'timestamp': timezone.now().isoformat()
                }
            )

            logger.info(f"Pushed to user {user_id}: {data.get('domain', 'unknown')}")
            return True

        except (ConnectionError, IOError) as e:
            logger.error(f"Failed to push to user {user_id}: {e}", exc_info=True)
            return False

    @classmethod
    async def push_to_device(cls, device_id: str, data: Dict[str, Any]) -> bool:
        """Push to specific device."""
        try:
            channel_layer = get_channel_layer()

            await channel_layer.send(
                f"mobile_device_{device_id}",
                {
                    'type': 'push_update',
                    'data': data,
                    'timestamp': timezone.now().isoformat()
                }
            )

            return True

        except (ConnectionError, IOError) as e:
            logger.error(f"Failed to push to device {device_id}: {e}", exc_info=True)
            return False

    @classmethod
    async def push_data_update(cls, user_id: int, domain: str,
                              operation: str, entity_data: Dict) -> bool:
        """
        Push data change notification.

        Args:
            user_id: Target user
            domain: journal, task, ticket, etc.
            operation: create, update, delete
            entity_data: Changed data

        Returns:
            True if pushed
        """
        data = {
            'type': 'data_update',
            'domain': domain,
            'operation': operation,
            'data': entity_data,
            'server_timestamp': timezone.now().isoformat()
        }

        return await cls.push_to_user(user_id, data)

    @classmethod
    async def push_sync_trigger(cls, user_id: int, domains: List[str]) -> bool:
        """
        Trigger sync for specific domains.

        Args:
            user_id: Target user
            domains: List of domains to sync

        Returns:
            True if triggered
        """
        data = {
            'type': 'sync_trigger',
            'domains': domains,
            'reason': 'server_update'
        }

        return await cls.push_to_user(user_id, data, priority='high')

    @classmethod
    async def push_conflict_alert(cls, user_id: int, conflict_id: str,
                                  domain: str) -> bool:
        """
        Alert user about conflict requiring resolution.

        Args:
            user_id: Target user
            conflict_id: Conflict UUID
            domain: Data domain

        Returns:
            True if alerted
        """
        data = {
            'type': 'conflict_alert',
            'conflict_id': conflict_id,
            'domain': domain,
            'action_required': True
        }

        return await cls.push_to_user(user_id, data, priority='critical')

    @classmethod
    async def broadcast_to_tenant(cls, tenant_id: int, data: Dict[str, Any]) -> int:
        """
        Broadcast message to all users in tenant.

        Args:
            tenant_id: Tenant ID
            data: Data to broadcast

        Returns:
            Number of users reached
        """
        try:
            from apps.peoples.models import People

            users = People.objects.filter(businessunit_id=tenant_id, enable=True)

            tasks = [cls.push_to_user(user.id, data) for user in users]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if r is True)

            logger.info(f"Broadcast to tenant {tenant_id}: {success_count} users")
            return success_count

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Broadcast failed for tenant {tenant_id}: {e}", exc_info=True)
            return 0

    @classmethod
    def push_to_user_sync(cls, user_id: int, data: Dict[str, Any]) -> bool:
        """Synchronous wrapper for push_to_user."""
        return async_to_sync(cls.push_to_user)(user_id, data)

    @classmethod
    def _check_rate_limit(cls, key: str) -> bool:
        """Check if rate limit allows push."""
        cache_key = f"push_rate_limit:{key}"

        count = cache.get(cache_key, 0)

        if count >= cls.PUSH_RATE_LIMIT:
            return False

        cache.set(cache_key, count + 1, cls.PUSH_RATE_WINDOW)
        return True

    @classmethod
    async def queue_offline_message(cls, user_id: int, device_id: str,
                                    message: Dict[str, Any]) -> bool:
        """
        Queue message for offline device (delivered on reconnect).

        Args:
            user_id: User ID
            device_id: Device ID
            message: Message to queue

        Returns:
            True if queued
        """
        try:
            queue_key = f"offline_queue:{user_id}:{device_id}"

            queued_messages = cache.get(queue_key, [])
            queued_messages.append({
                'message': message,
                'queued_at': timezone.now().isoformat()
            })

            if len(queued_messages) > 50:
                queued_messages = queued_messages[-50:]

            cache.set(queue_key, queued_messages, cls.OFFLINE_QUEUE_TTL)

            logger.debug(f"Queued offline message for {device_id}")
            return True

        except CACHE_EXCEPTIONS as e:
            logger.error(f"Failed to queue offline message: {e}", exc_info=True)
            return False

    @classmethod
    async def get_offline_messages(cls, user_id: int, device_id: str) -> List[Dict]:
        """
        Retrieve queued messages for device.

        Args:
            user_id: User ID
            device_id: Device ID

        Returns:
            List of queued messages
        """
        queue_key = f"offline_queue:{user_id}:{device_id}"

        messages = cache.get(queue_key, [])

        cache.delete(queue_key)

        logger.info(f"Retrieved {len(messages)} offline messages for {device_id}")
        return messages


sync_push_service = SyncPushService()