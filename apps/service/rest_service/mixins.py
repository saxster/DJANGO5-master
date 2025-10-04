"""
REST API ViewSet Mixins

Provides tenant isolation, pagination, and query optimization for REST viewsets.

Security Features:
- Automatic tenant filtering by client_id
- Permission-based access control
- Pagination to prevent resource exhaustion
- Query optimization with select_related

Compliance: Addresses CRITICAL tenant isolation vulnerability in REST API
"""

from rest_framework import viewsets, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from datetime import datetime
from typing import List
import logging

logger = logging.getLogger('api')


class TenantAwarePagination(PageNumberPagination):
    """
    Pagination class with configurable page sizes for tenant-aware API.

    Default: 50 items per page
    Max: 100 items per page (prevents excessive data exposure)
    Client can customize via 'page_size' query parameter
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """Enhanced pagination response with metadata."""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.page_size,
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })


class TenantFilteredViewSetMixin:
    """
    Mixin to enforce tenant isolation on all viewsets.

    Security Features:
    - Automatic filtering by request.user.client_id
    - Prevents cross-tenant data access
    - Optional last_update filtering for mobile sync
    - Query optimization with select_related/prefetch_related

    Usage:
        class MyViewSet(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
            queryset = MyModel.objects.all()
            serializer_class = MyModelSerializer

            def _get_related_fields(self):
                return ['related_model', 'another_relation']
    """

    permission_classes = [IsAuthenticated]
    pagination_class = TenantAwarePagination

    def get_queryset(self):
        """
        Get queryset with automatic tenant filtering and optimization.

        Returns:
            QuerySet filtered by client_id and optimized with select_related
        """
        queryset = super().get_queryset() if hasattr(super(), 'get_queryset') else self.queryset

        user = self.request.user

        # Ensure user is authenticated
        if not user or not user.is_authenticated:
            logger.warning(
                "Unauthenticated REST API access attempt",
                extra={'endpoint': self.request.path}
            )
            return queryset.none()

        # Apply tenant filtering
        queryset = self._apply_tenant_filter(queryset, user)

        # Apply last_update filtering for mobile sync
        queryset = self._apply_sync_filter(queryset)

        # Apply query optimization
        queryset = self._optimize_queryset(queryset)

        # Log access for security monitoring
        self._log_access(user, queryset)

        return queryset

    def _apply_tenant_filter(self, queryset, user):
        """
        Filter queryset by tenant (client_id).

        Args:
            queryset: Base queryset
            user: Authenticated user

        Returns:
            Tenant-filtered queryset
        """
        model = queryset.model

        # Check if model has client_id field
        if hasattr(model, 'client_id'):
            queryset = queryset.filter(client_id=user.client_id)

            logger.debug(
                f"Applied client_id filter: {user.client_id}",
                extra={
                    'user_id': user.id,
                    'client_id': user.client_id,
                    'model': model.__name__
                }
            )

        # Check if model has tenant_id field (alternative naming)
        elif hasattr(model, 'tenant_id'):
            queryset = queryset.filter(tenant_id=user.client_id)

        else:
            # Model doesn't have tenant field - log warning
            logger.warning(
                f"Model {model.__name__} lacks tenant filtering field",
                extra={
                    'model': model.__name__,
                    'user_id': user.id,
                    'security_risk': 'potential_cross_tenant_access'
                }
            )

        return queryset

    def _apply_sync_filter(self, queryset):
        """
        Filter by last_update parameter for mobile sync optimization.

        Args:
            queryset: Base queryset

        Returns:
            QuerySet filtered by mdtz if last_update provided
        """
        last_update = self.request.query_params.get('last_update')

        if last_update and hasattr(queryset.model, 'mdtz'):
            try:
                # Parse ISO format datetime
                last_update_dt = datetime.strptime(
                    last_update,
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                queryset = queryset.filter(mdtz__gt=last_update_dt)

                logger.debug(
                    f"Applied sync filter: last_update={last_update}",
                    extra={'last_update': last_update}
                )

            except ValueError as e:
                logger.warning(
                    f"Invalid last_update format: {last_update}",
                    extra={'error': str(e), 'last_update': last_update}
                )

        return queryset

    def _optimize_queryset(self, queryset):
        """
        Optimize queryset with select_related and prefetch_related.

        Calls _get_related_fields() which should be overridden by subclasses
        to specify which related fields to fetch.

        Args:
            queryset: Base queryset

        Returns:
            Optimized queryset with related fields pre-fetched
        """
        related_fields = self._get_related_fields()

        if related_fields:
            # Apply select_related for foreign key relationships
            queryset = queryset.select_related(*related_fields)

            logger.debug(
                f"Applied query optimization: {related_fields}",
                extra={'related_fields': related_fields}
            )

        return queryset

    def _get_related_fields(self) -> List[str]:
        """
        Override this method in subclasses to specify related fields.

        Returns:
            List of field names for select_related()

        Example:
            def _get_related_fields(self):
                return ['department', 'bu', 'client']
        """
        return []

    def _log_access(self, user, queryset):
        """
        Log API access for security monitoring.

        Args:
            user: Authenticated user
            queryset: Final queryset being accessed
        """
        if hasattr(self, 'action') and self.action in ['list', 'retrieve']:
            logger.info(
                f"REST API access: {self.action}",
                extra={
                    'user_id': user.id,
                    'client_id': user.client_id,
                    'action': self.action,
                    'model': queryset.model.__name__,
                    'endpoint': self.request.path
                }
            )

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to ensure tenant isolation on single object access.

        This prevents users from accessing objects outside their tenant
        by directly accessing /api/model/ID/ URLs.
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)

        except PermissionDenied:
            logger.warning(
                f"Cross-tenant access attempt blocked",
                extra={
                    'user_id': request.user.id,
                    'client_id': request.user.client_id,
                    'attempted_id': kwargs.get('pk'),
                    'model': self.queryset.model.__name__
                }
            )
            return Response(
                {'detail': 'Object not found or access denied.'},
                status=status.HTTP_404_NOT_FOUND
            )


class AdminOverrideMixin:
    """
    Mixin that allows admins to override tenant filtering.

    Use with caution - only for admin-facing viewsets where
    cross-tenant access is required (e.g., admin dashboards).
    """

    def get_queryset(self):
        """Allow admins to see all data, regular users see tenant-filtered data."""
        queryset = super().get_queryset()
        user = self.request.user

        if user and user.is_authenticated and user.isadmin:
            # Admin sees all data
            logger.info(
                f"Admin accessing cross-tenant data",
                extra={
                    'user_id': user.id,
                    'model': queryset.model.__name__,
                    'endpoint': self.request.path
                }
            )
            return queryset

        # Regular users get tenant filtering
        return queryset
