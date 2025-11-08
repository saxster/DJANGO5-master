"""
Cache Invalidation Signals

Automatically invalidate caches when models change to prevent stale data.

Created: November 2025 (ULTRATHINK Code Review - Performance Optimization)

Signals:
- Guard GPS cache invalidation (when People record updates)
- Attendance list cache invalidation (when PeopleEventlog changes)
- Session cache invalidation (various triggers)
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

logger = logging.getLogger('cache.invalidation')


@receiver([post_save, post_delete], sender='peoples.People')
def invalidate_guard_cache(sender, instance, **kwargs):
    """
    Invalidate guard cache when People record changes.

    Triggers: Guard profile updated, shift changed, etc.
    Cache keys: guard_people_{guard_id}
    """
    cache_key = f"guard_people_{instance.id}"
    deleted = cache.delete(cache_key)

    if deleted:
        logger.debug(f"Invalidated guard cache for People ID {instance.id}")


@receiver([post_save, post_delete], sender='attendance.PeopleEventlog')
def invalidate_attendance_cache(sender, instance, **kwargs):
    """
    Invalidate attendance list caches when attendance records change.

    Cache keys affected:
    - attendance_list_{user_id}_{params_hash}
    - geofence_analytics_{client_id}_{date_range}
    """
    # Invalidate user-specific attendance list caches
    try:
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")

        # Pattern: attendance_list_*_{user_id}_*
        pattern = f"attendance_list_*"
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_conn.scan(cursor, match=pattern, count=100)
            if keys:
                redis_conn.delete(*keys)
                deleted_count += len(keys)
            if cursor == 0:
                break

        if deleted_count > 0:
            logger.debug(f"Invalidated {deleted_count} attendance cache keys")

    except (ConnectionError, TimeoutError, OSError) as e:
        logger.warning(f"Redis connection failed during cache invalidation: {e}", exc_info=True)

    # Invalidate geofence analytics cache for affected date
    if instance.datefor:
        analytics_pattern = f"geofence_analytics_*_{instance.datefor}_*"
        try:
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match=analytics_pattern, count=100)
                if keys:
                    redis_conn.delete(*keys)
                if cursor == 0:
                    break
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"Redis connection failed during analytics cache invalidation: {e}", exc_info=True)


# Auto-register signals
import apps.peoples.models
import apps.attendance.models
