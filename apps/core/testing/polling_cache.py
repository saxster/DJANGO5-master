"""Cache-specific polling utilities."""

from typing import Any, Optional

from django.core.cache import cache

from .polling_core import poll_until


def wait_for_cache(
    cache_key: str,
    timeout: float = 5.0,
    interval: float = 0.1,
    expected_value: Optional[Any] = None
) -> Any:
    """
    Wait for a cache key to exist (and optionally match a value).

    Args:
        cache_key: Django cache key to monitor
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        expected_value: If provided, cache value must equal this (optional)

    Returns:
        The cache value when key is set

    Raises:
        ConditionTimeoutError: If cache key not set within timeout

    Example:
        # Wait for cache key to be set
        value = wait_for_cache('processing:complete', timeout=10)

        # Wait for cache key with specific value
        value = wait_for_cache(
            'counter:value',
            expected_value=42,
            timeout=5
        )
    """
    def condition():
        value = cache.get(cache_key)
        if expected_value is None:
            return value is not None
        return value == expected_value

    poll_until(
        condition=condition,
        timeout=timeout,
        interval=interval,
        error_message=(
            f"Cache key '{cache_key}' not set" +
            (f" to {expected_value}" if expected_value else "")
        )
    )

    return cache.get(cache_key)
