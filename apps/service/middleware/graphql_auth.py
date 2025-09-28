"""
GraphQL Authentication Middleware

Provides middleware-level authentication validation for all GraphQL operations
to prevent unauthorized access before resolver execution.

This middleware works in conjunction with resolver-level decorators to provide
defense-in-depth security for GraphQL endpoints.

Security Features:
- JWT token validation
- Introspection query allow-listing (for schema discovery)
- Authentication requirement for all non-introspection queries
- Security event logging
- Rate limiting integration
- Correlation ID tracking

Configuration:
    Add to GRAPHENE['MIDDLEWARE'] in settings:

    GRAPHENE = {
        'MIDDLEWARE': [
            'graphql_jwt.middleware.JSONWebTokenMiddleware',
            'apps.service.middleware.GraphQLAuthenticationMiddleware',
        ]
    }
"""

import logging
import time
from typing import Any, Callable, Optional
from graphql import GraphQLError
from graphql.execution.base import ResolveInfo
from django.conf import settings
from django.core.cache import cache


security_logger = logging.getLogger('security')
graphql_auth_logger = logging.getLogger('graphql_security')


class GraphQLAuthenticationMiddleware:
    """
    Middleware that enforces authentication for all GraphQL operations.

    This middleware runs before resolver execution to validate that users
    are authenticated for all non-introspection queries.

    Introspection queries (used for schema discovery) are allowed without
    authentication to support GraphQL client tooling.
    """

    INTROSPECTION_QUERIES = {
        '__schema',
        '__type',
        '__typename',
    }

    ALLOWED_UNAUTHENTICATED_OPERATIONS = {
        'LoginUser',
        'token_auth',
        'verifyclient',
        'security_info',
    }

    def __init__(self, get_response=None):
        """
        Initialize the middleware.

        Args:
            get_response: The next middleware or resolver in the chain
        """
        self.get_response = get_response

    def resolve(self, next_resolver: Callable, root: Any, info: ResolveInfo, **kwargs) -> Any:
        """
        Middleware resolution method called for each GraphQL field.

        Args:
            next_resolver: The next resolver in the chain
            root: The parent object being resolved
            info: GraphQL ResolveInfo object containing request context
            **kwargs: Additional arguments passed to the resolver

        Returns:
            Result from the next resolver

        Raises:
            GraphQLError: If authentication is required but not provided
        """
        operation_name = info.field_name
        correlation_id = self._get_correlation_id(info)

        if self._is_introspection_query(info):
            graphql_auth_logger.debug(
                f"Allowing introspection query: {operation_name}",
                extra={'operation': operation_name, 'correlation_id': correlation_id}
            )
            return next_resolver(root, info, **kwargs)

        if operation_name in self.ALLOWED_UNAUTHENTICATED_OPERATIONS:
            graphql_auth_logger.debug(
                f"Allowing unauthenticated operation: {operation_name}",
                extra={'operation': operation_name, 'correlation_id': correlation_id}
            )
            return next_resolver(root, info, **kwargs)

        if not self._is_authenticated(info):
            client_ip = self._get_client_ip(info)

            graphql_auth_logger.warning(
                f"Unauthenticated GraphQL access attempt blocked",
                extra={
                    'operation': operation_name,
                    'field_name': info.field_name,
                    'parent_type': info.parent_type.name if info.parent_type else None,
                    'ip': client_ip,
                    'correlation_id': correlation_id,
                    'user_agent': info.context.META.get('HTTP_USER_AGENT', 'unknown')
                }
            )

            self._record_auth_failure(client_ip, operation_name)

            raise GraphQLError(
                "Authentication required. Please provide a valid JWT token.",
                extensions={
                    'code': 'UNAUTHENTICATED',
                    'correlation_id': correlation_id
                }
            )

        user = info.context.user
        graphql_auth_logger.debug(
            f"Authenticated GraphQL access: {operation_name}",
            extra={
                'operation': operation_name,
                'user_id': user.id,
                'username': getattr(user, 'loginid', str(user)),
                'correlation_id': correlation_id
            }
        )

        if self._should_rate_limit(info, user):
            raise GraphQLError(
                "Rate limit exceeded. Please try again later.",
                extensions={
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'correlation_id': correlation_id
                }
            )

        start_time = time.time()
        result = next_resolver(root, info, **kwargs)
        execution_time = (time.time() - start_time) * 1000

        graphql_auth_logger.debug(
            f"GraphQL resolver executed: {operation_name}",
            extra={
                'operation': operation_name,
                'execution_time_ms': execution_time,
                'user_id': user.id,
                'correlation_id': correlation_id
            }
        )

        return result

    def _is_authenticated(self, info: ResolveInfo) -> bool:
        """
        Check if the request is authenticated.

        Args:
            info: GraphQL ResolveInfo object

        Returns:
            bool: True if authenticated, False otherwise
        """
        if not hasattr(info, 'context') or not info.context:
            return False

        request = info.context

        if not hasattr(request, 'user'):
            return False

        return request.user.is_authenticated

    def _is_introspection_query(self, info: ResolveInfo) -> bool:
        """
        Check if the current query is an introspection query.

        Introspection queries are used by GraphQL clients to discover the schema
        and should be allowed without authentication.

        Args:
            info: GraphQL ResolveInfo object

        Returns:
            bool: True if introspection query, False otherwise
        """
        field_name = info.field_name

        if field_name in self.INTROSPECTION_QUERIES:
            return True

        parent_type_name = info.parent_type.name if info.parent_type else ''
        if parent_type_name.startswith('__'):
            return True

        return False

    def _get_client_ip(self, info: ResolveInfo) -> str:
        """
        Extract client IP address from request.

        Args:
            info: GraphQL ResolveInfo object

        Returns:
            str: Client IP address or 'unknown'
        """
        if not hasattr(info, 'context'):
            return 'unknown'

        request = info.context
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()

        return request.META.get('REMOTE_ADDR', 'unknown')

    def _get_correlation_id(self, info: ResolveInfo) -> Optional[str]:
        """
        Get or generate correlation ID for request tracking.

        Args:
            info: GraphQL ResolveInfo object

        Returns:
            str: Correlation ID or None
        """
        if not hasattr(info, 'context'):
            return None

        request = info.context

        if hasattr(request, 'correlation_id'):
            return request.correlation_id

        return request.META.get('HTTP_X_CORRELATION_ID')

    def _record_auth_failure(self, client_ip: str, operation: str):
        """
        Record authentication failure for rate limiting and monitoring.

        Args:
            client_ip: Client IP address
            operation: Operation name that failed
        """
        cache_key = f"graphql_auth_failure:{client_ip}"
        failures = cache.get(cache_key, 0)
        cache.set(cache_key, failures + 1, timeout=300)

        if failures >= 5:
            security_logger.warning(
                f"Multiple GraphQL authentication failures from {client_ip}",
                extra={
                    'ip': client_ip,
                    'failure_count': failures + 1,
                    'operation': operation
                }
            )

    def _should_rate_limit(self, info: ResolveInfo, user) -> bool:
        """
        Check if the request should be rate limited.

        Args:
            info: GraphQL ResolveInfo object
            user: Authenticated user

        Returns:
            bool: True if should rate limit, False otherwise
        """
        if not getattr(settings, 'ENABLE_GRAPHQL_RATE_LIMITING', True):
            return False

        rate_limit_key = f"graphql_rate_limit:user:{user.id}"
        max_requests = getattr(settings, 'GRAPHQL_RATE_LIMIT_MAX', 100)
        window_seconds = getattr(settings, 'GRAPHQL_RATE_LIMIT_WINDOW', 60)

        current_requests = cache.get(rate_limit_key, 0)

        if current_requests >= max_requests:
            return True

        cache.set(rate_limit_key, current_requests + 1, timeout=window_seconds)
        return False


class GraphQLTenantValidationMiddleware:
    """
    Middleware that validates tenant isolation for GraphQL operations.

    This middleware ensures that users can only access data from their own tenant,
    preventing cross-tenant data leaks.
    """

    def __init__(self, get_response=None):
        """
        Initialize the middleware.

        Args:
            get_response: The next middleware or resolver in the chain
        """
        self.get_response = get_response

    def resolve(self, next_resolver: Callable, root: Any, info: ResolveInfo, **kwargs) -> Any:
        """
        Middleware resolution method that validates tenant access.

        Args:
            next_resolver: The next resolver in the chain
            root: The parent object being resolved
            info: GraphQL ResolveInfo object containing request context
            **kwargs: Additional arguments passed to the resolver

        Returns:
            Result from the next resolver

        Raises:
            GraphQLError: If tenant validation fails
        """
        if not hasattr(info, 'context') or not info.context:
            return next_resolver(root, info, **kwargs)

        user = getattr(info.context, 'user', None)

        if not user or not user.is_authenticated:
            return next_resolver(root, info, **kwargs)

        requested_client_id = kwargs.get('clientid') or kwargs.get('client_id')
        requested_bu_id = kwargs.get('buid') or kwargs.get('bu_id')

        if requested_client_id and user.client_id != requested_client_id:
            graphql_auth_logger.warning(
                f"Cross-tenant access attempt by user {user.id}",
                extra={
                    'user_id': user.id,
                    'user_client_id': user.client_id,
                    'requested_client_id': requested_client_id,
                    'operation': info.field_name
                }
            )

            raise GraphQLError(
                "Access denied - insufficient tenant permissions",
                extensions={'code': 'TENANT_ACCESS_DENIED'}
            )

        if requested_bu_id and user.bu_id != requested_bu_id:
            from apps.peoples.models import Pgbelonging

            has_bu_access = Pgbelonging.objects.filter(
                peopleid=user.id,
                buid=requested_bu_id
            ).exists()

            if not has_bu_access:
                graphql_auth_logger.warning(
                    f"Unauthorized business unit access by user {user.id}",
                    extra={
                        'user_id': user.id,
                        'user_bu_id': user.bu_id,
                        'requested_bu_id': requested_bu_id,
                        'operation': info.field_name
                    }
                )

                raise GraphQLError(
                    "Access denied - insufficient business unit permissions",
                    extensions={'code': 'BU_ACCESS_DENIED'}
                )

        return next_resolver(root, info, **kwargs)


class GraphQLMutationChainingProtectionMiddleware:
    """
    Middleware to protect against mutation chaining attacks and enforce
    transaction-level rate limiting.

    Features:
    - Detects and limits chained mutations in single requests
    - Per-transaction mutation counting
    - Protection against batch mutation abuse
    - Transaction-level rate limiting
    - Comprehensive security logging

    Security Compliance:
    - Addresses CVSS 7.2 (High) - GraphQL Authorization Gaps
    - Prevents mutation chaining bypass attacks
    - Enforces operation-level rate limits
    """

    MAX_MUTATIONS_PER_REQUEST = 5
    MUTATION_CHAIN_CACHE_TTL = 60

    def __init__(self, get_response=None):
        """Initialize the middleware."""
        self.get_response = get_response

    def resolve(self, next_resolver: Callable, root: Any, info: ResolveInfo, **kwargs) -> Any:
        """
        Middleware resolution method for mutation chaining protection.

        Args:
            next_resolver: The next resolver in the chain
            root: The parent object being resolved
            info: GraphQL ResolveInfo object
            **kwargs: Additional arguments

        Returns:
            Result from next resolver

        Raises:
            GraphQLError: If mutation chaining limits exceeded
        """
        if not self._is_mutation(info):
            return next_resolver(root, info, **kwargs)

        user = getattr(info.context, 'user', None)

        if not user or not user.is_authenticated:
            return next_resolver(root, info, **kwargs)

        correlation_id = self._get_correlation_id(info)

        mutation_count = self._increment_mutation_count(user, correlation_id)

        max_mutations = getattr(
            settings,
            'GRAPHQL_MAX_MUTATIONS_PER_REQUEST',
            self.MAX_MUTATIONS_PER_REQUEST
        )

        if mutation_count > max_mutations:
            graphql_auth_logger.warning(
                f"Mutation chaining limit exceeded",
                extra={
                    'user_id': user.id,
                    'mutation_count': mutation_count,
                    'max_mutations': max_mutations,
                    'correlation_id': correlation_id,
                    'operation': info.field_name
                }
            )

            raise GraphQLError(
                f"Mutation chaining limit exceeded. Maximum {max_mutations} mutations per request.",
                extensions={
                    'code': 'MUTATION_CHAIN_LIMIT_EXCEEDED',
                    'mutation_count': mutation_count,
                    'max_allowed': max_mutations,
                    'correlation_id': correlation_id
                }
            )

        graphql_auth_logger.debug(
            f"Mutation chaining check passed: {mutation_count}/{max_mutations}",
            extra={
                'user_id': user.id,
                'mutation_count': mutation_count,
                'max_mutations': max_mutations,
                'correlation_id': correlation_id,
                'operation': info.field_name
            }
        )

        return next_resolver(root, info, **kwargs)

    def _is_mutation(self, info: ResolveInfo) -> bool:
        """Check if the current operation is a mutation."""
        if not hasattr(info, 'parent_type'):
            return False

        parent_type_name = info.parent_type.name if info.parent_type else ''

        return (
            parent_type_name in ['Mutation', 'RootMutation'] or
            'mutation' in parent_type_name.lower()
        )

    def _get_correlation_id(self, info: ResolveInfo) -> Optional[str]:
        """Get or generate correlation ID for request tracking."""
        if not hasattr(info, 'context'):
            return None

        request = info.context

        if hasattr(request, 'correlation_id'):
            return request.correlation_id

        return request.META.get('HTTP_X_CORRELATION_ID')

    def _increment_mutation_count(self, user, correlation_id: str) -> int:
        """
        Increment mutation count for the current request.

        Args:
            user: The authenticated user
            correlation_id: Request correlation ID

        Returns:
            int: Current mutation count for this request
        """
        cache_key = f"graphql_mutation_chain:{user.id}:{correlation_id}"

        current_count = cache.get(cache_key, 0)
        new_count = current_count + 1

        cache.set(cache_key, new_count, timeout=self.MUTATION_CHAIN_CACHE_TTL)

        return new_count


class GraphQLIntrospectionControlMiddleware:
    """
    Middleware to control GraphQL introspection based on environment.

    Features:
    - Disables introspection in production environments
    - Allows introspection in development/testing
    - Configurable via settings
    - Security logging for introspection attempts

    Security Compliance:
    - Addresses CVSS 7.2 (High) - GraphQL Authorization Gaps
    - Prevents schema discovery in production
    - Reduces attack surface by hiding API structure
    """

    INTROSPECTION_FIELDS = {'__schema', '__type', '__typename'}

    def __init__(self, get_response=None):
        """Initialize the middleware."""
        self.get_response = get_response
        self.disable_in_production = getattr(
            settings,
            'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',
            True
        )

    def resolve(self, next_resolver: Callable, root: Any, info: ResolveInfo, **kwargs) -> Any:
        """
        Middleware resolution method for introspection control.

        Args:
            next_resolver: The next resolver in the chain
            root: The parent object
            info: GraphQL ResolveInfo object
            **kwargs: Additional arguments

        Returns:
            Result from next resolver

        Raises:
            GraphQLError: If introspection is disabled and attempted
        """
        if not self._is_introspection_field(info):
            return next_resolver(root, info, **kwargs)

        is_production = not getattr(settings, 'DEBUG', False)

        if is_production and self.disable_in_production:
            user = getattr(info.context, 'user', None)

            graphql_auth_logger.warning(
                "GraphQL introspection attempt blocked in production",
                extra={
                    'user_id': user.id if user and hasattr(user, 'id') else None,
                    'field_name': info.field_name,
                    'ip': info.context.META.get('REMOTE_ADDR', 'unknown') if hasattr(info, 'context') else 'unknown',
                    'correlation_id': self._get_correlation_id(info)
                }
            )

            raise GraphQLError(
                "Introspection queries are disabled in production. Please refer to API documentation.",
                extensions={
                    'code': 'INTROSPECTION_DISABLED',
                    'documentation_url': '/api/docs/'
                }
            )

        graphql_auth_logger.debug(
            f"Introspection query allowed: {info.field_name}",
            extra={
                'field_name': info.field_name,
                'environment': 'development' if settings.DEBUG else 'production'
            }
        )

        return next_resolver(root, info, **kwargs)

    def _is_introspection_field(self, info: ResolveInfo) -> bool:
        """Check if the field is an introspection field."""
        field_name = getattr(info, 'field_name', '')

        if field_name in self.INTROSPECTION_FIELDS:
            return True

        if field_name.startswith('__'):
            return True

        parent_type = getattr(info, 'parent_type', None)
        if parent_type and hasattr(parent_type, 'name'):
            if parent_type.name.startswith('__'):
                return True

        return False

    def _get_correlation_id(self, info: ResolveInfo) -> Optional[str]:
        """Get correlation ID from request context."""
        if not hasattr(info, 'context'):
            return None

        request = info.context

        if hasattr(request, 'correlation_id'):
            return request.correlation_id

        return request.META.get('HTTP_X_CORRELATION_ID')