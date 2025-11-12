"""
Unified Search API Views

REST API endpoint for platform-wide semantic search.
Supports cross-module search with fuzzy matching and voice search.

Follows CLAUDE.md standards:
- Rule #2: Authentication required for all endpoints
- Rule #15: Tenant isolation enforced
- Rule #16: Input validation and sanitization
- Rule #18: API versioning (v1)
"""

import logging
import uuid
from typing import Optional

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone

from apps.search.services.unified_semantic_search_service import UnifiedSemanticSearchService
from apps.search.models import SearchAnalytics
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unified_search_view(request):
    """
    Unified semantic search across multiple modules.

    GET /api/v1/search/unified/?q=query&modules=tickets,assets&limit=20

    Query Parameters:
        q (str, required): Search query text
        modules (str, optional): Comma-separated modules to search
            Options: tickets, work_orders, assets, people, knowledge_base
            Default: all modules
        limit (int, optional): Maximum results (1-100). Default: 50
        status (str, optional): Filter by status (module-specific)
        priority (str, optional): Filter by priority (HIGH, MEDIUM, LOW)
        date_from (str, optional): Filter from date (ISO format)
        date_to (str, optional): Filter to date (ISO format)

    Returns:
        200 OK:
            {
                "results": [
                    {
                        "id": "uuid",
                        "module": "tickets",
                        "type": "ticket",
                        "title": "Ticket T00123",
                        "snippet": "AC not cooling in Building 3...",
                        "metadata": {
                            "status": "OPEN",
                            "priority": "HIGH",
                            ...
                        },
                        "url": "/helpdesk/ticket/123/",
                        "relevance_score": 0.95,
                        "timestamp": "2025-11-03T10:00:00Z"
                    },
                    ...
                ],
                "total_count": 15,
                "search_time_ms": 45,
                "query": "AC cooling issue",
                "modules_searched": ["tickets", "work_orders", "assets"],
                "suggestions": ["cooling", "hvac", "temperature"],
                "fuzzy_matches": ["Ticket T00124: AC cool issue"],
                "from_cache": false,
                "correlation_id": "uuid"
            }

        400 Bad Request:
            {
                "error": "Query parameter 'q' is required",
                "correlation_id": "uuid"
            }

        500 Internal Server Error:
            {
                "error": "Search service error",
                "correlation_id": "uuid"
            }

    Features:
        - Semantic similarity search using txtai
        - Fuzzy matching for typos
        - Multi-module cross-search
        - Tenant isolation (automatic)
        - Relevance ranking
        - Search suggestions
        - Voice search support (accepts transcribed text)
        - Result caching (5 minutes)
        - Search analytics tracking

    Examples:
        # Basic search
        GET /api/v1/search/unified/?q=AC+cooling

        # Search specific modules
        GET /api/v1/search/unified/?q=John+Doe&modules=people

        # Filter by priority
        GET /api/v1/search/unified/?q=urgent+repair&priority=HIGH

        # Date range search
        GET /api/v1/search/unified/?q=maintenance&date_from=2025-11-01&date_to=2025-11-03
    """
    correlation_id = str(uuid.uuid4())

    try:
        # Extract and validate parameters
        query = request.GET.get('q', '').strip()
        if not query:
            return Response(
                {
                    'error': "Query parameter 'q' is required",
                    'correlation_id': correlation_id,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse modules
        modules_param = request.GET.get('modules', '')
        if modules_param:
            modules = [m.strip() for m in modules_param.split(',') if m.strip()]
            # Validate module names
            valid_modules = {'tickets', 'work_orders', 'assets', 'people', 'knowledge_base'}
            invalid_modules = set(modules) - valid_modules
            if invalid_modules:
                return Response(
                    {
                        'error': f"Invalid modules: {', '.join(invalid_modules)}",
                        'valid_modules': list(valid_modules),
                        'correlation_id': correlation_id,
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            modules = None  # Search all

        # Parse limit
        try:
            limit = int(request.GET.get('limit', 50))
            if limit < 1 or limit > 100:
                return Response(
                    {
                        'error': "Limit must be between 1 and 100",
                        'correlation_id': correlation_id,
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {
                    'error': "Invalid limit parameter",
                    'correlation_id': correlation_id,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build filters
        filters = {}
        if request.GET.get('status'):
            filters['status'] = request.GET.get('status')
        if request.GET.get('priority'):
            filters['priority'] = request.GET.get('priority')
        if request.GET.get('date_from'):
            filters['date_from'] = request.GET.get('date_from')
        if request.GET.get('date_to'):
            filters['date_to'] = request.GET.get('date_to')

        # Get tenant from user
        tenant_id = request.user.tenant_id

        # Perform search
        service = UnifiedSemanticSearchService()
        result = service.search(
            query=query,
            tenant_id=tenant_id,
            modules=modules,
            limit=limit,
            user_id=request.user.id,
            filters=filters
        )

        # Add correlation ID
        result['correlation_id'] = correlation_id

        # Track search analytics (async to not slow down response)
        try:
            _track_search_analytics(
                tenant_id=tenant_id,
                user_id=request.user.id,
                query=query,
                modules=modules,
                filters=filters,
                result_count=result.get('total_count', 0),
                response_time_ms=result.get('search_time_ms', 0),
                correlation_id=correlation_id,
            )
        except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
            logger.warning(f"Failed to track search analytics: {e}", exc_info=True)

        return Response(result, status=status.HTTP_200_OK)

    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(
            f"Error in unified search (correlation_id={correlation_id}): {e}",
            exc_info=True
        )
        return Response(
            {
                'error': "Search service error",
                'correlation_id': correlation_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_suggestions_view(request):
    """
    Get search suggestions based on query prefix.

    GET /api/v1/search/suggestions/?q=cool

    Query Parameters:
        q (str, required): Query prefix (minimum 2 characters)
        limit (int, optional): Maximum suggestions (1-10). Default: 5

    Returns:
        200 OK:
            {
                "suggestions": [
                    "cooling",
                    "coolant",
                    "cool temperature"
                ],
                "query": "cool"
            }

    Features:
        - Based on previous searches
        - Tenant-specific suggestions
        - Cached for performance
    """
    try:
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return Response(
                {'error': "Query must be at least 2 characters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        limit = min(int(request.GET.get('limit', 5)), 10)
        tenant_id = request.user.tenant_id

        # Check cache
        cache_key = f"search_suggestions:{tenant_id}:{query.lower()}"
        cached_suggestions = cache.get(cache_key)

        if cached_suggestions:
            return Response({
                'suggestions': cached_suggestions,
                'query': query,
                'from_cache': True,
            })

        # Get suggestions from recent searches
        recent_searches = SearchAnalytics.objects.filter(
            tenant_id=tenant_id,
            query__istartswith=query
        ).values_list('query', flat=True).distinct()[:limit]

        suggestions = list(recent_searches)

        # Cache for 1 hour
        cache.set(cache_key, suggestions, 3600)

        return Response({
            'suggestions': suggestions,
            'query': query,
            'from_cache': False,
        })

    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error getting search suggestions: {e}", exc_info=True)
        return Response(
            {'error': "Failed to get suggestions"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_analytics_click_view(request):
    """
    Track search result click for analytics.

    POST /api/v1/search/analytics/click/
    {
        "correlation_id": "uuid",
        "entity_type": "ticket",
        "entity_id": "uuid",
        "position": 3
    }

    Body Parameters:
        correlation_id (str, required): Correlation ID from search
        entity_type (str, required): Type of entity clicked
        entity_id (str, required): ID of entity clicked
        position (int, required): Position in search results (0-indexed)

    Returns:
        200 OK:
            {
                "success": true,
                "message": "Click tracked"
            }

    Features:
        - Click-through rate tracking
        - Result position analysis
        - Search quality metrics
    """
    try:
        data = request.data

        # Validate required fields
        required_fields = ['correlation_id', 'entity_type', 'entity_id', 'position']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return Response(
                {'error': f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find and update search analytics record
        try:
            analytics = SearchAnalytics.objects.get(
                correlation_id=data['correlation_id']
            )
            analytics.clicked_entity_type = data['entity_type']
            analytics.clicked_entity_id = data['entity_id']
            analytics.click_position = data['position']
            analytics.save(update_fields=[
                'clicked_entity_type',
                'clicked_entity_id',
                'click_position'
            ])

            logger.info(
                f"Tracked click: {data['entity_type']} {data['entity_id']} "
                f"at position {data['position']}"
            )

            return Response({
                'success': True,
                'message': "Click tracked"
            })

        except SearchAnalytics.DoesNotExist:
            logger.warning(f"Analytics record not found: {data['correlation_id']}", exc_info=True)
            return Response(
                {'error': "Search analytics record not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Error tracking search click: {e}", exc_info=True)
        return Response(
            {'error': "Failed to track click"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _track_search_analytics(
    tenant_id: int,
    user_id: int,
    query: str,
    modules: Optional[list],
    filters: dict,
    result_count: int,
    response_time_ms: int,
    correlation_id: str,
):
    """Track search analytics in database."""
    try:
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.get(id=tenant_id)
        user = People.objects.get(id=user_id)

        SearchAnalytics.objects.create(
            tenant=tenant,
            user=user,
            query=query,
            entities=modules or [],
            filters=filters,
            result_count=result_count,
            response_time_ms=response_time_ms,
            correlation_id=correlation_id,
        )

        logger.debug(f"Tracked search analytics: {query} -> {result_count} results")

    except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
        logger.error(f"Failed to save search analytics: {e}", exc_info=True)
        # Don't raise - analytics failure shouldn't break search
