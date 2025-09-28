"""
Channels health checks: WebSocket/ASGI connectivity via Redis Channels.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
import asyncio
from typing import Dict, Any
from django.utils import timezone
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_channel_layer',
]


@timeout_check(timeout_seconds=5)
def check_channel_layer() -> Dict[str, Any]:
    """
    Check Django Channels layer connectivity and functionality.

    Returns:
        Health check result with channel layer status.
    """
    start_time = time.time()

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()

        if channel_layer is None:
            return format_check_result(
                status="degraded",
                message="Channel layer not configured",
                details={"note": "WebSocket features unavailable"},
                duration_ms=(time.time() - start_time) * 1000,
            )

        test_channel = f"health_check_{int(time.time())}"
        test_message = {
            "type": "test.message",
            "data": "health_check",
            "timestamp": timezone.now().isoformat(),
        }

        try:
            async_to_sync(channel_layer.send)(test_channel, test_message)
        except (ConnectionError, TimeoutError) as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Channel layer send failed: {e}",
                extra={"error_type": type(e).__name__, "duration_ms": duration},
            )
            return format_check_result(
                status="error",
                message=f"Channel layer send failed: {str(e)}",
                details={"error_type": type(e).__name__},
                duration_ms=duration,
            )

        try:
            received_message = async_to_sync(channel_layer.receive)(test_channel)
        except (ConnectionError, TimeoutError) as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Channel layer receive failed: {e}",
                extra={"error_type": type(e).__name__, "duration_ms": duration},
            )
            return format_check_result(
                status="error",
                message=f"Channel layer receive failed: {str(e)}",
                details={"error_type": type(e).__name__},
                duration_ms=duration,
            )

        if received_message.get("data") != "health_check":
            return format_check_result(
                status="error",
                message="Channel layer message verification failed",
                details={"expected": "health_check", "received": received_message.get("data")},
                duration_ms=(time.time() - start_time) * 1000,
            )

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status="healthy",
            message="Channel layer operational",
            details={
                "backend": channel_layer.__class__.__name__,
                "send_receive_test": "passed",
            },
            duration_ms=duration,
        )

    except ImportError as e:
        duration = (time.time() - start_time) * 1000
        logger.warning("Channels not installed")
        return format_check_result(
            status="degraded",
            message="Channels not installed",
            details={"note": "WebSocket features unavailable"},
            duration_ms=duration,
        )

    except RuntimeError as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Channel layer runtime error: {e}",
            extra={"error_type": "RuntimeError", "duration_ms": duration},
        )
        return format_check_result(
            status="error",
            message=f"Channel layer error: {str(e)}",
            details={"error_type": "RuntimeError"},
            duration_ms=duration,
        )