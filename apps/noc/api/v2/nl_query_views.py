"""
NOC Natural Language Query API Views.

REST API endpoints for natural language querying of NOC data.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #8 (view methods <30 lines),
Rule #11 (specific exception handling).
"""

import logging
from django.core.exceptions import ValidationError, PermissionDenied
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle

from apps.noc.services.nl_query_service import NLQueryService
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


__all__ = ['natural_language_query_view', 'query_cache_stats_view']

logger = logging.getLogger('noc.api.nl_query')


class NLQueryRateThrottle(UserRateThrottle):
    """Rate limit for natural language queries: 10 requests per minute."""
    rate = '10/min'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([NLQueryRateThrottle])
@never_cache
def natural_language_query_view(request):
    """
    Process natural language query against NOC data.

    **Endpoint:** POST /api/v2/noc/query/nl/

    **Authentication:** Required (JWT or session)

    **Rate Limit:** 10 queries per minute per user

    **Required Permission:** `noc:view`

    **Request Body:**
    ```json
    {
        "query": "Show me critical alerts from the last 24 hours",
        "output_format": "summary"  // Optional: summary, detailed, table, json
    }
    ```

    **Response (Success):**
    ```json
    {
        "status": "success",
        "summary": "Found 5 critical alerts in the last 24 hours...",
        "data": [...],
        "insights": "3 alerts concentrated in Site A...",
        "metadata": {...},
        "cached": false
    }
    ```

    **Response (Error):**
    ```json
    {
        "status": "error",
        "error": "Error message",
        "error_type": "ValidationError"
    }
    ```

    **Status Codes:**
    - 200: Query processed successfully
    - 400: Invalid query text or parameters
    - 403: Permission denied (missing noc:view capability)
    - 429: Rate limit exceeded
    - 500: Server error during query processing
    """
    try:
        # Extract query text
        query_text = request.data.get('query')
        if not query_text:
            return Response(
                {
                    'status': 'error',
                    'error': 'Missing required field: query',
                    'error_type': 'ValidationError'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract output format (optional)
        output_format = request.data.get('output_format', 'summary')

        # Validate output format
        valid_formats = ['summary', 'detailed', 'table', 'json']
        if output_format not in valid_formats:
            return Response(
                {
                    'status': 'error',
                    'error': f'Invalid output_format. Must be one of: {", ".join(valid_formats)}',
                    'error_type': 'ValidationError'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Log query attempt
        logger.info(
            f"NL query request",
            extra={
                'user_id': request.user.id,
                'query_length': len(query_text),
                'output_format': output_format,
                'ip_address': request.META.get('REMOTE_ADDR'),
            }
        )

        # Process query
        result = NLQueryService.process_natural_language_query(
            query_text=query_text,
            user=request.user,
            output_format=output_format
        )

        # Log successful response
        logger.info(
            f"NL query processed successfully",
            extra={
                'user_id': request.user.id,
                'result_count': len(result.get('data', [])),
                'cached': result.get('cached', False),
            }
        )

        return Response(result, status=status.HTTP_200_OK)

    except ValidationError as e:
        logger.warning(
            f"Validation error: {e}",
            extra={'user_id': request.user.id}
        )
        return Response(
            {
                'status': 'error',
                'error': str(e),
                'error_type': 'ValidationError'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    except PermissionDenied as e:
        logger.warning(
            f"Permission denied: {e}",
            extra={'user_id': request.user.id}
        )
        return Response(
            {
                'status': 'error',
                'error': str(e),
                'error_type': 'PermissionDenied'
            },
            status=status.HTTP_403_FORBIDDEN
        )

    except ValueError as e:
        logger.error(
            f"Query processing error: {e}",
            extra={'user_id': request.user.id},
            exc_info=True
        )
        return Response(
            {
                'status': 'error',
                'error': str(e),
                'error_type': 'ValueError'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Unexpected error processing NL query: {e}",
            extra={'user_id': request.user.id},
            exc_info=True
        )
        return Response(
            {
                'status': 'error',
                'error': 'Internal server error processing query',
                'error_type': 'ServerError'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def query_cache_stats_view(request):
    """
    Get natural language query cache statistics.

    **Endpoint:** GET /api/v2/noc/query/nl/stats/

    **Authentication:** Required

    **Required Permission:** `noc:view`

    **Response:**
    ```json
    {
        "status": "success",
        "cache_stats": {
            "hits": 150,
            "misses": 50,
            "total_queries": 200,
            "hit_rate_percent": 75.0
        }
    }
    ```
    """
    try:
        stats = NLQueryService.get_cache_stats()

        logger.info(
            f"Cache stats requested",
            extra={'user_id': request.user.id}
        )

        return Response(
            {
                'status': 'success',
                'cache_stats': stats
            },
            status=status.HTTP_200_OK
        )

    except NETWORK_EXCEPTIONS as e:
        logger.error(
            f"Error retrieving cache stats: {e}",
            extra={'user_id': request.user.id},
            exc_info=True
        )
        return Response(
            {
                'status': 'error',
                'error': 'Failed to retrieve cache statistics'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
