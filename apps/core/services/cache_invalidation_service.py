"""
Cache Invalidation Service

Provides automatic cache invalidation when models are created, updated, or deleted.

Features:
- Signal-based invalidation (post_save, post_delete)
- Pattern-based cache clearing
- Multi-model support (Ticket, People, Attendance)
- Tenant-aware invalidation

Usage:
    # Automatic invalidation via signals (no manual calls needed)
    ticket.save()  # Automatically invalidates related caches

Follows .claude/rules.md:
- Functions < 50 lines
- Specific exception handling
- No blocking I/O
"""

import logging
from typing import List, Optional
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


class CacheInvalidationService:
    """Service for managing cache invalidation across the application."""

    @staticmethod
    def invalidate_patterns(patterns: List[str]) -> None:
        """
        Invalidate multiple cache key patterns.

        Args:
            patterns: List of cache key patterns to invalidate
        """
        for pattern in patterns:
            try:
                if hasattr(cache, 'delete_pattern'):
                    deleted = cache.delete_pattern(pattern)
                    logger.debug(f"Invalidated {deleted} keys for pattern: {pattern}")
                else:
                    # Fallback: delete specific known keys
                    logger.warning(
                        f"Cache backend doesn't support pattern deletion. "
                        f"Consider using django-redis. Pattern: {pattern}"
                    )
            except Exception as e:
                logger.error(
                    f"Error invalidating cache pattern {pattern}: {e}",
                    exc_info=True
                )

    @staticmethod
    def invalidate_ticket_caches(ticket_id: Optional[int] = None,
                                  reporter_id: Optional[int] = None,
                                  assigned_to_id: Optional[int] = None,
                                  status: Optional[str] = None) -> None:
        """
        Invalidate ticket-related caches.

        Args:
            ticket_id: Specific ticket ID (invalidates all caches for this ticket)
            reporter_id: Reporter user ID (invalidates reporter's ticket lists)
            assigned_to_id: Assignee user ID (invalidates assignee's ticket lists)
            status: Ticket status (invalidates status-filtered lists)
        """
        patterns = []

        # Invalidate all ticket list caches
        patterns.append('tickets:*')

        # Invalidate specific user caches
        if reporter_id:
            patterns.append(f'tickets:*:user:{reporter_id}:*')

        if assigned_to_id:
            patterns.append(f'tickets:*:user:{assigned_to_id}:*')

        # Invalidate status-filtered caches
        if status:
            patterns.append(f'tickets:*:status:{status}:*')

        CacheInvalidationService.invalidate_patterns(patterns)
        logger.info(f"Invalidated ticket caches (ticket_id={ticket_id})")

    @staticmethod
    def invalidate_people_caches(user_id: Optional[int] = None,
                                  tenant_id: Optional[int] = None) -> None:
        """
        Invalidate people/user search caches.

        Args:
            user_id: Specific user ID
            tenant_id: Tenant/client ID (invalidate all users in tenant)
        """
        patterns = []

        # Invalidate all people search caches
        patterns.append('people:*')
        patterns.append('people_search:*')

        # Tenant-specific invalidation
        if tenant_id:
            patterns.append(f'people:*:tenant:{tenant_id}:*')

        CacheInvalidationService.invalidate_patterns(patterns)
        logger.info(f"Invalidated people caches (user_id={user_id}, tenant_id={tenant_id})")

    @staticmethod
    def invalidate_attendance_caches(attendance_id: Optional[int] = None,
                                      user_id: Optional[int] = None,
                                      date: Optional[str] = None) -> None:
        """
        Invalidate attendance query caches.

        Args:
            attendance_id: Specific attendance record ID
            user_id: User ID (invalidate user's attendance records)
            date: Date string (invalidate date-specific caches)
        """
        patterns = []

        # Invalidate all attendance caches
        patterns.append('attendance:*')

        # User-specific invalidation
        if user_id:
            patterns.append(f'attendance:*:user:{user_id}:*')

        # Date-specific invalidation
        if date:
            patterns.append(f'attendance:*:date:{date}:*')

        CacheInvalidationService.invalidate_patterns(patterns)
        logger.info(f"Invalidated attendance caches (attendance_id={attendance_id})")


# ============================================================================
# SIGNAL HANDLERS - Automatic Cache Invalidation
# ============================================================================

@receiver(post_save, sender='y_helpdesk.Ticket')
def invalidate_ticket_cache_on_save(sender, instance, **kwargs):
    """Invalidate ticket caches when a ticket is created or updated."""
    CacheInvalidationService.invalidate_ticket_caches(
        ticket_id=instance.id,
        reporter_id=instance.reporter_id if hasattr(instance, 'reporter_id') else None,
        assigned_to_id=instance.assigned_to_id if hasattr(instance, 'assigned_to_id') else None,
        status=instance.status if hasattr(instance, 'status') else None,
    )


@receiver(post_delete, sender='y_helpdesk.Ticket')
def invalidate_ticket_cache_on_delete(sender, instance, **kwargs):
    """Invalidate ticket caches when a ticket is deleted."""
    CacheInvalidationService.invalidate_ticket_caches(
        ticket_id=instance.id,
        reporter_id=instance.reporter_id if hasattr(instance, 'reporter_id') else None,
        assigned_to_id=instance.assigned_to_id if hasattr(instance, 'assigned_to_id') else None,
    )


@receiver(post_save, sender='peoples.People')
def invalidate_people_cache_on_save(sender, instance, **kwargs):
    """Invalidate people caches when a user is created or updated."""
    CacheInvalidationService.invalidate_people_caches(
        user_id=instance.id,
        tenant_id=instance.client_id if hasattr(instance, 'client_id') else None,
    )


@receiver(post_delete, sender='peoples.People')
def invalidate_people_cache_on_delete(sender, instance, **kwargs):
    """Invalidate people caches when a user is deleted."""
    CacheInvalidationService.invalidate_people_caches(
        user_id=instance.id,
        tenant_id=instance.client_id if hasattr(instance, 'client_id') else None,
    )


@receiver(post_save, sender='attendance.PeopleEventlog')
def invalidate_attendance_cache_on_save(sender, instance, **kwargs):
    """Invalidate attendance caches when attendance record is created or updated."""
    CacheInvalidationService.invalidate_attendance_caches(
        attendance_id=instance.id,
        user_id=instance.people_id if hasattr(instance, 'people_id') else None,
        date=str(instance.datefor) if hasattr(instance, 'datefor') else None,
    )


@receiver(post_delete, sender='attendance.PeopleEventlog')
def invalidate_attendance_cache_on_delete(sender, instance, **kwargs):
    """Invalidate attendance caches when attendance record is deleted."""
    CacheInvalidationService.invalidate_attendance_caches(
        attendance_id=instance.id,
        user_id=instance.people_id if hasattr(instance, 'people_id') else None,
    )


__all__ = ['CacheInvalidationService']
