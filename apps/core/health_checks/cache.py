"""
Cache health checks: Redis connectivity and Select2 cache validation.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
from typing import Dict, Any
from django.core.cache import cache, caches
from django.utils import timezone
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_redis_connectivity',
    'check_default_cache',
    'check_select2_cache',
]


@timeout_check(timeout_seconds=5)
def check_redis_connectivity() -> Dict[str, Any]:
    """
    Direct Redis connectivity check using redis client.

    Returns:
        Health check result with Redis connection status.
    """
    start_time = time.time()

    try:
        import redis
        from django.conf import settings

        cache_config = settings.CACHES.get("default", {})
        location = cache_config.get("LOCATION", "redis://127.0.0.1:6379/1")

        redis_client = redis.from_url(location, decode_responses=True)

        ping_result = redis_client.ping()

        if not ping_result:
            return format_check_result(
                status="error",
                message="Redis ping failed",
                duration_ms=(time.time() - start_time) * 1000,
            )

        info = redis_client.info("server")

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="Redis connection successful",
            details={
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
            },
            duration_ms=duration,
        )

    except redis.ConnectionError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Redis connection error: {e}",
            extra={"error_type": "ConnectionError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Redis connection failed: {str(e)}",
            details={"error_type": "ConnectionError"},
            duration_ms=duration,
        )

    except redis.TimeoutError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Redis timeout: {e}",
            extra={"error_type": "TimeoutError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Redis timeout: {str(e)}",
            details={"error_type": "TimeoutError"},
            duration_ms=duration,
        )

    except redis.RedisError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Redis error: {e}",
            extra={"error_type": "RedisError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Redis error: {str(e)}",
            details={"error_type": "RedisError"},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_default_cache() -> Dict[str, Any]:
    """
    Check default Django cache backend functionality.

    Returns:
        Health check result with cache read/write status.
    """
    start_time = time.time()

    try:
        test_key = f"health_check_{int(time.time())}"
        test_value = {"test": True, "timestamp": timezone.now().isoformat()}

        cache.set(test_key, test_value, timeout=10)
        retrieved_value = cache.get(test_key)

        if retrieved_value != test_value:
            return format_check_result(
                status="error",
                message="Cache read/write verification failed",
                details={"backend": cache.__class__.__name__},
                duration_ms=(time.time() - start_time) * 1000,
            )

        cache.delete(test_key)

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="Default cache operational",
            details={
                "backend": cache.__class__.__name__,
                "read_write_test": "passed",
            },
            duration_ms=duration,
        )

    except ConnectionError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Cache connection error: {e}",
            extra={"error_type": "ConnectionError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Cache connection failed: {str(e)}",
            details={"backend": cache.__class__.__name__},
            duration_ms=duration,
        )

    except TimeoutError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Cache timeout: {e}",
            extra={"error_type": "TimeoutError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Cache timeout: {str(e)}",
            details={"backend": cache.__class__.__name__},
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_select2_cache() -> Dict[str, Any]:
    """
    Check Select2 materialized view cache functionality.

    Returns:
        Health check result with Select2 cache status.
    """
    start_time = time.time()

    try:
        select2_cache = caches["select2"]

        test_key = f"select2_health_check_{int(time.time())}"
        test_value = {"model": "test", "data": [1, 2, 3]}

        select2_cache.set(test_key, test_value, timeout=10)
        retrieved_value = select2_cache.get(test_key)

        if retrieved_value != test_value:
            return format_check_result(
                status="degraded",
                message="Select2 cache read/write verification failed",
                details={
                    "backend": select2_cache.__class__.__name__,
                    "note": "Select2 cache degraded, using fallback",
                },
                duration_ms=(time.time() - start_time) * 1000,
            )

        select2_cache.delete(test_key)

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="Select2 cache operational",
            details={
                "backend": select2_cache.__class__.__name__,
                "read_write_test": "passed",
            },
            duration_ms=duration,
        )

    except KeyError as e:
        logger.warning("Select2 cache not configured")
        return format_check_result(
            status="degraded",
            message="Select2 cache not configured",
            details={"note": "Select2 cache not available, using fallback queries"},
            duration_ms=(time.time() - start_time) * 1000,
        )

    except (ConnectionError, TimeoutError) as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Select2 cache error: {e}",
            extra={"error_type": type(e).__name__, "duration_ms": duration},
        )
        return format_check_result(
            status="degraded",
            message=f"Select2 cache unavailable: {str(e)}",
            details={"error_type": type(e).__name__},
            duration_ms=duration,
        )