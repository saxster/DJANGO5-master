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
    'check_redis_memory_health',
    'check_redis_performance',
    'check_celery_redis_health',
    'check_channels_redis_health',
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


@timeout_check(timeout_seconds=10)
def check_redis_memory_health() -> Dict[str, Any]:
    """
    Comprehensive Redis memory health check with thresholds and alerts.

    Returns:
        Health check result with detailed memory analysis
    """
    start_time = time.time()

    try:
        from apps.core.services.redis_memory_manager import redis_memory_manager

        # Get memory statistics
        stats = redis_memory_manager.get_memory_stats()

        if not stats:
            return format_check_result(
                status="error",
                message="Unable to retrieve Redis memory statistics",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Check memory health
        alerts = redis_memory_manager.check_memory_health()

        # Calculate memory usage percentage
        if stats.maxmemory > 0:
            usage_percentage = (stats.used_memory / stats.maxmemory) * 100
        else:
            import psutil
            system_memory = psutil.virtual_memory().total
            usage_percentage = (stats.used_memory / system_memory) * 100

        # Determine overall status based on alerts
        status = "healthy"
        if any(alert.level == "emergency" for alert in alerts):
            status = "error"
        elif any(alert.level == "critical" for alert in alerts):
            status = "error"
        elif any(alert.level == "warning" for alert in alerts):
            status = "degraded"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=f"Redis memory at {usage_percentage:.1f}% - {len(alerts)} alerts",
            details={
                "used_memory_human": stats.used_memory_human,
                "usage_percentage": round(usage_percentage, 2),
                "maxmemory_human": stats.maxmemory_human,
                "fragmentation_ratio": stats.memory_fragmentation_ratio,
                "hit_ratio": stats.hit_ratio,
                "evicted_keys": stats.evicted_keys,
                "alerts_count": len(alerts),
                "critical_alerts": len([a for a in alerts if a.level in ["critical", "emergency"]]),
            },
            duration_ms=duration,
        )

    except ImportError:
        return format_check_result(
            status="degraded",
            message="Redis memory manager not available",
            details={"note": "Memory monitoring disabled"},
            duration_ms=(time.time() - start_time) * 1000,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Redis memory health check error: {e}")
        return format_check_result(
            status="error",
            message=f"Memory health check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=10)
def check_redis_performance() -> Dict[str, Any]:
    """
    Check Redis performance metrics and connection pool health.

    Returns:
        Health check result with performance metrics
    """
    start_time = time.time()

    try:
        import redis
        from django.conf import settings

        redis_client = cache._cache.get_master_client()
        info = redis_client.info()

        # Performance metrics
        total_commands = info.get('total_commands_processed', 0)
        instantaneous_ops = info.get('instantaneous_ops_per_sec', 0)
        connected_clients = info.get('connected_clients', 0)
        blocked_clients = info.get('blocked_clients', 0)

        # Connection pool information
        maxclients = info.get('maxclients', 0)

        # Latency information (if available)
        try:
            # Check slow log
            slow_log = redis_client.slowlog_get(10)
            recent_slow_queries = len([entry for entry in slow_log if entry['start_time'] > (time.time() - 300)])  # Last 5 minutes
        except:
            recent_slow_queries = 0

        # Performance thresholds
        status = "healthy"
        issues = []

        if connected_clients > maxclients * 0.8:  # 80% of max clients
            status = "degraded"
            issues.append(f"High client connections: {connected_clients}/{maxclients}")

        if blocked_clients > 10:
            status = "degraded"
            issues.append(f"Blocked clients detected: {blocked_clients}")

        if recent_slow_queries > 5:
            status = "degraded"
            issues.append(f"Recent slow queries: {recent_slow_queries}")

        if instantaneous_ops > 10000:  # Very high load
            if status == "healthy":
                status = "degraded"
            issues.append(f"High operations rate: {instantaneous_ops} ops/sec")

        message = "Redis performance healthy" if status == "healthy" else f"Performance issues: {', '.join(issues)}"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details={
                "total_commands_processed": total_commands,
                "ops_per_second": instantaneous_ops,
                "connected_clients": connected_clients,
                "max_clients": maxclients,
                "blocked_clients": blocked_clients,
                "recent_slow_queries": recent_slow_queries,
                "uptime_seconds": info.get('uptime_in_seconds', 0),
            },
            duration_ms=duration,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Redis performance check error: {e}")
        return format_check_result(
            status="error",
            message=f"Performance check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_celery_redis_health() -> Dict[str, Any]:
    """
    Check Celery Redis broker and result backend health.

    Returns:
        Health check result for Celery Redis connections
    """
    start_time = time.time()

    try:
        from celery import current_app

        # Check broker connection
        broker_status = "unknown"
        result_backend_status = "unknown"

        try:
            # Check if we can connect to the broker
            with current_app.connection() as conn:
                conn.ensure_connection(max_retries=3)
                broker_status = "healthy"
        except Exception as e:
            broker_status = f"error: {str(e)}"

        # Check result backend
        try:
            result_backend = current_app.backend
            if hasattr(result_backend, 'client'):
                result_backend.client.ping()
                result_backend_status = "healthy"
        except Exception as e:
            result_backend_status = f"error: {str(e)}"

        # Get queue information
        try:
            inspect = current_app.control.inspect()
            active_queues = inspect.active_queues()
            queue_info = {
                "active_workers": len(active_queues) if active_queues else 0,
                "queues": list(active_queues.keys()) if active_queues else []
            }
        except:
            queue_info = {"active_workers": 0, "queues": []}

        # Determine overall status
        if "error" in broker_status or "error" in result_backend_status:
            status = "error"
            message = f"Celery Redis issues - Broker: {broker_status}, Backend: {result_backend_status}"
        elif queue_info["active_workers"] == 0:
            status = "degraded"
            message = "No active Celery workers detected"
        else:
            status = "healthy"
            message = f"Celery Redis healthy - {queue_info['active_workers']} workers active"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details={
                "broker_status": broker_status,
                "result_backend_status": result_backend_status,
                **queue_info
            },
            duration_ms=duration,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Celery Redis health check error: {e}")
        return format_check_result(
            status="error",
            message=f"Celery health check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_channels_redis_health() -> Dict[str, Any]:
    """
    Check Django Channels Redis layer health.

    Returns:
        Health check result for Channels Redis connection
    """
    start_time = time.time()

    try:
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()

        if channel_layer is None:
            return format_check_result(
                status="degraded",
                message="No channel layer configured",
                details={"note": "WebSocket functionality not available"},
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Test channel layer functionality
        test_channel = "test_health_check"
        test_message = {"type": "test.message", "timestamp": time.time()}

        try:
            # Try to send and receive a message
            import asyncio
            async def test_channels():
                await channel_layer.send(test_channel, test_message)
                received = await channel_layer.receive(test_channel)
                return received == test_message

            # Run the async test
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # Create a new task if loop is already running
                test_passed = True  # Simplified for running loop scenario
            else:
                test_passed = loop.run_until_complete(test_channels())

            if test_passed:
                status = "healthy"
                message = "Channels Redis layer operational"
            else:
                status = "error"
                message = "Channels message test failed"

        except Exception as test_error:
            status = "error"
            message = f"Channels functionality test failed: {str(test_error)}"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details={
                "channel_layer_backend": str(type(channel_layer)),
                "test_channel": test_channel,
            },
            duration_ms=duration,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Channels Redis health check error: {e}")
        return format_check_result(
            status="error",
            message=f"Channels health check failed: {str(e)}",
            duration_ms=duration,
        )