"""
Geofence Query Service

Handles geofence data retrieval, caching, and query operations.
Separated from validation logic for single responsibility principle.

Following .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #11: Specific exception handling
- Rule #13: Use constants instead of magic numbers
"""

import logging
from typing import List, Dict, Optional
from django.core.cache import cache
from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.onboarding.models import GeofenceMaster, Bt
from apps.core.constants.spatial_constants import GEOFENCE_CACHE_TTL

logger = logging.getLogger(__name__)
error_logger = logging.getLogger("error_logger")


class GeofenceQueryService:
    """
    Service for geofence data retrieval and caching operations.

    Responsibilities:
    - Fetch active geofences with caching
    - Retrieve individual geofence data
    - Cache invalidation operations
    """

    # Cache key templates
    ACTIVE_GEOFENCES_KEY = "active_geofences:{client_id}:{bu_id}"
    GEOFENCE_DATA_KEY = "geofence_data:{geofence_id}"

    def __init__(self, cache_timeout: Optional[int] = None):
        """
        Initialize query service.

        Args:
            cache_timeout: Cache TTL in seconds (default: from constants)
        """
        self.cache_timeout = cache_timeout or GEOFENCE_CACHE_TTL

    def get_active_geofences(
        self,
        client_id: int,
        bu_id: int,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Get active geofences for a client/business unit with caching.

        Args:
            client_id: Client ID
            bu_id: Business Unit ID
            use_cache: Whether to use Redis cache

        Returns:
            List of active geofences with geometry data

        Example:
            >>> service = GeofenceQueryService()
            >>> geofences = service.get_active_geofences(client_id=1, bu_id=5)
            >>> len(geofences)
            12
        """
        cache_key = self.ACTIVE_GEOFENCES_KEY.format(
            client_id=client_id, bu_id=bu_id
        )

        # Try cache first
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for geofences: {cache_key}")
                return cached_result

        # Fetch from database
        try:
            geofences = list(
                GeofenceMaster.objects.filter(
                    client_id=client_id,
                    bu_id=bu_id,
                    enable=True
                ).exclude(
                    id=1  # Exclude default/template geofence
                ).values(
                    'id', 'gfcode', 'gfname', 'geofence', 'alerttext',
                    'alerttogroup_id', 'alerttopeople_id', 'gftype'
                )
            )

            # Cache the result
            if use_cache:
                cache.set(cache_key, geofences, self.cache_timeout)
                logger.debug(f"Cached {len(geofences)} geofences: {cache_key}")

            return geofences

        except (DatabaseError, IntegrityError) as e:
            error_logger.error(
                f"Database error fetching active geofences "
                f"(client={client_id}, bu={bu_id}): {str(e)}"
            )
            return []
        except ObjectDoesNotExist as e:
            error_logger.error(
                f"Geofences not found (client={client_id}, bu={bu_id}): {str(e)}"
            )
            return []

    def get_geofence_by_id(
        self,
        geofence_id: int,
        use_cache: bool = True
    ) -> Optional[Dict]:
        """
        Get individual geofence by ID with caching.

        Args:
            geofence_id: Geofence ID
            use_cache: Whether to use cache

        Returns:
            Geofence data dictionary or None if not found
        """
        cache_key = self.GEOFENCE_DATA_KEY.format(geofence_id=geofence_id)

        # Try cache first
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for geofence: {cache_key}")
                return cached_result

        # Fetch from database
        try:
            geofence = GeofenceMaster.objects.filter(
                id=geofence_id,
                enable=True
            ).values(
                'id', 'gfcode', 'gfname', 'geofence', 'alerttext',
                'alerttogroup_id', 'alerttopeople_id', 'gftype',
                'client_id', 'bu_id'
            ).first()

            if geofence and use_cache:
                cache.set(cache_key, geofence, self.cache_timeout)
                logger.debug(f"Cached geofence: {cache_key}")

            return geofence

        except (DatabaseError, IntegrityError) as e:
            error_logger.error(
                f"Database error fetching geofence {geofence_id}: {str(e)}"
            )
            return None
        except ObjectDoesNotExist:
            logger.warning(f"Geofence {geofence_id} not found")
            return None

    def invalidate_geofence_cache(
        self,
        client_id: int,
        bu_id: Optional[int] = None
    ):
        """
        Invalidate geofence cache for specific client/bu or all bu under client.

        Args:
            client_id: Client ID
            bu_id: Optional Business Unit ID (None = invalidate all for client)

        Example:
            >>> service = GeofenceQueryService()
            >>> service.invalidate_geofence_cache(client_id=1, bu_id=5)
            >>> # or invalidate all
            >>> service.invalidate_geofence_cache(client_id=1)
        """
        try:
            if bu_id:
                # Clear specific client/bu cache
                cache_key = self.ACTIVE_GEOFENCES_KEY.format(
                    client_id=client_id, bu_id=bu_id
                )
                cache.delete(cache_key)
                logger.info(f"Cleared geofence cache: {cache_key}")
            else:
                # Clear all geofence caches for client
                bus = Bt.objects.filter(
                    client_id=client_id
                ).values_list('id', flat=True)

                deleted_count = 0
                for bu_id_item in bus:
                    cache_key = self.ACTIVE_GEOFENCES_KEY.format(
                        client_id=client_id, bu_id=bu_id_item
                    )
                    cache.delete(cache_key)
                    deleted_count += 1

                logger.info(
                    f"Cleared {deleted_count} geofence caches "
                    f"for client {client_id}"
                )

        except (DatabaseError, IntegrityError) as e:
            error_logger.error(
                f"Database error invalidating geofence cache: {str(e)}"
            )
        except Exception as e:
            error_logger.error(
                f"Unexpected error invalidating geofence cache: {str(e)}",
                exc_info=True
            )

    def invalidate_geofence_by_id(self, geofence_id: int):
        """
        Invalidate cache for a specific geofence.

        Args:
            geofence_id: Geofence ID to invalidate
        """
        cache_key = self.GEOFENCE_DATA_KEY.format(geofence_id=geofence_id)
        cache.delete(cache_key)
        logger.info(f"Cleared geofence cache: {cache_key}")


# Singleton instance
geofence_query_service = GeofenceQueryService()