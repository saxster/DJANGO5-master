"""
NOC Views Utilities.

Helper functions for pagination, filtering, and response formatting.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import logging
from typing import Any, Dict
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from django.db.models import QuerySet

__all__ = [
    'NOCPagination',
    'paginated_response',
    'success_response',
    'error_response',
    'parse_filter_params',
]

logger = logging.getLogger('noc.views')


class NOCPagination(PageNumberPagination):
    """Custom pagination for NOC API endpoints."""

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.page_size,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })


def paginated_response(queryset: QuerySet, serializer_class, request, context: Dict = None) -> Response:
    """
    Create paginated response from queryset.

    Args:
        queryset: Django queryset to paginate
        serializer_class: Serializer class to use
        request: Django request object
        context: Additional context for serializer

    Returns:
        Response: Paginated DRF response
    """
    paginator = NOCPagination()
    page = paginator.paginate_queryset(queryset, request)

    if page is not None:
        serializer_context = {'user': request.user, 'request': request}
        if context:
            serializer_context.update(context)

        serializer = serializer_class(page, many=True, context=serializer_context)
        return paginator.get_paginated_response(serializer.data)

    serializer_context = {'user': request.user, 'request': request}
    if context:
        serializer_context.update(context)

    serializer = serializer_class(queryset, many=True, context=serializer_context)
    return Response(serializer.data)


def success_response(data: Any = None, message: str = None, status_code: int = status.HTTP_200_OK) -> Response:
    """
    Create standardized success response.

    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code

    Returns:
        Response: DRF response
    """
    response_data = {'status': 'success'}

    if message:
        response_data['message'] = message

    if data is not None:
        response_data['data'] = data

    return Response(response_data, status=status_code)


def error_response(message: str, errors: Dict = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    """
    Create standardized error response.

    Args:
        message: Error message
        errors: Detailed error dict
        status_code: HTTP status code

    Returns:
        Response: DRF response
    """
    response_data = {
        'status': 'error',
        'message': message
    }

    if errors:
        response_data['errors'] = errors

    return Response(response_data, status=status_code)


def parse_filter_params(request) -> Dict[str, Any]:
    """
    Parse common filter parameters from request.

    Args:
        request: Django request object

    Returns:
        Dict: Parsed filter parameters
    """
    filters = {}

    if client_ids := request.GET.get('client_ids'):
        try:
            filters['client_ids'] = [int(cid) for cid in client_ids.split(',') if cid]
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid client_ids format", extra={'error': str(e)})

    if city := request.GET.get('city'):
        filters['city'] = city

    if state := request.GET.get('state'):
        filters['state'] = state

    if oic_id := request.GET.get('oic_id'):
        try:
            filters['oic_id'] = int(oic_id)
        except (ValueError, TypeError):
            logger.warning("Invalid oic_id format")

    if time_range := request.GET.get('time_range'):
        try:
            filters['time_range_hours'] = int(time_range)
        except (ValueError, TypeError):
            filters['time_range_hours'] = 24

    if status_filter := request.GET.get('status'):
        filters['status'] = status_filter

    if severity := request.GET.get('severity'):
        filters['severity'] = severity

    if entity_type := request.GET.get('entity_type'):
        filters['entity_type'] = entity_type

    return filters