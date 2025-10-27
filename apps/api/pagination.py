"""
Custom Pagination Classes for REST API

Provides efficient pagination strategies optimized for different use cases.

Compliance with .claude/rules.md:
- Utility functions < 50 lines
- Specific exception handling (no bare except)
"""

from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict


class MobileSyncCursorPagination(CursorPagination):
    """
    Cursor-based pagination optimized for mobile sync operations.

    Benefits over offset pagination:
    - O(1) performance regardless of page depth
    - Stable pagination even with concurrent writes
    - Lower database load for deep pagination

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            pagination_class = MobileSyncCursorPagination

    Mobile client usage:
        GET /api/v1/people/?cursor=cD0yMDI1LTEwLTI3
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    ordering = '-modified_at'  # Most recent first for sync
    cursor_query_param = 'cursor'

    def get_paginated_response(self, data):
        """
        Return paginated response with metadata for mobile sync.

        Response format:
        {
            "next": "cD0yMDI1LTEwLTI3" or null,
            "previous": "cj0xNjk4NzY1NDMy" or null,
            "count": 1500,  # Approximate count
            "results": [...]
        }
        """
        return Response(OrderedDict([
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('count', self.page.paginator.count if hasattr(self.page, 'paginator') else None),
            ('results', data)
        ]))


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard page-based pagination for web UI and simple list views.

    Usage:
        GET /api/v1/people/?page=2&page_size=25

    Response includes:
    - count: Total number of items
    - next/previous: Full URLs to adjacent pages
    - results: Current page data
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Return paginated response with full metadata.
        """
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('results', data)
        ]))


class LargePaginationSet(PageNumberPagination):
    """
    Pagination for large datasets (reports, analytics).

    Usage: Bulk export operations
    Page size: 100 items
    Max: 500 items per request
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


__all__ = [
    'MobileSyncCursorPagination',
    'StandardPageNumberPagination',
    'LargePaginationSet',
]
