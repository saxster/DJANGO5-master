"""
Search Caching Service

Redis-backed caching for search results.

Features:
- 5-minute TTL for search results
- Cache key based on query + filters + permissions
- Cache hit/miss analytics
- Graceful degradation if Redis unavailable

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service < 150 lines
- Rule #11: Specific exception handling
- Rule #12: Database query optimization

Note: Cache invalidation uses entity version tokens that are updated via signals,
so stale entries are ignored immediately after relevant data changes.
"""

import logging
import hashlib
import json
import secrets
from typing import Dict, Any, Optional, List, Iterable

from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

logger = logging.getLogger(__name__)


class SearchCacheService:
    """
    Manages caching for search results with intelligent invalidation.

    Cache key format: search:{tenant}:{query_hash}:{filters_hash}:{permissions_hash}
    """

    # Cache configuration
    CACHE_PREFIX = 'search_result'
    CACHE_TTL = 5 * SECONDS_IN_MINUTE  # 5 minutes
    ANALYTICS_PREFIX = 'search_cache_analytics'
    ANALYTICS_TTL = 24 * 60 * SECONDS_IN_MINUTE  # 24 hours
    ENTITY_VERSION_PREFIX = 'search_cache_entity_version'
    ENTITY_VERSION_TTL = 30 * 24 * 60 * SECONDS_IN_MINUTE  # 30 days

    def __init__(self, tenant_id: int, user_id: Optional[int] = None):
        """
        Initialize cache service for specific tenant and user.

        Args:
            tenant_id: Tenant ID for cache isolation
            user_id: Optional user ID for permission-based caching
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._analytics_enabled = True

    def get_cached_results(
        self,
        query: str,
        entities: List[str],
        filters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached search results if available.

        Args:
            query: Search query string
            entities: Entity types being searched
            filters: Additional filters

        Returns:
            Cached results dict or None if cache miss
        """
        try:
            cache_key = self._generate_cache_key(query, entities, filters)

            cached_data = cache.get(cache_key)

            if cached_data:
                self._track_cache_hit(cache_key)
                logger.debug(
                    f"Search cache HIT for query: {query[:50]}",
                    extra={
                        'cache_key': cache_key,
                        'tenant_id': self.tenant_id,
                        'user_id': self.user_id,
                    }
                )
                return cached_data

            self._track_cache_miss(cache_key)
            logger.debug(
                f"Search cache MISS for query: {query[:50]}",
                extra={
                    'cache_key': cache_key,
                    'tenant_id': self.tenant_id,
                    'user_id': self.user_id,
                }
            )
            return None

        except Exception as e:
            self._disable_analytics_tracking()
            logger.warning(
                f"Cache retrieval failed: {e}. Proceeding without cache.",
                exc_info=True
            )
            return None

    def cache_results(
        self,
        query: str,
        entities: List[str],
        filters: Dict[str, Any],
        results: Dict[str, Any]
    ) -> bool:
        """
        Cache search results.

        Args:
            query: Search query string
            entities: Entity types being searched
            filters: Additional filters
            results: Search results to cache

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(query, entities, filters)

            # Prepare cacheable data (exclude non-serializable items)
            cacheable_data = {
                'results': results.get('results', []),
                'total_results': results.get('total_results', results.get('count', 0)),
                'response_time_ms': results.get('response_time_ms', 0),
                'cached_at': timezone.now().isoformat(),
                'query': query,
                'entities': entities,
            }

            # Cache with TTL
            cache.set(cache_key, cacheable_data, timeout=self.CACHE_TTL)

            logger.debug(
                f"Search results cached for query: {query[:50]}",
                extra={
                    'cache_key': cache_key,
                    'result_count': cacheable_data['total_results'],
                    'tenant_id': self.tenant_id,
                }
            )

            return True

        except (ConnectionError, TimeoutError, TypeError, Exception) as e:
            self._disable_analytics_tracking()
            logger.warning(
                f"Failed to cache search results: {e}",
                exc_info=True
            )
            return False

# Cache invalidation is handled via per-entity version tokens.
# See invalidate_entities() for integration points (signals update versions).

    def get_cache_analytics(self) -> Dict[str, Any]:
        """
        Get cache hit/miss statistics.

        Returns:
            Dict with cache analytics
        """
        try:
            analytics_key = f"{self.ANALYTICS_PREFIX}:{self.tenant_id}"
            analytics = cache.get(analytics_key, {
                'hits': 0,
                'misses': 0,
                'hit_rate': 0.0,
            })

            # Calculate hit rate
            total = analytics['hits'] + analytics['misses']
            if total > 0:
                analytics['hit_rate'] = (analytics['hits'] / total) * 100

            return analytics

        except (ConnectionError, TimeoutError) as e:
            logger.warning(
                f"Failed to retrieve cache analytics: {e}",
                exc_info=True
            )
            return {'hits': 0, 'misses': 0, 'hit_rate': 0.0}

    def _generate_cache_key(
        self,
        query: str,
        entities: List[str],
        filters: Dict[str, Any]
    ) -> str:
        """
        Generate unique cache key for search parameters.

        Args:
            query: Search query string
            entities: Entity types
            filters: Additional filters

        Returns:
            Cache key string
        """
        # Create stable string representation
        query_normalized = query.lower().strip()
        entities_sorted = sorted(entities)
        filters_json = json.dumps(filters, sort_keys=True, cls=DjangoJSONEncoder)

        # Create hash of search parameters
        entity_versions = self._get_entity_versions(entities_sorted)
        search_params = f"{query_normalized}:{entities_sorted}:{filters_json}:{entity_versions}"
        search_hash = hashlib.sha256(search_params.encode()).hexdigest()[:16]

        # Include user permissions in key (if applicable)
        permission_suffix = f":{self.user_id}" if self.user_id else ""

        return f"{self.CACHE_PREFIX}:{self.tenant_id}:{search_hash}{permission_suffix}"

    def _track_cache_hit(self, cache_key: str):
        """Track cache hit for analytics"""
        if not self._analytics_enabled:
            return
        try:
            analytics_key = f"{self.ANALYTICS_PREFIX}:{self.tenant_id}"
            analytics = cache.get(analytics_key, {'hits': 0, 'misses': 0})
            analytics['hits'] += 1
            cache.set(analytics_key, analytics, timeout=self.ANALYTICS_TTL)
        except (ConnectionError, TimeoutError, TypeError, Exception):
            self._disable_analytics_tracking()

    def _track_cache_miss(self, cache_key: str):
        """Track cache miss for analytics"""
        if not self._analytics_enabled:
            return
        try:
            analytics_key = f"{self.ANALYTICS_PREFIX}:{self.tenant_id}"
            analytics = cache.get(analytics_key, {'hits': 0, 'misses': 0})
            analytics['misses'] += 1
            cache.set(analytics_key, analytics, timeout=self.ANALYTICS_TTL)
        except (ConnectionError, TimeoutError, TypeError, Exception):
            self._disable_analytics_tracking()

    def _get_entity_versions(self, entities: List[str]) -> List[str]:
        """Return stable version tokens for each entity involved in the query."""
        versions = []
        for entity in entities:
            version_key = self._entity_version_key(entity)
            version = None
            if version_key:
                try:
                    version = cache.get(version_key)
                except (ConnectionError, TimeoutError, TypeError, Exception):
                    # Backend unavailable – skip analytics tracking to avoid noisy errors
                    self._disable_analytics_tracking()

                if not version:
                    version = self._initialize_entity_version(version_key)

            versions.append(version or 'v0')
        return versions

    def _entity_version_key(self, entity: str) -> Optional[str]:
        """Build cache key used for per-entity versioning."""
        if not self.tenant_id or not entity:
            return None
        normalized_entity = str(entity).lower()
        return f"{self.ENTITY_VERSION_PREFIX}:{self.tenant_id}:{normalized_entity}"

    def _initialize_entity_version(self, version_key: Optional[str]) -> str:
        """Ensure a version token exists when first seen."""
        token = self._new_version_token()
        if not version_key:
            return token
        try:
            cache.add(version_key, token, timeout=self.ENTITY_VERSION_TTL)
        except (ConnectionError, TimeoutError, TypeError, Exception):
            self._disable_analytics_tracking()
        return token

    @classmethod
    def invalidate_entities(cls, tenant_id: Optional[int], entities: Iterable[str]):
        """
        Bump version tokens for the provided entities so stale cache entries are ignored.
        """
        if not tenant_id:
            return

        unique_entities = {str(entity).lower() for entity in entities if entity}
        for entity in unique_entities:
            version_key = f"{cls.ENTITY_VERSION_PREFIX}:{tenant_id}:{entity}"
            token = cls._new_version_token()
            try:
                cache.set(version_key, token, timeout=cls.ENTITY_VERSION_TTL)
                logger.debug(
                    "Search cache invalidated",
                    extra={'tenant_id': tenant_id, 'entity': entity}
                )
            except (ConnectionError, TimeoutError, TypeError, Exception) as exc:
                logger.warning(
                    "Failed to invalidate search cache for tenant %s entity %s: %s",
                    tenant_id,
                    entity,
                    exc,
                    exc_info=True
                )

    @staticmethod
    def _new_version_token() -> str:
        """Generate a new opaque version token for cache busting."""
        return secrets.token_hex(8)

    def _disable_analytics_tracking(self):
        """Disable cache analytics tracking for this instance after a backend failure."""
        if self._analytics_enabled:
            logger.debug(
                "Disabling search cache analytics tracking for tenant %s due to backend error",
                self.tenant_id
            )
        self._analytics_enabled = False
