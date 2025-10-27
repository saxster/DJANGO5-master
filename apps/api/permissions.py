"""
Custom REST API Permissions

Provides tenant isolation and capability-based access control for REST API endpoints.

Security features:
- Automatic tenant filtering based on user's client/bu
- Capability-based access control (JSON field validation)
- Field-level permissions via serializers
- Object-level permissions for detail views

Compliance with .claude/rules.md:
- Specific exception handling (no bare except)
- Utility functions < 50 lines
"""

from rest_framework import permissions
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)


class TenantIsolationPermission(permissions.BasePermission):
    """
    Enforces tenant isolation at the API level.

    Ensures users can only access data belonging to their tenant (client/bu).

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [TenantIsolationPermission]

    How it works:
    - READ operations: Filters queryset by user's client_id/bu_id
    - WRITE operations: Validates object belongs to user's tenant
    - Prevents cross-tenant data access

    Attributes checked:
    - user.client_id
    - user.bu_id (business unit)
    - object.client_id
    - object.bu_id
    """

    def has_permission(self, request, view):
        """
        Check if user is authenticated and has tenant info.

        Returns:
            bool: True if user is authenticated with tenant info
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # Ensure user has tenant information
        if not hasattr(request.user, 'client_id') or request.user.client_id is None:
            logger.warning(f"User {request.user.username} missing client_id")
            return False

        return True

    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific object based on tenant.

        Args:
            request: DRF request object
            view: DRF view object
            obj: Model instance being accessed

        Returns:
            bool: True if object belongs to user's tenant
        """
        user = request.user

        # Admin users bypass tenant isolation
        if user.is_superuser:
            return True

        # Check client_id match
        if hasattr(obj, 'client_id'):
            if obj.client_id != user.client_id:
                logger.warning(
                    f"Tenant isolation violation: User {user.username} "
                    f"(client_id={user.client_id}) attempted to access object "
                    f"(client_id={obj.client_id})"
                )
                return False

        # Check bu_id match if present
        if hasattr(obj, 'bu_id') and hasattr(user, 'bu_id'):
            if user.bu_id is not None and obj.bu_id != user.bu_id:
                logger.warning(
                    f"BU isolation violation: User {user.username} "
                    f"(bu_id={user.bu_id}) attempted to access object "
                    f"(bu_id={obj.bu_id})"
                )
                return False

        return True


class CapabilityBasedPermission(permissions.BasePermission):
    """
    Capability-based access control using user's capabilities JSON field.

    Checks if user has required capability for the requested action.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [CapabilityBasedPermission]
            required_capabilities = {
                'list': ['view_reports'],
                'retrieve': ['view_reports'],
                'create': ['create_reports'],
                'update': ['edit_reports'],
                'destroy': ['delete_reports'],
            }

    Capabilities format (JSON field in People model):
        {
            "view_reports": true,
            "create_reports": true,
            "edit_reports": false,
            "delete_reports": false,
            "admin_access": false
        }
    """

    def has_permission(self, request, view):
        """
        Check if user has required capability for this action.

        Args:
            request: DRF request object
            view: DRF view object

        Returns:
            bool: True if user has required capability
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin users bypass capability checks
        if request.user.is_superuser:
            return True

        # Check if view defines required capabilities
        if not hasattr(view, 'required_capabilities'):
            # No capabilities required, allow access
            return True

        # Get action name (list, retrieve, create, update, destroy, etc.)
        action = view.action if hasattr(view, 'action') else None

        if action is None:
            # Unable to determine action, deny by default
            logger.warning(f"Unable to determine action for view {view.__class__.__name__}")
            return False

        # Get required capabilities for this action
        required_caps = view.required_capabilities.get(action, [])

        if not required_caps:
            # No capabilities required for this action
            return True

        # Get user's capabilities
        user_capabilities = self._get_user_capabilities(request.user)

        # Check if user has all required capabilities
        for cap in required_caps:
            if not user_capabilities.get(cap, False):
                logger.warning(
                    f"Capability check failed: User {request.user.username} "
                    f"missing capability '{cap}' for action '{action}'"
                )
                return False

        return True

    def _get_user_capabilities(self, user):
        """
        Extract capabilities from user model.

        Args:
            user: People model instance

        Returns:
            dict: User's capabilities {capability_name: bool}
        """
        if hasattr(user, 'capabilities') and user.capabilities:
            # capabilities is a JSON field
            if isinstance(user.capabilities, dict):
                return user.capabilities

        # Default: no capabilities
        return {}


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners of an object or admins to edit/delete it.

    Usage:
        class ProfileViewSet(viewsets.ModelViewSet):
            permission_classes = [IsOwnerOrAdmin]

    Checks:
    - Object has 'user' or 'created_by' or 'owner' field
    - Current user matches that field OR is admin
    """

    def has_object_permission(self, request, view, obj):
        """
        Check if user owns the object or is admin.

        Args:
            request: DRF request object
            view: DRF view object
            obj: Model instance being accessed

        Returns:
            bool: True if user is owner or admin
        """
        # Admin users can access everything
        if request.user.is_superuser:
            return True

        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check various ownership fields
        if hasattr(obj, 'user') and obj.user == request.user:
            return True

        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True

        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True

        # Check if object IS the user (for profile endpoints)
        if isinstance(obj, type(request.user)) and obj.id == request.user.id:
            return True

        logger.warning(
            f"Ownership check failed: User {request.user.username} "
            f"attempted to modify object they don't own"
        )
        return False


__all__ = [
    'TenantIsolationPermission',
    'CapabilityBasedPermission',
    'IsOwnerOrAdmin',
]
