"""
People Caching Service

Redis-based caching for people list views to improve performance.
Implements cache invalidation strategies.
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional, List

from django.core.cache import cache
from django.conf import settings

from apps.core.services.base_service import BaseService, monitor_service_performance

logger = logging.getLogger(__name__)


class PeopleCachingService(BaseService):
    """Service for caching people data to improve performance."""

    CACHE_PREFIX = "people_list"
    CACHE_TTL = 300

    @monitor_service_performance("get_cached_people_list")
    def get_cached_people_list(
        self,
        cache_key_params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached people list if available.

        Args:
            cache_key_params: Parameters to generate cache key

        Returns:
            Cached data or None
        """
        cache_key = self._generate_cache_key(cache_key_params)

        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                self.logger.debug(f"Cache HIT for key: {cache_key}")
                return cached_data
            else:
                self.logger.debug(f"Cache MISS for key: {cache_key}")
                return None

        except (ValueError, TypeError) as e:
            self.logger.error(f"Cache retrieval error: {str(e)}")
            return None

    @monitor_service_performance("cache_people_list")
    def cache_people_list(
        self,
        cache_key_params: Dict[str, Any],
        data: Dict[str, Any]
    ) -> bool:
        """
        Cache people list data.

        Args:
            cache_key_params: Parameters to generate cache key
            data: Data to cache

        Returns:
            True if cached successfully
        """
        cache_key = self._generate_cache_key(cache_key_params)

        try:
            cache.set(cache_key, data, self.CACHE_TTL)
            self.logger.debug(f"Cached data for key: {cache_key}")
            return True

        except (ValueError, TypeError) as e:
            self.logger.error(f"Cache write error: {str(e)}")
            return False

    @monitor_service_performance("invalidate_people_cache")
    def invalidate_people_cache(
        self,
        session: Dict[str, Any]
    ) -> None:
        """
        Invalidate all cached people lists for user's session.

        Args:
            session: User session data
        """
        pattern = f"{self.CACHE_PREFIX}:bu_{session.get('bu_id')}:*"

        try:
            cache.delete_pattern(pattern)
            self.logger.info(f"Invalidated cache pattern: {pattern}")

        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Cache invalidation error: {str(e)}")

    def _generate_cache_key(
        self,
        params: Dict[str, Any]
    ) -> str:
        """
        Generate cache key from parameters (< 20 lines).

        Args:
            params: Parameters dictionary

        Returns:
            Cache key string
        """
        cache_params = {
            'bu_id': params.get('bu_id'),
            'client_id': params.get('client_id'),
            'search': params.get('search', ''),
            'start': params.get('start', 0),
            'length': params.get('length', 10),
            'order': params.get('order', '')
        }

        params_str = json.dumps(cache_params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]

        return f"{self.CACHE_PREFIX}:bu_{cache_params['bu_id']}:{params_hash}"

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "PeopleCachingService"