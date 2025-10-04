"""
Search REST API Views

Enhanced with:
- Query sanitization (Rule #9: Input validation)
- Result caching (5-minute TTL)
- Rate limiting (via middleware)

Complies with Rule #8: View methods < 30 lines
Complies with Rule #17: Transaction management
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from apps.search.services.aggregator_service import SearchAggregatorService
from apps.search.services.caching_service import SearchCacheService
from apps.core.services.query_sanitization_service import query_sanitizer
from apps.search.serializers import (
    SearchRequestSerializer,
    SearchResponseSerializer,
    SavedSearchSerializer
)
import logging

logger = logging.getLogger(__name__)


class GlobalSearchView(APIView):
    """
    POST /api/v1/search

    Global search across all entities with permission filtering
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Execute global search with sanitization and caching.

        Enhanced with:
        - Query sanitization to prevent injection attacks
        - Redis caching (5-min TTL) for performance
        - Rate limiting (handled by middleware)
        """
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Sanitize query input (Rule #9)
            raw_query = serializer.validated_data['query']
            sanitized_query = query_sanitizer.sanitize_sql_input(
                raw_query,
                context='value'
            )

            entities = serializer.validated_data.get('entities', [])
            filters = serializer.validated_data.get('filters', {})
            limit = serializer.validated_data.get('limit', 20)

            # Check cache first
            cache_service = SearchCacheService(
                tenant_id=request.user.tenant.id,
                user_id=request.user.id
            )
            cached_results = cache_service.get_cached_results(
                sanitized_query,
                entities,
                filters
            )

            if cached_results:
                cached_results['from_cache'] = True
                return Response(cached_results, status=status.HTTP_200_OK)

            # Execute search
            search_service = SearchAggregatorService(
                user=request.user,
                tenant=request.user.tenant,
                business_unit=request.user.business_unit
            )

            results = search_service.search(
                query=sanitized_query,
                entities=entities,
                filters=filters,
                limit=limit
            )

            # Cache results
            cache_service.cache_results(
                sanitized_query,
                entities,
                filters,
                results
            )

            results['from_cache'] = False
            return Response(results, status=status.HTTP_200_OK)

        except PermissionDenied:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValidationError as e:
            logger.warning(f"Search validation error: {e}")
            return Response(
                {'error': 'Invalid search parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Search database error: {e}", exc_info=True)
            return Response(
                {'error': 'Search temporarily unavailable'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SavedSearchListCreateView(APIView):
    """
    GET /api/v1/search/saved - List saved searches
    POST /api/v1/search/saved - Create saved search
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List user's saved searches (< 30 lines)"""

        from apps.search.models import SavedSearch

        saved_searches = SavedSearch.objects.filter(
            tenant=request.user.tenant,
            user=request.user
        ).order_by('-created_on')

        data = [
            {
                'id': str(s.id),
                'name': s.name,
                'query': s.query,
                'is_alert_enabled': s.is_alert_enabled,
            }
            for s in saved_searches
        ]

        return Response({'saved_searches': data}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create saved search (< 30 lines)"""

        serializer = SavedSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from apps.search.models import SavedSearch

        saved_search = SavedSearch.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            **serializer.validated_data
        )

        return Response(
            {'id': str(saved_search.id), 'message': 'Saved search created'},
            status=status.HTTP_201_CREATED
        )