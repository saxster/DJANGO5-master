"""
View Mixins for Code Duplication Elimination

This module provides reusable mixins for Django views to eliminate
permission checking and other patterns duplicated across view implementations.

Following .claude/rules.md:
- Rule #7: Classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
"""

import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import View
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.core.validators import validate_tenant_access, validate_user_permissions

logger = logging.getLogger(__name__)


class TenantPermissionMixin:
    """
    Mixin providing tenant-aware permission checking.

    Consolidates tenant permission patterns used across tenant-aware views.
    """

    def check_tenant_access(self, user, tenant, action: str = "access") -> None:
        """
        Check user has access to specified tenant.

        Args:
            user: User to check
            tenant: Tenant to validate access for
            action: Action being performed

        Raises:
            PermissionDenied: If user doesn't have access
        """
        try:
            validate_tenant_access(user, tenant, action)
        except (ValidationError, PermissionDenied) as e:
            logger.warning(f"Tenant access denied for user {user.id}: {e}")
            raise PermissionDenied(str(e))

    def get_user_tenant(self, user):
        """
        Get user's associated tenant.

        Args:
            user: User to get tenant for

        Returns:
            Tenant object or None
        """
        if hasattr(user, 'bu') and user.bu:
            if hasattr(user.bu, 'tenant'):
                return user.bu.tenant
            elif hasattr(user.bu, 'client'):
                return getattr(user.bu.client, 'tenant', None)
        return None

    def filter_by_tenant(self, queryset, user):
        """
        Filter queryset by user's tenant.

        Args:
            queryset: Queryset to filter
            user: User for tenant filtering

        Returns:
            Filtered queryset
        """
        tenant = self.get_user_tenant(user)
        if tenant:
            if hasattr(queryset.model, 'tenant'):
                return queryset.filter(tenant=tenant)
            elif hasattr(queryset.model, 'client'):
                return queryset.filter(client__tenant=tenant)
        return queryset


class PermissionCheckMixin:
    """
    Mixin providing standardized permission checking.

    Consolidates permission checking patterns used across views.
    """

    required_permissions = []  # Override in subclasses

    def check_permissions(self, user, obj=None) -> None:
        """
        Check user has required permissions.

        Args:
            user: User to check permissions for
            obj: Optional object for object-level permissions

        Raises:
            PermissionDenied: If user doesn't have required permissions
        """
        if not self.required_permissions:
            return

        try:
            validate_user_permissions(user, self.required_permissions, obj)
        except (ValidationError, PermissionDenied) as e:
            logger.warning(f"Permission denied for user {user.id}: {e}")
            raise PermissionDenied(str(e))

    def has_object_permission(self, user, obj) -> bool:
        """
        Check if user has permission for specific object.

        Args:
            user: User to check
            obj: Object to check permissions for

        Returns:
            bool: True if user has permission
        """
        try:
            self.check_permissions(user, obj)
            return True
        except PermissionDenied:
            return False


class AuthenticationMixin:
    """
    Mixin providing enhanced authentication checking.

    Consolidates authentication patterns used across views.
    """

    def check_authentication(self, user) -> None:
        """
        Check user authentication with enhanced validation.

        Args:
            user: User to check

        Raises:
            PermissionDenied: If user is not properly authenticated
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required")

        # Additional authentication checks
        if not user.is_active:
            raise PermissionDenied("Account is disabled")

        if hasattr(user, 'enable') and not user.enable:
            raise PermissionDenied("Account access is disabled")

    def get_authenticated_user(self, request):
        """
        Get authenticated user with validation.

        Args:
            request: HTTP request

        Returns:
            Authenticated user

        Raises:
            PermissionDenied: If authentication fails
        """
        user = request.user
        self.check_authentication(user)
        return user


class JSONResponseMixin:
    """
    Mixin providing standardized JSON responses.

    Consolidates JSON response patterns used across API views.
    """

    def json_response(
        self,
        data: Any = None,
        message: str = "",
        success: bool = True,
        status_code: int = 200,
        extra_data: Optional[Dict] = None
    ) -> JsonResponse:
        """
        Create standardized JSON response.

        Args:
            data: Response data
            message: Response message
            success: Success status
            status_code: HTTP status code
            extra_data: Additional data to include

        Returns:
            JsonResponse
        """
        response_data = {
            'success': success,
            'message': message,
            'data': data
        }

        if extra_data:
            response_data.update(extra_data)

        return JsonResponse(response_data, status=status_code)

    def error_response(
        self,
        message: str,
        errors: Optional[Dict] = None,
        status_code: int = 400
    ) -> JsonResponse:
        """
        Create standardized error response.

        Args:
            message: Error message
            errors: Detailed errors
            status_code: HTTP status code

        Returns:
            JsonResponse
        """
        response_data = {
            'success': False,
            'message': message,
            'errors': errors or {}
        }

        return JsonResponse(response_data, status=status_code)


class EnhancedViewMixin(
    TenantPermissionMixin,
    PermissionCheckMixin,
    AuthenticationMixin,
    JSONResponseMixin
):
    """
    Combined view mixin providing all enhanced view capabilities.

    Consolidates all view patterns into a single mixin that can be
    used as a base for view classes throughout the codebase.
    """

    def dispatch(self, request, *args, **kwargs):
        """
        Enhanced dispatch with unified permission checking.
        """
        try:
            # Check authentication
            user = self.get_authenticated_user(request)

            # Check basic permissions
            self.check_permissions(user)

            # Check tenant access if needed
            if hasattr(self, 'get_tenant_for_request'):
                tenant = self.get_tenant_for_request(request)
                if tenant:
                    self.check_tenant_access(user, tenant)

            return super().dispatch(request, *args, **kwargs)

        except PermissionDenied as e:
            if request.accepts('application/json'):
                return self.error_response(str(e), status_code=403)
            else:
                return HttpResponseForbidden(str(e))
        except Exception as e:
            logger.error(f"Unexpected error in view dispatch: {e}", exc_info=True)
            if request.accepts('application/json'):
                return self.error_response("Internal server error", status_code=500)
            else:
                raise


class EnhancedLoginRequiredView(EnhancedViewMixin, LoginRequiredMixin, View):
    """
    Enhanced Django class-based view with login requirement.

    Consolidates common patterns for login-required views.
    """
    pass


class EnhancedAPIView(EnhancedViewMixin, APIView):
    """
    Enhanced Django REST Framework API view.

    Consolidates common patterns for API views with DRF integration.
    """

    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        """
        Enhanced exception handling for API views.
        """
        if isinstance(exc, PermissionDenied):
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'error_code': 'PERMISSION_DENIED'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        elif isinstance(exc, ValidationError):
            return Response(
                {
                    'success': False,
                    'message': 'Validation error',
                    'errors': exc.message_dict if hasattr(exc, 'message_dict') else str(exc),
                    'error_code': 'VALIDATION_ERROR'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Enhanced response finalization with logging.
        """
        response = super().finalize_response(request, response, *args, **kwargs)

        # Log API access
        logger.info(
            f"API access: {request.method} {request.path}",
            extra={
                'user_id': getattr(request.user, 'id', None),
                'status_code': response.status_code,
                'view_name': self.__class__.__name__
            }
        )

        return response


class PaginationMixin:
    """
    Mixin providing standardized pagination.

    Consolidates pagination patterns used across list views.
    """

    default_page_size = 20
    max_page_size = 100

    def get_page_size(self, request) -> int:
        """
        Get page size from request parameters.

        Args:
            request: HTTP request

        Returns:
            int: Page size
        """
        try:
            page_size = int(request.GET.get('page_size', self.default_page_size))
            return min(page_size, self.max_page_size)
        except (ValueError, TypeError):
            return self.default_page_size

    def get_page_number(self, request) -> int:
        """
        Get page number from request parameters.

        Args:
            request: HTTP request

        Returns:
            int: Page number
        """
        try:
            return max(1, int(request.GET.get('page', 1)))
        except (ValueError, TypeError):
            return 1

    def paginate_queryset(self, queryset, request):
        """
        Apply pagination to queryset.

        Args:
            queryset: Queryset to paginate
            request: HTTP request

        Returns:
            tuple: (paginated_queryset, pagination_data)
        """
        page_size = self.get_page_size(request)
        page_number = self.get_page_number(request)

        start = (page_number - 1) * page_size
        end = start + page_size

        total_count = queryset.count()
        paginated_queryset = queryset[start:end]

        pagination_data = {
            'page': page_number,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size,
            'has_next': end < total_count,
            'has_previous': page_number > 1
        }

        return paginated_queryset, pagination_data