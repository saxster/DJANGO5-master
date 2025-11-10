"""
NOC Cache Service for Dashboard Performance Optimization.

Implements intelligent caching with TTL management, cache warming, and
targeted invalidation strategies.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #12 (query optimization).
"""

import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db.models import QuerySet
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger('noc.cache')

__all__ = ['NOCCacheService']


class NOCCacheService:
    """Service for NOC dashboard data caching."""

    CACHE_TTL = {
        'dashboard': 300,
        'metrics': 180,
        'alerts': 60,
        'aggregation': 300,
    }

    CACHE_KEY_PREFIX = 'noc'

    @staticmethod
    def get_dashboard_data(user, filters=None):
        """
        Get cached dashboard data or fetch and cache.

        Args:
            user: People instance
            filters: Optional dict of filters

        Returns:
            dict: Dashboard data
        """
        cache_key = NOCCacheService._build_cache_key(
            'dashboard',
            user.id,
            filters or {}
        )

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached_data

        logger.debug(f"Cache miss: {cache_key}")
        data = NOCCacheService._fetch_dashboard_data(user, filters)

        cache.set(
            cache_key,
            data,
            NOCCacheService.CACHE_TTL['dashboard']
        )

        return data

    @staticmethod
    def warm_dashboard_cache(user):
        """
        Pre-warm dashboard cache for executive users.

        Args:
            user: People instance with noc:view_all_clients capability
        """
        if not user.has_capability('noc:view_all_clients'):
            return

        try:
            filters_sets = [
                {},
                {'severity': 'CRITICAL'},
                {'severity': 'HIGH'},
                {'time_range': '24h'},
            ]

            for filters in filters_sets:
                NOCCacheService.get_dashboard_data(user, filters)

            logger.info(
                f"Cache warming completed",
                extra={'user_id': user.id, 'filter_sets': len(filters_sets)}
            )

        except (ValueError, KeyError) as e:
            logger.error(
                f"Cache warming failed",
                extra={'user_id': user.id, 'error': str(e)}
            )

    @staticmethod
    def invalidate_client_cache(client_id):
        """
        Invalidate all caches related to a specific client.

        Args:
            client_id: Client BU ID
        """
        scope = NOCCacheService._tenant_scope()
        pattern = f"{NOCCacheService.CACHE_KEY_PREFIX}:tenant_{scope}:*:client_{client_id}:*"
        cache.delete_pattern(pattern)
        logger.debug(f"Invalidated cache for client {client_id}")

    @staticmethod
    def invalidate_tenant_cache(tenant_id):
        """
        Invalidate all caches for a tenant.

        Args:
            tenant_id: Tenant ID
        """
        scope = NOCCacheService._tenant_scope()
        pattern = f"{NOCCacheService.CACHE_KEY_PREFIX}:tenant_{scope}:*:tenant_{tenant_id}:*"
        cache.delete_pattern(pattern)
        logger.debug(f"Invalidated cache for tenant {tenant_id}")

    @staticmethod
    def get_metrics_cached(client_id, window_minutes=5):
        """
        Get cached metrics snapshot for client.

        Args:
            client_id: Client BU ID
            window_minutes: Time window in minutes

        Returns:
            dict: Metrics data or None
        """
        scope = NOCCacheService._tenant_scope()
        cache_key = f"{NOCCacheService.CACHE_KEY_PREFIX}:tenant_{scope}:metrics:client_{client_id}"
        return cache.get(cache_key)

    @staticmethod
    def set_metrics_cache(client_id, metrics_data):
        """
        Cache metrics snapshot for client.

        Args:
            client_id: Client BU ID
            metrics_data: Metrics dictionary
        """
        scope = NOCCacheService._tenant_scope()
        cache_key = f"{NOCCacheService.CACHE_KEY_PREFIX}:tenant_{scope}:metrics:client_{client_id}"
        cache.set(cache_key, metrics_data, NOCCacheService.CACHE_TTL['metrics'])

    @staticmethod
    def _build_cache_key(data_type, user_id, filters):
        """
        Build cache key with filters hash.

        Args:
            data_type: Type of data (dashboard, metrics, etc.)
            user_id: User ID
            filters: Filters dictionary

        Returns:
            str: Cache key
        """
        import hashlib
        import json

        filters_str = json.dumps(filters, sort_keys=True)
        filters_hash = hashlib.md5(filters_str.encode()).hexdigest()[:8]

        tenant_scope = NOCCacheService._tenant_scope()
        return f"{NOCCacheService.CACHE_KEY_PREFIX}:tenant_{tenant_scope}:{data_type}:user_{user_id}:{filters_hash}"

    @staticmethod
    def _fetch_dashboard_data(user, filters):
        """
        Fetch dashboard data from database.

        Args:
            user: People instance
            filters: Filters dictionary

        Returns:
            dict: Dashboard data
        """
        from apps.noc.services import NOCAggregationService, NOCRBACService
        from apps.noc.models import NOCAlertEvent

        clients = NOCRBACService.get_visible_clients(user)

        metrics = NOCAggregationService.get_aggregated_metrics(
            clients=clients,
            filters=filters
        )

        alerts = NOCAlertEvent.objects.filter(
            client__in=clients,
            status__in=['NEW', 'ACKNOWLEDGED'],
            tenant=user.tenant
        ).select_related('client', 'bu', 'tenant')[:50]

        return {
            'metrics': metrics,
            'alerts': [
                {
                    'id': alert.id,
                    'type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'client_id': alert.client_id,
                    'created_at': alert.cdtz.isoformat(),
                }
                for alert in alerts
            ],
            'cached_at': timezone.now().isoformat(),
        }
    @staticmethod
    def _tenant_scope() -> str:
        try:
            return get_current_db_name() or 'default'
        except Exception:
            return 'default'
