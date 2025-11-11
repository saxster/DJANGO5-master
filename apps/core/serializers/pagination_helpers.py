"""
Pagination Helpers and Query Optimization Mixins
Provides enhanced pagination with metadata and eager loading utilities
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class FrontendPagination(PageNumberPagination):
    """
    Enhanced pagination with frontend-friendly metadata
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Return paginated response with enhanced metadata
        """
        pagination_meta = self._build_pagination_meta()

        # Use response envelope if view supports it
        if self._has_response_envelope():
            return self._get_envelope_response(data, pagination_meta)

        return Response({
            'results': data,
            **pagination_meta
        })

    def _build_pagination_meta(self):
        """
        Build pagination metadata dictionary
        """
        return {
            'pagination': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'total_items': self.page.paginator.count,
                'page_size': self.get_page_size(self.request),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
                'next_page': self.page.next_page_number() if self.page.has_next() else None,
                'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
                'start_index': self.page.start_index(),
                'end_index': self.page.end_index(),
            }
        }

    def _has_response_envelope(self):
        """
        Check if view has response envelope method
        """
        return (hasattr(self.request, 'view') and
                hasattr(self.request.view, 'get_response_envelope'))

    def _get_envelope_response(self, data, pagination_meta):
        """
        Get response using view's response envelope
        """
        return Response(self.request.view.get_response_envelope(
            data=data,
            request=self.request,
            **pagination_meta
        ))


class RelationshipEagerLoadingMixin:
    """
    Mixin to optimize database queries for relationships
    """

    def get_optimized_queryset(self, queryset):
        """
        Apply select_related and prefetch_related optimizations
        """
        if hasattr(self.Meta, 'select_related'):
            queryset = queryset.select_related(*self.Meta.select_related)

        if hasattr(self.Meta, 'prefetch_related'):
            queryset = queryset.prefetch_related(*self.Meta.prefetch_related)

        return queryset

    @classmethod
    def setup_eager_loading(cls, queryset):
        """
        Class method to set up eager loading for viewsets
        """
        serializer = cls()
        return serializer.get_optimized_queryset(queryset)
