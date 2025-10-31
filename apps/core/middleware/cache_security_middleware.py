"""
Cache Security Middleware to prevent cache poisoning attacks.

Validates cache operations and enforces security policies.
Complies with .claude/rules.md - security-first approach.
"""

import logging
from typing import Optional, Any, Dict

from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.caching.security import (
    CacheRateLimiter,
    validate_cache_key,
    CacheSecurityError
)

logger = logging.getLogger(__name__)

__all__ = ['CacheSecurityMiddleware']


class CacheSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for cache operations.

    Prevents:
    - Cache poisoning via malicious keys
    - DoS attacks via excessive cache writes
    - Cache key injection attacks
    """

    CACHE_ADMIN_PATHS = [
        '/admin/cache/',
        '/cache/health/'
    ]

    def process_request(self, request: HttpRequest):
        """Validate cache-related requests"""
        try:
            is_cache_admin_request = any(request.path.startswith(path) for path in self.CACHE_ADMIN_PATHS)
            if is_cache_admin_request:
                return self._validate_cache_admin_request(request)
            self._track_cache_request(request)
            return None
        except PermissionDenied:
            raise
        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Cache security middleware error: {e}")
            return None

    def _validate_cache_admin_request(self, request: HttpRequest):
        """Validate administrative cache operations"""
        try:
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required for cache management")
            if not request.user.is_staff:
                raise PermissionDenied("Staff privileges required for cache management")

            if request.method == 'POST':
                rate_limit = CacheRateLimiter.check_rate_limit(identifier=f"cache_admin:{request.user.id}", limit=100, window=3600)
                if not rate_limit['allowed']:
                    logger.warning(f"Cache admin rate limit exceeded for user {request.user.id}", extra={'user_id': request.user.id})
                    return JsonResponse({'error': 'Rate limit exceeded for cache operations', 'retry_after': rate_limit.get('reset_at')}, status=429)
            return None
        except PermissionDenied:
            raise
        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Cache admin validation error: {e}")
            return None

    def _track_cache_request(self, request: HttpRequest):
        """Track cache-related requests for monitoring"""
        try:
            cache_operation = request.GET.get('cache_operation')
            if cache_operation in ['invalidate', 'clear', 'delete']:
                if not request.user.is_authenticated or not request.user.is_staff:
                    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', 'unknown')
                    logger.warning(f"Unauthorized cache operation attempted: {cache_operation}", extra={'path': request.path, 'ip': ip})
        except (AttributeError, KeyError):
            pass


def validate_cache_operation(
    operation: str,
    cache_key: Optional[str] = None,
    cache_data: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Validate cache operation for security.

    Args:
        operation: Operation type ('get', 'set', 'delete')
        cache_key: Cache key (for validation)
        cache_data: Data to cache (for size validation)

    Returns:
        Validation results

    Raises:
        CacheSecurityError: If validation fails
    """
    try:
        if cache_key:
            validate_cache_key(cache_key)

        if operation == 'set' and cache_data is not None:
            from apps.core.caching.security import validate_cache_entry_size
            validate_cache_entry_size(cache_data)

        return {
            'valid': True,
            'operation': operation,
            'message': 'Cache operation validated successfully'
        }

    except CacheSecurityError as e:
        logger.error(
            f"Cache operation validation failed: {e}",
            extra={
                'operation': operation,
                'cache_key': cache_key[:50] if cache_key else None
            }
        )

        return {
            'valid': False,
            'operation': operation,
            'error': str(e)
        }
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"Unexpected cache validation error: {e}")
        return {
            'valid': False,
            'operation': operation,
            'error': f'Validation error: {str(e)}'
        }


def is_safe_cache_pattern(pattern: str) -> bool:
    """
    Validate if cache invalidation pattern is safe.

    Args:
        pattern: Wildcard pattern for cache clearing

    Returns:
        True if pattern is safe to use

    Raises:
        CacheSecurityError: If pattern is dangerous
    """
    try:
        if pattern == '*' or pattern == '*:*':
            raise CacheSecurityError(
                "Wildcard-only patterns are too broad and dangerous"
            )

        if pattern.count('*') > 3:
            raise CacheSecurityError(
                "Pattern contains too many wildcards"
            )

        safe_prefixes = ['tenant:', 'user:', 'model:', 'query:', 'dropdown:', 'dashboard:']

        has_safe_prefix = any(pattern.startswith(prefix) for prefix in safe_prefixes)

        if not has_safe_prefix:
            raise CacheSecurityError(
                f"Pattern must start with safe prefix: {safe_prefixes}"
            )

        return True

    except CacheSecurityError:
        raise
    except (AttributeError, TypeError) as e:
        raise CacheSecurityError(f"Invalid pattern format: {e}")
