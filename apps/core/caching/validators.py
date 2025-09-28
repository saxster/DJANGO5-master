"""
Cache validation utilities.
Extracted from security.py for .claude/rules.md compliance (< 200 lines).
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

__all__ = ['validate_cache_operation', 'is_safe_cache_pattern']


class CacheSecurityError(Exception):
    """Raised when cache security validation fails"""
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
            from apps.core.caching.security import validate_cache_key
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
            extra={'operation': operation, 'cache_key': cache_key[:50] if cache_key else None}
        )
        return {'valid': False, 'operation': operation, 'error': str(e)}
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"Unexpected cache validation error: {e}")
        return {'valid': False, 'operation': operation, 'error': f'Validation error: {str(e)}'}


def is_safe_cache_pattern(pattern: str) -> bool:
    """
    Validate if cache invalidation pattern is safe.

    Args:
        pattern: Wildcard pattern for cache clearing

    Returns:
        True if pattern is safe

    Raises:
        CacheSecurityError: If pattern is dangerous
    """
    try:
        if pattern == '*' or pattern == '*:*':
            raise CacheSecurityError("Wildcard-only patterns are too broad and dangerous")

        if pattern.count('*') > 3:
            raise CacheSecurityError("Pattern contains too many wildcards")

        safe_prefixes = ['tenant:', 'user:', 'model:', 'query:', 'dropdown:', 'dashboard:']

        has_safe_prefix = any(pattern.startswith(prefix) for prefix in safe_prefixes)

        if not has_safe_prefix:
            raise CacheSecurityError(f"Pattern must start with safe prefix: {safe_prefixes}")

        return True

    except CacheSecurityError:
        raise
    except (AttributeError, TypeError) as e:
        raise CacheSecurityError(f"Invalid pattern format: {e}")