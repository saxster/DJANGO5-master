"""
User permissions caching service.

Caches user permissions to avoid repeated database hits on permission checks.
Automatically invalidates cache on permission changes.

Created: 2025-11-07
"""

import logging
from typing import Dict, Optional
from django.core.cache import cache
from django.contrib.auth.models import Permission
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

logger = logging.getLogger(__name__)


class PermissionCacheService:
    """Service for caching user permissions."""
    
    # Cache timeout: 15 minutes
    CACHE_TIMEOUT = 900
    
    @classmethod
    def get_user_permissions(cls, user) -> Dict[str, bool]:
        """
        Get cached user permissions.
        
        Args:
            user: User instance
            
        Returns:
            Dictionary of permission checks
        """
        cache_key = cls._get_cache_key(user.id)
        permissions = cache.get(cache_key)
        
        if permissions is None:
            # Cache miss - compute permissions
            permissions = cls._compute_permissions(user)
            cache.set(cache_key, permissions, cls.CACHE_TIMEOUT)
            logger.debug(f"Cached permissions for user {user.id}")
        
        return permissions
    
    @classmethod
    def _compute_permissions(cls, user) -> Dict[str, bool]:
        """
        Compute all permissions for a user.
        
        Args:
            user: User instance
            
        Returns:
            Dictionary of permission checks
        """
        return {
            # Activity permissions
            'can_create_tasks': user.has_perm('activity.add_task'),
            'can_edit_tasks': user.has_perm('activity.change_task'),
            'can_delete_tasks': user.has_perm('activity.delete_task'),
            'can_view_tasks': user.has_perm('activity.view_task'),
            
            # Work order permissions
            'can_create_work_orders': user.has_perm('work_order_management.add_workorder'),
            'can_edit_work_orders': user.has_perm('work_order_management.change_workorder'),
            'can_approve_work_orders': user.has_perm('work_order_management.approve_workorder'),
            
            # Report permissions
            'can_view_reports': user.has_perm('reports.view_report'),
            'can_create_reports': user.has_perm('reports.add_report'),
            'can_export_reports': user.has_perm('reports.export_report'),
            
            # Helpdesk permissions
            'can_view_tickets': user.has_perm('y_helpdesk.view_ticket'),
            'can_create_tickets': user.has_perm('y_helpdesk.add_ticket'),
            'can_assign_tickets': user.has_perm('y_helpdesk.assign_ticket'),
            
            # People permissions
            'can_manage_users': user.has_perm('peoples.change_people'),
            'can_view_attendance': user.has_perm('attendance.view_attendance'),
            
            # Site permissions
            'can_manage_sites': user.has_perm('client_onboarding.change_site'),
            
            # Admin permissions
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }
    
    @classmethod
    def invalidate_user_cache(cls, user_id: int) -> None:
        """
        Invalidate cached permissions for a user.
        
        Args:
            user_id: User ID
        """
        cache_key = cls._get_cache_key(user_id)
        deleted = cache.delete(cache_key)
        if deleted:
            logger.info(f"Invalidated permission cache for user {user_id}")
    
    @classmethod
    def _get_cache_key(cls, user_id: int) -> str:
        """
        Get cache key for user permissions.
        
        Args:
            user_id: User ID
            
        Returns:
            Cache key string
        """
        return f"user_perms_{user_id}"


# Signal handlers for automatic cache invalidation

@receiver(post_save, sender='peoples.People')
def invalidate_user_permissions_on_save(sender, instance, **kwargs):
    """Invalidate permissions cache when user is saved."""
    PermissionCacheService.invalidate_user_cache(instance.id)


@receiver(m2m_changed, sender='peoples.People.groups.through')
def invalidate_user_permissions_on_group_change(sender, instance, **kwargs):
    """Invalidate permissions cache when user groups change."""
    if kwargs.get('action') in ['post_add', 'post_remove', 'post_clear']:
        PermissionCacheService.invalidate_user_cache(instance.id)


@receiver(m2m_changed, sender='peoples.People.user_permissions.through')
def invalidate_user_permissions_on_perm_change(sender, instance, **kwargs):
    """Invalidate permissions cache when user permissions change."""
    if kwargs.get('action') in ['post_add', 'post_remove', 'post_clear']:
        PermissionCacheService.invalidate_user_cache(instance.id)


__all__ = ['PermissionCacheService']
