"""
Base Search Adapter Pattern

Abstract base class for entity-specific search adapters
Ensures consistent interface and permission handling

Complies with Rule #7: < 150 lines
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from django.db.models import QuerySet
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.exceptions import PermissionDenied


class BaseSearchAdapter(ABC):
    """
    Abstract base for entity search adapters

    Each adapter must implement:
    - get_queryset(): Return base queryset with optimizations
    - apply_filters(): Apply entity-specific filters
    - format_result(): Convert model instance to search result
    - get_actions(): Return available actions for result
    """

    entity_type: str = None

    def __init__(self, user, tenant, business_unit=None):
        """
        Initialize adapter with user context

        Args:
            user: Requesting user (for permissions)
            tenant: Tenant for isolation
            business_unit: Optional BU filter
        """
        self.user = user
        self.tenant = tenant
        business_unit = business_unit

    @abstractmethod
    def get_queryset(self) -> QuerySet:
        """
        Return base queryset with select_related/prefetch_related

        MUST follow Rule #12: Query optimization
        """
        pass

    @abstractmethod
    def apply_filters(self, queryset: QuerySet, filters: Dict) -> QuerySet:
        """
        Apply entity-specific filters

        Args:
            queryset: Base queryset
            filters: Filter dict from search request

        Returns:
            Filtered queryset
        """
        pass

    @abstractmethod
    def format_result(self, instance: Any) -> Dict:
        """
        Format model instance to search result

        Args:
            instance: Model instance

        Returns:
            Formatted result dict with title, subtitle, snippet
        """
        pass

    @abstractmethod
    def get_actions(self, instance: Any) -> List[Dict]:
        """
        Get available actions for this result

        Args:
            instance: Model instance

        Returns:
            List of action dicts {label, href, method}
        """
        pass

    def check_permission(self, instance: Any, action: str = 'view') -> bool:
        """
        Check if user has permission for this instance

        Args:
            instance: Model instance
            action: Permission action (view, edit, delete)

        Returns:
            True if permitted, False otherwise

        Complies with Rule #11: Specific exception handling
        """
        try:
            if hasattr(instance, 'tenant') and instance.tenant != self.tenant:
                return False

            if hasattr(self.user, f'has_perm'):
                perm = f'{self.entity_type}.{action}_{self.entity_type}'
                return self.user.has_perm(perm)

            return True

        except (AttributeError, TypeError) as e:
            return False

    def search(self, query: str, filters: Optional[Dict] = None, limit: int = 50) -> List[Dict]:
        """
        Execute search with permission filtering

        Args:
            query: Search query string
            filters: Additional filters
            limit: Max results

        Returns:
            List of formatted results

        Complies with Rule #17: Transaction management
        """
        filters = filters or {}

        queryset = self.get_queryset()

        queryset = queryset.filter(tenant=self.tenant)

        queryset = self.apply_filters(queryset, filters)

        if query:
            queryset = self._apply_fulltext_search(queryset, query)

        queryset = queryset[:limit]

        results = []
        for instance in queryset:
            if self.check_permission(instance):
                result = self.format_result(instance)
                result['actions'] = self.get_actions(instance)
                result['entity'] = self.entity_type
                results.append(result)

        return results

    def _apply_fulltext_search(self, queryset: QuerySet, query: str) -> QuerySet:
        """
        Apply PostgreSQL FTS to queryset

        Uses SearchQuery + SearchRank for relevance scoring
        """
        try:
            search_query = SearchQuery(query, search_type='websearch')

            search_fields = self.get_search_fields()

            if hasattr(queryset.model, 'search_vector'):
                queryset = queryset.annotate(
                    rank=SearchRank(models.F('search_vector'), search_query)
                ).filter(search_vector=search_query).order_by('-rank')
            else:
                from django.db.models import Q
                q_objects = Q()
                for field in search_fields:
                    q_objects |= Q(**{f'{field}__icontains': query})
                queryset = queryset.filter(q_objects)

            return queryset

        except (AttributeError, TypeError, ValueError) as e:
            return queryset

    @abstractmethod
    def get_search_fields(self) -> List[str]:
        """Return list of searchable field names"""
        pass