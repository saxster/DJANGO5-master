"""
Search Aggregator Service

Fan-out coordinator that queries multiple entity adapters,
merges results, and applies unified ranking

Complies with Rule #7: < 150 lines
Complies with Rule #11: Specific exception handling
Complies with Rule #17: Transaction management
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from apps.core.utils_new.db_utils import get_current_db_name
from apps.search.adapters.people_adapter import PeopleAdapter
from apps.search.adapters.ticket_adapter import TicketAdapter
from apps.search.adapters.workorder_adapter import WorkOrderAdapter
from apps.search.services.ranking_service import RankingService
from apps.search.models import SearchAnalytics

logger = logging.getLogger(__name__)


class SearchAggregatorService:
    """
    Coordinates search across multiple entity adapters

    Features:
    - Parallel fan-out to adapters
    - Unified ranking with RankingService
    - Permission enforcement
    - Analytics tracking
    - Query timeout (5 seconds)
    """

    ADAPTER_REGISTRY = {
        'people': PeopleAdapter,
        'ticket': TicketAdapter,
        'work_order': WorkOrderAdapter,
    }

    MAX_RESULTS_PER_ENTITY = 50
    SEARCH_TIMEOUT = 5

    def __init__(self, user, tenant, business_unit=None):
        self.user = user
        self.tenant = tenant
        self.business_unit = business_unit
        self.ranking_service = RankingService()

    def search(
        self,
        query: str,
        entities: Optional[List[str]] = None,
        filters: Optional[Dict] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Execute global search across entities

        Args:
            query: Search query string
            entities: Entity types to search (all if None)
            filters: Additional filters
            limit: Max total results

        Returns:
            Search results dict with ranked results
        """
        start_time = time.time()
        correlation_id = uuid.uuid4()
        entities = entities or list(self.ADAPTER_REGISTRY.keys())
        filters = filters or {}

        try:
            raw_results = self._fan_out_search(
                query,
                entities,
                filters
            )

            ranked_results = self.ranking_service.rank_results(
                raw_results,
                query
            )

            final_results = ranked_results[:limit]

            response_time_ms = int((time.time() - start_time) * 1000)

            self._track_analytics(
                query=query,
                entities=entities,
                filters=filters,
                result_count=len(final_results),
                response_time_ms=response_time_ms,
                correlation_id=correlation_id
            )

            return {
                'results': final_results,
                'total_results': len(final_results),
                'response_time_ms': response_time_ms,
                'query_id': str(correlation_id),
            }

        except PermissionDenied as e:
            logger.warning(f"Permission denied for search: {e}", extra={'user_id': self.user.id})
            raise
        except ValidationError as e:
            logger.error(f"Validation error in search: {e}")
            raise
        except (DatabaseError, TimeoutError) as e:
            logger.error(f"Database error in search: {e}", extra={'correlation_id': str(correlation_id)})
            return {'results': [], 'total_results': 0, 'error': 'Search temporarily unavailable'}

    def _fan_out_search(
        self,
        query: str,
        entities: List[str],
        filters: Dict
    ) -> List[Dict]:
        """
        Parallel search across adapters with timeout
        """
        results = []

        with ThreadPoolExecutor(max_workers=len(entities)) as executor:
            future_to_entity = {}

            for entity_type in entities:
                adapter_class = self.ADAPTER_REGISTRY.get(entity_type)
                if not adapter_class:
                    continue

                adapter = adapter_class(self.user, self.tenant, self.business_unit)
                future = executor.submit(
                    adapter.search,
                    query,
                    filters.get(entity_type, {}),
                    self.MAX_RESULTS_PER_ENTITY
                )
                future_to_entity[future] = entity_type

            for future in as_completed(future_to_entity, timeout=self.SEARCH_TIMEOUT):
                try:
                    entity_results = future.result()
                    results.extend(entity_results)
                except TimeoutError:
                    logger.warning(f"Search timeout for {future_to_entity[future]}")
                except (DatabaseError, PermissionDenied) as e:
                    logger.error(f"Adapter error: {e}")

        return results

    def _track_analytics(
        self,
        query: str,
        entities: List[str],
        filters: Dict,
        result_count: int,
        response_time_ms: int,
        correlation_id: uuid.UUID
    ):
        """
        Track search analytics (Rule #15: No PII in logs)
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                SearchAnalytics.objects.create(
                    tenant=self.tenant,
                    user=self.user,
                    query=query[:500],
                    entities=entities,
                    filters=filters,
                    result_count=result_count,
                    response_time_ms=response_time_ms,
                    correlation_id=correlation_id
                )
        except (DatabaseError, ValidationError) as e:
            logger.error(f"Failed to track analytics: {e}")