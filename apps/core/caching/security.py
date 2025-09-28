"""
Cache security utilities to prevent cache poisoning and abuse.

Implements validation, sanitization, and rate limiting for cache operations.
Complies with .claude/rules.md - security-first, specific exceptions.
"""

import re
import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

__all__ = [
    'validate_cache_key',
    'sanitize_cache_key',
    'CacheRateLimiter',
    'validate_cache_entry_size',
    'CacheSecurityError',
]


DANGEROUS_PATTERNS = [
    '..',
    '/',
    '\\',
    ';',
    '|',
    '&',
    '$',
    '`',
    '\n',
    '\r',
    '\x00'
]

SAFE_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9:_\-\.]+$')

MAX_CACHE_ENTRY_SIZE = 1024 * 1024
MAX_CACHE_KEY_LENGTH = 250


class CacheSecurityError(Exception):
    """Raised when cache security validation fails"""
    pass


def validate_cache_key(cache_key: str) -> bool:
    """
    Validate cache key for security.

    Args:
        cache_key: Cache key to validate

    Returns:
        True if valid

    Raises:
        CacheSecurityError: If validation fails
    """
    try:
        if not cache_key or not isinstance(cache_key, str):
            raise CacheSecurityError("Cache key must be non-empty string")

        if len(cache_key) > MAX_CACHE_KEY_LENGTH:
            raise CacheSecurityError(
                f"Cache key exceeds maximum length of {MAX_CACHE_KEY_LENGTH}"
            )

        for dangerous in DANGEROUS_PATTERNS:
            if dangerous in cache_key:
                raise CacheSecurityError(
                    f"Cache key contains dangerous pattern: {dangerous}"
                )

        if not SAFE_KEY_PATTERN.match(cache_key):
            raise CacheSecurityError(
                "Cache key contains unsafe characters"
            )

        return True

    except CacheSecurityError:
        raise
    except (AttributeError, TypeError) as e:
        raise CacheSecurityError(f"Invalid cache key format: {e}")


def sanitize_cache_key(unsafe_key: str) -> str:
    """Sanitize user-provided cache key input"""
    try:
        if not isinstance(unsafe_key, str):
            unsafe_key = str(unsafe_key)
        for dangerous in DANGEROUS_PATTERNS:
            unsafe_key = unsafe_key.replace(dangerous, '_')
        safe_key = re.sub(r'[^a-zA-Z0-9:_\-\.]', '_', unsafe_key)
        return safe_key[:MAX_CACHE_KEY_LENGTH]
    except (AttributeError, TypeError) as e:
        logger.error(f"Error sanitizing cache key: {e}")
        return 'sanitized_key_error'


def validate_cache_entry_size(data: Any) -> bool:
    """
    Validate cache entry size to prevent memory exhaustion.

    Args:
        data: Data to cache

    Returns:
        True if size is acceptable

    Raises:
        CacheSecurityError: If data too large
    """
    try:
        import sys

        size = sys.getsizeof(data)

        if size > MAX_CACHE_ENTRY_SIZE:
            raise CacheSecurityError(
                f"Cache entry size ({size} bytes) exceeds maximum ({MAX_CACHE_ENTRY_SIZE} bytes)"
            )

        return True

    except CacheSecurityError:
        raise
    except (AttributeError, TypeError) as e:
        logger.warning(f"Could not validate cache entry size: {e}")
        return True


def is_safe_cache_pattern(pattern: str) -> bool:
    """
    Validate cache pattern for safe operations.

    Args:
        pattern: Cache pattern to validate

    Returns:
        True if pattern is safe
    """
    try:
        safe_patterns = [
            'tenant:',
            'user:',
            'dashboard:',
            'dropdown:',
            'form:',
            'report:',
            'attendance:',
            'asset:',
        ]

        return any(pattern.startswith(prefix) for prefix in safe_patterns)

    except (AttributeError, TypeError):
        return False


class CacheRateLimiter:
    """Rate limiting for cache operations to prevent DoS"""

    RATE_LIMIT_KEY_PREFIX = 'cache:ratelimit'
    DEFAULT_LIMIT = 1000
    DEFAULT_WINDOW = 3600

    @classmethod
    def check_rate_limit(cls, identifier: str, limit: int = DEFAULT_LIMIT, window: int = DEFAULT_WINDOW) -> Dict[str, Any]:
        """Check if identifier is within rate limit"""
        try:
            rate_key = f"{cls.RATE_LIMIT_KEY_PREFIX}:{identifier}"
            current_count = cache.get(rate_key, 0)

            if current_count >= limit:
                logger.warning(f"Cache rate limit exceeded for {identifier}", extra={'identifier': identifier, 'current_count': current_count, 'limit': limit})
                return {'allowed': False, 'current_count': current_count, 'limit': limit, 'reset_at': (timezone.now() + timedelta(seconds=window)).isoformat()}

            cache.set(rate_key, current_count + 1, timeout=window)
            return {'allowed': True, 'current_count': current_count + 1, 'limit': limit, 'remaining': limit - current_count - 1}

        except (ConnectionError, AttributeError) as e:
            logger.error(f"Rate limit check failed: {e}")
            return {'allowed': True, 'error': str(e)}