"""
Sync Cache Service - Performance optimization for mobile sync operations

Caches frequently accessed data to reduce database load:
- Tenant conflict policies
- User sync permissions
- Device health status

Follows .claude/rules.md:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
- Rule #12: Database query optimization with select_related()
"""

import logging
from django.core.cache import cache
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from typing import Optional, Dict, Any

from apps.core.models.sync_conflict_policy import TenantConflictPolicy

logger = logging.getLogger(__name__)


class SyncCacheService:
    """
    Service for caching sync-related data with smart invalidation.

    Cache Keys:
    - sync_policy:{tenant_id}:{domain} - Conflict policies
    - sync_device_health:{device_id} - Device health scores
    - sync_user_perms:{user_id} - User sync permissions
    """

    CACHE_TTL = {
        'conflict_policy': 3600,
        'device_health': 300,
        'user_permissions': 1800,
    }

    @classmethod
    def get_conflict_policy(cls, tenant_id: int, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant conflict policy from cache or database.

        Args:
            tenant_id: Tenant ID
            domain: Data domain (journal, attendance, task, etc.)

        Returns:
            Policy dict or None if not found
        """
        cache_key = f"sync_policy:{tenant_id}:{domain}"

        cached_policy = cache.get(cache_key)
        if cached_policy is not None:
            logger.debug(f"Cache hit for policy: {cache_key}")
            return cached_policy

        try:
            policy = TenantConflictPolicy.objects.select_related('tenant').get(
                tenant_id=tenant_id,
                domain=domain
            )

            policy_data = {
                'resolution_policy': policy.resolution_policy,
                'auto_resolve': policy.auto_resolve,
                'notify_on_conflict': policy.notify_on_conflict,
                'tenant_name': policy.tenant.tenantname,
            }

            cache.set(cache_key, policy_data, cls.CACHE_TTL['conflict_policy'])
            logger.debug(f"Cached policy: {cache_key}")

            return policy_data

        except ObjectDoesNotExist:
            logger.warning(f"No policy found: tenant={tenant_id}, domain={domain}")
            return None
        except DatabaseError as e:
            logger.error(f"Database error fetching policy: {e}", exc_info=True)
            return None

    @classmethod
    def invalidate_conflict_policy(cls, tenant_id: int, domain: str) -> bool:
        """
        Invalidate cached conflict policy.

        Args:
            tenant_id: Tenant ID
            domain: Data domain

        Returns:
            True if cache was invalidated
        """
        cache_key = f"sync_policy:{tenant_id}:{domain}"
        try:
            cache.delete(cache_key)
            logger.info(f"Invalidated policy cache: {cache_key}")
            return True
        except (DatabaseError, IOError) as e:
            logger.error(f"Failed to invalidate cache: {e}", exc_info=True)
            return False

    @classmethod
    def get_all_tenant_policies(cls, tenant_id: int) -> Dict[str, Dict[str, Any]]:
        """
        Get all conflict policies for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dict mapping domains to policies
        """
        cache_key = f"sync_policies_all:{tenant_id}"

        cached_policies = cache.get(cache_key)
        if cached_policies is not None:
            return cached_policies

        try:
            policies = TenantConflictPolicy.objects.filter(
                tenant_id=tenant_id
            ).select_related('tenant')

            policies_dict = {
                policy.domain: {
                    'resolution_policy': policy.resolution_policy,
                    'auto_resolve': policy.auto_resolve,
                    'notify_on_conflict': policy.notify_on_conflict,
                }
                for policy in policies
            }

            cache.set(cache_key, policies_dict, cls.CACHE_TTL['conflict_policy'])
            logger.debug(f"Cached all policies for tenant {tenant_id}")

            return policies_dict

        except DatabaseError as e:
            logger.error(f"Database error fetching all policies: {e}", exc_info=True)
            return {}

    @classmethod
    def cache_device_health(cls, device_id: str, health_data: Dict[str, Any]) -> bool:
        """
        Cache device health metrics.

        Args:
            device_id: Device identifier
            health_data: Health metrics dict

        Returns:
            True if successfully cached
        """
        cache_key = f"sync_device_health:{device_id}"
        try:
            cache.set(cache_key, health_data, cls.CACHE_TTL['device_health'])
            return True
        except (DatabaseError, IOError) as e:
            logger.error(f"Failed to cache device health: {e}", exc_info=True)
            return False

    @classmethod
    def get_device_health(cls, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached device health metrics.

        Args:
            device_id: Device identifier

        Returns:
            Health data dict or None
        """
        cache_key = f"sync_device_health:{device_id}"
        return cache.get(cache_key)

    @classmethod
    def warm_cache_for_tenant(cls, tenant_id: int) -> int:
        """
        Pre-warm cache with all policies for a tenant.

        Useful during deployment or cache invalidation.

        Args:
            tenant_id: Tenant ID

        Returns:
            Number of policies cached
        """
        try:
            policies = cls.get_all_tenant_policies(tenant_id)

            for domain, policy in policies.items():
                cache_key = f"sync_policy:{tenant_id}:{domain}"
                cache.set(cache_key, policy, cls.CACHE_TTL['conflict_policy'])

            logger.info(f"Warmed cache for tenant {tenant_id}: {len(policies)} policies")
            return len(policies)

        except (DatabaseError, IOError) as e:
            logger.error(f"Failed to warm cache: {e}", exc_info=True)
            return 0


sync_cache_service = SyncCacheService()