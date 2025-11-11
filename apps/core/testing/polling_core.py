"""
Core polling function for condition-based waiting utility.

This minimal module provides the fundamental polling logic used by all
higher-level waiting utilities.
"""

import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ConditionTimeoutError(TimeoutError):
    """Raised when a condition is not met within the timeout period."""
    pass


def poll_until(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: Optional[str] = None
) -> None:
    """
    Poll a condition function until it returns True or timeout is reached.

    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between checks in seconds (default: 0.1)
        error_message: Custom error message on timeout (optional)

    Raises:
        ConditionTimeoutError: If condition not met within timeout

    Example:
        # Wait for cache key to be set
        poll_until(
            lambda: cache.get('processing_complete') is not None,
            timeout=10,
            interval=0.5,
            error_message="Processing did not complete within 10 seconds"
        )
    """
    start_time = time.time()
    last_exception = None

    while time.time() - start_time < timeout:
        try:
            if condition():
                logger.debug(
                    f"Condition met after {time.time() - start_time:.2f}s"
                )
                return
        except (AttributeError, KeyError, ValueError, TypeError) as e:
            # Capture condition evaluation errors but continue polling
            last_exception = e
            logger.debug(
                f"Condition check failed (will retry): {e}"
            )

        time.sleep(interval)

    # Timeout reached
    elapsed = time.time() - start_time
    msg = error_message or f"Condition not met within {timeout}s"

    if last_exception:
        msg += f" (last error: {last_exception})"

    logger.error(f"Condition poll timeout: {msg} (elapsed: {elapsed:.2f}s)")
    raise ConditionTimeoutError(msg)
