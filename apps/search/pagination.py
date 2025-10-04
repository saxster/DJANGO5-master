"""
Enhanced Pagination for Search API

Provides both offset-based and cursor-based pagination:
- Offset pagination: Simple, familiar, good for small datasets
- Cursor pagination: Efficient for large datasets, prevents deep pagination issues

Compliance with .claude/rules.md:
- Rule #12: Database query optimization
"""

import base64
import json
from typing import Dict, Any, Optional, List
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict


class SearchOffsetPagination(PageNumberPagination):
    """
    Offset-based pagination for search results.

    Good for:
    - Small to medium datasets (< 10K results)
    - When users need to jump to specific pages
    - Familiar UX pattern

    Limitations:
    - Slow for deep pagination (page 1000+)
    - Can skip/duplicate results if data changes during pagination
    """

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """Enhanced response with total count estimate"""
        return Response(OrderedDict([
            ('pagination', {
                'count': self.page.paginator.count,
                'page': self.page.number,
                'page_size': self.page_size,
                'total_pages': self.page.paginator.num_pages,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }),
            ('results', data)
        ]))


class SearchCursorPagination(CursorPagination):
    """
    Cursor-based pagination for search results.

    Good for:
    - Large datasets (100K+ results)
    - Infinite scroll UX
    - Real-time data feeds

    Advantages:
    - O(1) performance regardless of dataset size
    - No skip/duplicate issues
    - Efficient database queries (uses indexes)

    Limitations:
    - No jumping to specific pages
    - No total count (expensive to calculate)
    """

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_on'  # Must have stable ordering
    cursor_query_param = 'cursor'

    def get_paginated_response(self, data):
        """Enhanced cursor-based response"""
        return Response(OrderedDict([
            ('pagination', {
                'page_size': self.page_size,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'has_next': self.get_next_link() is not None,
                'has_previous': self.get_previous_link() is not None,
                # Note: total count omitted for performance
                # Calculating COUNT(*) on large datasets is expensive
            }),
            ('results', data)
        ]))


class HybridSearchPagination:
    """
    Hybrid pagination that intelligently switches between offset and cursor.

    Strategy:
    - Use offset pagination for first 1000 results (good UX)
    - Switch to cursor pagination after page 40 (prevents deep pagination issues)
    - Provide total count estimate (not exact) for performance
    """

    OFFSET_THRESHOLD = 40  # Switch to cursor after page 40
    MAX_COUNT_ESTIMATE = 10000  # Max results to count exactly

    def __init__(self, page: int = 1, page_size: int = 25):
        self.page = page
        self.page_size = min(page_size, 100)  # Max 100 per page
        self.use_cursor = page > self.OFFSET_THRESHOLD

    def paginate_queryset(self, queryset, request):
        """
        Paginate queryset using appropriate strategy.

        Returns:
            Tuple of (paginated_results, pagination_metadata)
        """
        if self.use_cursor:
            return self._paginate_with_cursor(queryset, request)
        else:
            return self._paginate_with_offset(queryset, request)

    def _paginate_with_offset(self, queryset, request):
        """Offset pagination for early pages"""
        offset = (self.page - 1) * self.page_size
        limit = self.page_size

        # Get total count (with limit for performance)
        total_count = self._get_estimated_count(queryset)

        # Slice queryset
        results = list(queryset[offset:offset + limit])

        # Calculate pagination metadata
        total_pages = (total_count + self.page_size - 1) // self.page_size
        has_next = self.page < total_pages
        has_previous = self.page > 1

        metadata = {
            'type': 'offset',
            'page': self.page,
            'page_size': self.page_size,
            'total_count': total_count,
            'total_count_estimated': total_count >= self.MAX_COUNT_ESTIMATE,
            'total_pages': total_pages,
            'has_next': has_next,
            'has_previous': has_previous,
        }

        return results, metadata

    def _paginate_with_cursor(self, queryset, request):
        """Cursor pagination for deep pages"""
        # For cursor pagination, we need the last seen ID
        cursor = request.query_params.get('cursor')

        if cursor:
            cursor_id = self._decode_cursor(cursor)
            queryset = queryset.filter(id__lt=cursor_id)

        results = list(queryset[:self.page_size + 1])

        # Check if there are more results
        has_next = len(results) > self.page_size
        if has_next:
            results = results[:self.page_size]

        # Generate next cursor
        next_cursor = None
        if has_next and results:
            next_cursor = self._encode_cursor(results[-1].id)

        metadata = {
            'type': 'cursor',
            'page_size': self.page_size,
            'has_next': has_next,
            'next_cursor': next_cursor,
            # No total count for cursor pagination (performance)
        }

        return results, metadata

    def _get_estimated_count(self, queryset) -> int:
        """
        Get estimated count with performance optimization.

        For large datasets, exact COUNT(*) is expensive.
        We limit the count query for better performance.
        """
        try:
            # Try to get exact count up to threshold
            count = queryset[:self.MAX_COUNT_ESTIMATE + 1].count()
            return min(count, self.MAX_COUNT_ESTIMATE)
        except Exception:
            # Fallback to approximate count
            return self.MAX_COUNT_ESTIMATE

    def _encode_cursor(self, cursor_id: int) -> str:
        """Encode cursor ID to base64 string"""
        cursor_data = {'id': cursor_id}
        cursor_json = json.dumps(cursor_data)
        cursor_bytes = cursor_json.encode('utf-8')
        return base64.b64encode(cursor_bytes).decode('utf-8')

    def _decode_cursor(self, cursor_str: str) -> int:
        """Decode cursor string to ID"""
        try:
            cursor_bytes = base64.b64decode(cursor_str.encode('utf-8'))
            cursor_json = cursor_bytes.decode('utf-8')
            cursor_data = json.loads(cursor_json)
            return cursor_data['id']
        except (ValueError, KeyError, json.JSONDecodeError):
            raise ValueError("Invalid cursor format")
