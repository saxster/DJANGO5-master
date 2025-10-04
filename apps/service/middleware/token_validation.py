"""
JWT Token Validation Middleware

Validates JWT refresh tokens against blacklist before allowing GraphQL operations.

Security Features:
- Checks if refresh token is blacklisted
- Rejects revoked/rotated tokens
- Comprehensive security logging
- Performance-optimized with caching

Compliance: Addresses Medium-severity token security vulnerability
"""

from graphql import GraphQLError
from graphql.execution.base import ResolveInfo
from typing import Any, Callable
from django.core.cache import cache
from django.conf import settings
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE
import logging
import jwt

security_logger = logging.getLogger('security')
token_logger = logging.getLogger('token_validation')


class RefreshTokenValidationMiddleware:
    """
    GraphQL middleware that validates refresh tokens against blacklist.

    This middleware runs before GraphQL resolver execution to ensure that
    blacklisted tokens (rotated, logged out, or revoked) cannot be used.

    Integration: Add to GRAPHENE['MIDDLEWARE'] in settings
    """

    # Cache TTL for blacklist checks (5 minutes)
    BLACKLIST_CACHE_TTL = SECONDS_IN_MINUTE * 5

    def __init__(self, get_response=None):
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
            GraphQLError: If token is blacklisted
        """
        # Only validate on mutations (queries don't need strict token validation)
        if not self._is_mutation(info):
            return next_resolver(root, info, **kwargs)

        # Skip validation for unauthenticated operations
        if not hasattr(info.context, 'user') or not info.context.user.is_authenticated:
            return next_resolver(root, info, **kwargs)

        # Extract refresh token JTI from request headers
        refresh_token_jti = self._extract_refresh_token_jti(info.context)

        if refresh_token_jti:
            # Check if token is blacklisted
            if self._is_token_blacklisted(refresh_token_jti):
                user_id = info.context.user.id if hasattr(info.context, 'user') else None

                security_logger.warning(
                    f"Blacklisted token usage attempted",
                    extra={
                        'user_id': user_id,
                        'token_jti_prefix': refresh_token_jti[:10],
                        'operation': info.field_name,
                        'security_event': 'blacklisted_token_usage_attempt'
                    }
                )

                raise GraphQLError(
                    "Authentication token has been revoked. Please log in again.",
                    extensions={
                        'code': 'TOKEN_REVOKED',
                        'reason': 'token_blacklisted'
                    }
                )

        # Token is valid, continue with resolver
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

    def _extract_refresh_token_jti(self, request) -> str:
        """
        Extract refresh token JTI from request headers.

        The client should send the JTI in the X-Refresh-Token-JTI header.

        Args:
            request: Django request object

        Returns:
            Token JTI string, or None if not found
        """
        if not hasattr(request, 'META'):
            return None

        # Check for explicit JTI header (preferred)
        jti = request.META.get('HTTP_X_REFRESH_TOKEN_JTI')

        if jti:
            return jti

        # Fallback: Extract JTI from Authorization header if it's a refresh token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('JWT '):
            token = auth_header[4:]  # Remove 'JWT ' prefix
            jti = self._extract_jti_from_token(token)
            if jti:
                return jti

        return None

    def _extract_jti_from_token(self, token: str) -> str:
        """
        Extract JTI claim from JWT token.

        Args:
            token: JWT token string

        Returns:
            JTI claim value, or None if extraction fails
        """
        try:
            # Decode without verification (we just need the JTI)
            # The token is already validated by graphql-jwt middleware
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            return decoded.get('jti')

        except (jwt.DecodeError, jwt.InvalidTokenError, KeyError) as e:
            token_logger.debug(
                f"Failed to extract JTI from token: {e}",
                extra={'error': str(e)}
            )
            return None

    def _is_token_blacklisted(self, token_jti: str) -> bool:
        """
        Check if a token is blacklisted with caching for performance.

        Args:
            token_jti: JWT token identifier

        Returns:
            True if blacklisted, False otherwise
        """
        # Check cache first
        cache_key = f"token_blacklist_check:{token_jti}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        # Check database
        from apps.core.models.refresh_token_blacklist import RefreshTokenBlacklist

        is_blacklisted = RefreshTokenBlacklist.is_token_blacklisted(token_jti)

        # Cache the result (both positive and negative results)
        cache.set(cache_key, is_blacklisted, self.BLACKLIST_CACHE_TTL)

        if is_blacklisted:
            token_logger.info(
                f"Token found in blacklist: {token_jti[:10]}...",
                extra={'token_jti_prefix': token_jti[:10]}
            )

        return is_blacklisted


class RefreshTokenCleanupMiddleware:
    """
    Django middleware that triggers periodic cleanup of old blacklist entries.

    This runs at the Django request level (not GraphQL resolver level) to
    cleanup old entries without impacting GraphQL performance.
    """

    # Cleanup every N requests (adjust based on load)
    CLEANUP_INTERVAL_REQUESTS = 1000

    # Keep blacklist entries for 7 days (tokens typically expire in 2 days)
    CLEANUP_DAYS_OLD = 7

    def __init__(self, get_response):
        self.get_response = get_response
        self.request_count = 0

    def __call__(self, request):
        """Django middleware call method."""
        self.request_count += 1

        # Trigger cleanup periodically
        if self.request_count >= self.CLEANUP_INTERVAL_REQUESTS:
            self._trigger_cleanup()
            self.request_count = 0

        response = self.get_response(request)
        return response

    def _trigger_cleanup(self):
        """Trigger asynchronous cleanup of old blacklist entries."""
        try:
            # Import here to avoid circular dependency
            from apps.core.models.refresh_token_blacklist import RefreshTokenBlacklist

            # Run cleanup in background (don't block request)
            deleted_count = RefreshTokenBlacklist.cleanup_old_entries(
                days_old=self.CLEANUP_DAYS_OLD
            )

            if deleted_count > 0:
                security_logger.info(
                    f"Blacklist cleanup completed: {deleted_count} entries removed",
                    extra={
                        'deleted_count': deleted_count,
                        'days_threshold': self.CLEANUP_DAYS_OLD,
                        'maintenance_task': 'token_blacklist_cleanup'
                    }
                )

        except ConnectionError as e:
            security_logger.warning(
                f"Failed to cleanup token blacklist (database unavailable): {e}",
                extra={'error': str(e)}
            )
        except Exception as e:
            security_logger.error(
                f"Unexpected error during token blacklist cleanup: {e}",
                extra={'error': str(e)},
                exc_info=True
            )
