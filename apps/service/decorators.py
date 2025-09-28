"""
GraphQL Authentication and Authorization Decorators

Provides centralized authentication and authorization decorators for GraphQL resolvers
to prevent unauthorized access to sensitive data and operations.

Security Features:
- JWT token validation via graphql_jwt
- Multi-tenant authorization
- Business unit access control
- Role-based permissions
- Audit logging for security events

Usage:
    from apps.service.decorators import require_authentication, require_tenant_access

    @staticmethod
    @require_authentication
    def resolve_get_data(self, info, **kwargs):
        # Resolver implementation
        pass

    @staticmethod
    @require_tenant_access
    def resolve_get_tenant_data(self, info, tenant_id, **kwargs):
        # Resolver implementation with tenant validation
        pass
"""

import logging
import json
from functools import wraps
from typing import Callable, Any, Optional, List
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from django.core.exceptions import PermissionDenied


security_logger = logging.getLogger('security')
graphql_auth_logger = logging.getLogger('graphql_security')


def require_authentication(resolver: Callable) -> Callable:
    """
    Decorator to require authentication for GraphQL resolvers.

    This decorator ensures that only authenticated users can access the resolver.
    It uses the @login_required decorator from graphql_jwt to validate JWT tokens.

    Args:
        resolver: The GraphQL resolver function to protect

    Returns:
        Wrapped resolver that requires authentication

    Raises:
        GraphQLError: If user is not authenticated

    Example:
        @staticmethod
        @require_authentication
        def resolve_get_people(self, info, **kwargs):
            # Only authenticated users can access this
            return People.objects.all()
    """
    @wraps(resolver)
    @login_required
    def wrapper(*args, **kwargs):
        info = args[1] if len(args) > 1 else kwargs.get('info')

        if not info or not hasattr(info, 'context'):
            graphql_auth_logger.error("No context found in GraphQL info object")
            raise GraphQLError("Authentication required - invalid request context")

        request = info.context

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            graphql_auth_logger.warning(
                f"Unauthenticated access attempt to {resolver.__name__}",
                extra={
                    'resolver': resolver.__name__,
                    'ip': request.META.get('REMOTE_ADDR', 'unknown'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown')
                }
            )
            raise GraphQLError("Authentication required")

        graphql_auth_logger.debug(
            f"Authenticated access to {resolver.__name__}",
            extra={
                'resolver': resolver.__name__,
                'user_id': request.user.id,
                'username': request.user.loginid if hasattr(request.user, 'loginid') else str(request.user)
            }
        )

        return resolver(*args, **kwargs)

    return wrapper


def require_tenant_access(resolver: Callable) -> Callable:
    """
    Decorator to require tenant-level authorization for GraphQL resolvers.

    This decorator validates that the authenticated user has access to the
    requested tenant/client data. It prevents cross-tenant data access.

    Args:
        resolver: The GraphQL resolver function to protect

    Returns:
        Wrapped resolver with tenant authorization

    Raises:
        GraphQLError: If user doesn't have access to the tenant

    Example:
        @staticmethod
        @require_tenant_access
        def resolve_get_data(self, info, client_id, **kwargs):
            # User's client_id will be validated
            return Data.objects.filter(client_id=client_id)
    """
    @wraps(resolver)
    @login_required
    def wrapper(*args, **kwargs):
        info = args[1] if len(args) > 1 else kwargs.get('info')

        if not info or not hasattr(info, 'context'):
            raise GraphQLError("Authorization required - invalid request context")

        request = info.context
        user = request.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        requested_client_id = kwargs.get('clientid') or kwargs.get('client_id')
        requested_bu_id = kwargs.get('buid') or kwargs.get('bu_id')

        if requested_client_id and user.client_id != requested_client_id:
            graphql_auth_logger.warning(
                f"Cross-tenant access attempt by user {user.id}",
                extra={
                    'user_id': user.id,
                    'user_client_id': user.client_id,
                    'requested_client_id': requested_client_id,
                    'resolver': resolver.__name__,
                    'ip': request.META.get('REMOTE_ADDR', 'unknown')
                }
            )
            raise GraphQLError("Access denied - insufficient tenant permissions")

        if requested_bu_id and user.bu_id != requested_bu_id:
            from apps.peoples.models import Pgbelonging

            has_bu_access = Pgbelonging.objects.filter(
                peopleid=user.id,
                buid=requested_bu_id
            ).exists()

            if not has_bu_access:
                graphql_auth_logger.warning(
                    f"Unauthorized business unit access attempt by user {user.id}",
                    extra={
                        'user_id': user.id,
                        'user_bu_id': user.bu_id,
                        'requested_bu_id': requested_bu_id,
                        'resolver': resolver.__name__
                    }
                )
                raise GraphQLError("Access denied - insufficient business unit permissions")

        return resolver(*args, **kwargs)

    return wrapper


def require_permission(permission: str) -> Callable:
    """
    Decorator to require specific permissions for GraphQL resolvers.

    This decorator checks if the user has the specified permission before
    allowing access to the resolver.

    Args:
        permission: The permission string to check (e.g., 'can_view_reports')

    Returns:
        Decorator function

    Raises:
        GraphQLError: If user doesn't have the required permission

    Example:
        @staticmethod
        @require_permission('can_approve_work_permits')
        def resolve_approve_work_permit(self, info, **kwargs):
            # Only users with approval permission can access this
            pass
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        @login_required
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            if not info or not hasattr(info, 'context'):
                raise GraphQLError("Authorization required")

            user = info.context.user

            if not user.is_authenticated:
                raise GraphQLError("Authentication required")

            if user.isadmin:
                return resolver(*args, **kwargs)

            user_capabilities = user.capabilities if hasattr(user, 'capabilities') else {}

            if not isinstance(user_capabilities, dict):
                try:
                    import json
                    user_capabilities = json.loads(user_capabilities) if user_capabilities else {}
                except (json.JSONDecodeError, TypeError):
                    user_capabilities = {}

            if not user_capabilities.get(permission, False):
                graphql_auth_logger.warning(
                    f"Permission denied for user {user.id} - {permission}",
                    extra={
                        'user_id': user.id,
                        'required_permission': permission,
                        'resolver': resolver.__name__
                    }
                )
                raise GraphQLError(f"Permission denied - {permission} required")

            return resolver(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(resolver: Callable) -> Callable:
    """
    Decorator to require admin privileges for GraphQL resolvers.

    This decorator ensures only admin users can access the resolver.

    Args:
        resolver: The GraphQL resolver function to protect

    Returns:
        Wrapped resolver requiring admin access

    Raises:
        GraphQLError: If user is not an admin

    Example:
        @staticmethod
        @require_admin
        def resolve_delete_all_data(self, info, **kwargs):
            # Only admins can access this dangerous operation
            pass
    """
    @wraps(resolver)
    @login_required
    def wrapper(*args, **kwargs):
        info = args[1] if len(args) > 1 else kwargs.get('info')

        if not info or not hasattr(info, 'context'):
            raise GraphQLError("Authorization required")

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.isadmin:
            graphql_auth_logger.warning(
                f"Admin access denied for user {user.id}",
                extra={
                    'user_id': user.id,
                    'resolver': resolver.__name__,
                    'ip': info.context.META.get('REMOTE_ADDR', 'unknown')
                }
            )
            raise GraphQLError("Admin privileges required")

        return resolver(*args, **kwargs)

    return wrapper


def audit_resolver(operation_name: Optional[str] = None) -> Callable:
    """
    Decorator to audit GraphQL resolver access for security monitoring.

    This decorator logs all accesses to the resolver for security auditing,
    including user identity, timestamp, and request details.

    Args:
        operation_name: Optional name for the operation (defaults to resolver name)

    Returns:
        Decorator function

    Example:
        @staticmethod
        @audit_resolver(operation_name='sensitive_data_access')
        @require_authentication
        def resolve_get_sensitive_data(self, info, **kwargs):
            pass
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            op_name = operation_name or resolver.__name__

            if info and hasattr(info, 'context'):
                request = info.context
                user = getattr(request, 'user', None)

                security_logger.info(
                    f"GraphQL resolver access: {op_name}",
                    extra={
                        'operation': op_name,
                        'resolver': resolver.__name__,
                        'user_id': user.id if user and user.is_authenticated else None,
                        'username': user.loginid if user and hasattr(user, 'loginid') else 'anonymous',
                        'ip': request.META.get('REMOTE_ADDR', 'unknown'),
                        'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
                        'arguments': str(kwargs)
                    }
                )

            return resolver(*args, **kwargs)

        return wrapper

    return decorator


class TenantAuthorizationMixin:
    """
    Mixin class for GraphQL query classes to provide tenant authorization utilities.

    This mixin provides helper methods for validating tenant access and filtering
    queries based on user permissions.

    Usage:
        class MyQueries(TenantAuthorizationMixin, graphene.ObjectType):
            @staticmethod
            def resolve_get_data(self, info, **kwargs):
                user = self.get_authenticated_user(info)
                return self.filter_by_tenant(Data.objects.all(), user)
    """

    @staticmethod
    def get_authenticated_user(info):
        """
        Get the authenticated user from the GraphQL info context.

        Args:
            info: GraphQL info object

        Returns:
            Authenticated user object

        Raises:
            GraphQLError: If user is not authenticated
        """
        if not info or not hasattr(info, 'context'):
            raise GraphQLError("Invalid request context")

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        return user

    @staticmethod
    def validate_tenant_access(user, client_id: int, bu_id: Optional[int] = None):
        """
        Validate that the user has access to the specified tenant.

        Args:
            user: The authenticated user
            client_id: The requested client ID
            bu_id: Optional business unit ID

        Raises:
            GraphQLError: If user doesn't have access
        """
        if user.client_id != client_id:
            raise GraphQLError("Access denied - insufficient tenant permissions")

        if bu_id is not None:
            from apps.peoples.models import Pgbelonging

            has_bu_access = (
                user.bu_id == bu_id or
                Pgbelonging.objects.filter(peopleid=user.id, buid=bu_id).exists()
            )

            if not has_bu_access:
                raise GraphQLError("Access denied - insufficient business unit permissions")

    @staticmethod
    def filter_by_tenant(queryset, user):
        """
        Filter a queryset to only include data accessible by the user.

        Args:
            queryset: Django queryset to filter
            user: The authenticated user

        Returns:
            Filtered queryset
        """
        return queryset.filter(client_id=user.client_id)

    @staticmethod
    def filter_by_business_unit(queryset, user, bu_field='bu_id'):
        """
        Filter a queryset by business units accessible to the user.

        Args:
            queryset: Django queryset to filter
            user: The authenticated user
            bu_field: Name of the business unit field in the model

        Returns:
            Filtered queryset
        """
        from apps.peoples.models import Pgbelonging

        accessible_bus = Pgbelonging.objects.filter(
            peopleid=user.id
        ).values_list('buid', flat=True)

        filter_kwargs = {f"{bu_field}__in": list(accessible_bus) + [user.bu_id]}
        return queryset.filter(**filter_kwargs)


def require_model_permission(permission: str) -> Callable:
    """
    Decorator to require Django model permissions for GraphQL resolvers.

    Integrates with Django's built-in permission system (auth.Permission) to
    provide model-level authorization using standard permission strings.

    Args:
        permission: Django permission string (e.g., 'peoples.view_people', 'activity.change_jobneed')

    Returns:
        Decorator function

    Raises:
        GraphQLError: If user doesn't have the required permission

    Example:
        @staticmethod
        @require_model_permission('peoples.view_people')
        def resolve_get_all_people(self, info):
            return People.objects.all()
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        @login_required
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            if not info or not hasattr(info, 'context'):
                raise GraphQLError("Authorization required - invalid request context")

            user = info.context.user

            if not user.is_authenticated:
                raise GraphQLError("Authentication required")

            if user.isadmin or user.is_superuser:
                return resolver(*args, **kwargs)

            if not user.has_perm(permission):
                graphql_auth_logger.warning(
                    f"Django permission denied: {permission}",
                    extra={
                        'user_id': user.id,
                        'username': getattr(user, 'loginid', str(user)),
                        'required_permission': permission,
                        'resolver': resolver.__name__
                    }
                )
                raise GraphQLError(f"Permission denied - {permission} required")

            return resolver(*args, **kwargs)

        return wrapper

    return decorator


def require_object_permission(permission_checker: Callable[[Any, Any], bool]) -> Callable:
    """
    Decorator to require object-level permissions for GraphQL resolvers.

    Provides fine-grained authorization by checking permissions on individual
    objects returned by the resolver using a custom permission checker function.

    Args:
        permission_checker: Callable that takes (user, obj) and returns bool

    Returns:
        Decorator function

    Raises:
        GraphQLError: If user doesn't have permission for the object

    Example:
        def can_view_ticket(user, ticket):
            return (
                user.isadmin or
                ticket.created_by_id == user.id or
                ticket.assigned_to_id == user.id
            )

        @staticmethod
        @require_object_permission(can_view_ticket)
        def resolve_ticket(self, info, ticket_id):
            return Ticket.objects.get(id=ticket_id)
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        @login_required
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            if not info or not hasattr(info, 'context'):
                raise GraphQLError("Authorization required - invalid request context")

            user = info.context.user

            if not user.is_authenticated:
                raise GraphQLError("Authentication required")

            result = resolver(*args, **kwargs)

            if result is None:
                return None

            if isinstance(result, list):
                filtered_results = []
                for obj in result:
                    if permission_checker(user, obj):
                        filtered_results.append(obj)
                    else:
                        graphql_auth_logger.debug(
                            f"Object-level permission denied",
                            extra={
                                'user_id': user.id,
                                'object_type': type(obj).__name__,
                                'object_id': getattr(obj, 'id', None),
                                'resolver': resolver.__name__
                            }
                        )
                return filtered_results

            if not permission_checker(user, result):
                graphql_auth_logger.warning(
                    f"Object-level permission denied for single object",
                    extra={
                        'user_id': user.id,
                        'username': getattr(user, 'loginid', str(user)),
                        'object_type': type(result).__name__,
                        'object_id': getattr(result, 'id', None),
                        'resolver': resolver.__name__
                    }
                )
                raise GraphQLError("Access denied - insufficient permissions for this resource")

            return result

        return wrapper

    return decorator


def require_any_permission(*permissions: str) -> Callable:
    """
    Decorator to require ANY of the specified permissions (OR logic).

    Args:
        *permissions: Variable number of permission strings

    Returns:
        Decorator function

    Raises:
        GraphQLError: If user doesn't have any of the required permissions

    Example:
        @require_any_permission('can_view_reports', 'can_view_analytics', 'peoples.view_people')
        def resolve_dashboard_data(self, info):
            pass
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        @login_required
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            if not info or not hasattr(info, 'context'):
                raise GraphQLError("Authorization required")

            user = info.context.user

            if not user.is_authenticated:
                raise GraphQLError("Authentication required")

            if user.isadmin:
                return resolver(*args, **kwargs)

            user_capabilities = user.capabilities if hasattr(user, 'capabilities') else {}

            if isinstance(user_capabilities, str):
                try:
                    user_capabilities = json.loads(user_capabilities)
                except (json.JSONDecodeError, TypeError):
                    user_capabilities = {}

            for permission in permissions:
                if '.' in permission:
                    if user.has_perm(permission):
                        return resolver(*args, **kwargs)
                else:
                    if user_capabilities.get(permission, False):
                        return resolver(*args, **kwargs)

            graphql_auth_logger.warning(
                f"Permission denied - none of required permissions met",
                extra={
                    'user_id': user.id,
                    'required_permissions': list(permissions),
                    'resolver': resolver.__name__
                }
            )

            raise GraphQLError(f"Permission denied - requires one of: {', '.join(permissions)}")

        return wrapper

    return decorator