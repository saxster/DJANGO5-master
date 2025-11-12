"""
Condition-Based Polling Utilities

Replaces blocking time.sleep() in polling scenarios with event-driven checks.

Following .claude/rules.md:
- Rule #14: No blocking time.sleep() in request paths
- Superpowers skill: condition-based-waiting

Usage:
    from apps.core.utils_new.condition_polling import poll_until_condition

    # Replace:
    # while not is_ready():
    #     time.sleep(1)  # ❌ BLOCKING

    # With:
    result = poll_until_condition(
        condition_func=lambda: check_if_ready(),
        timeout_seconds=30,
        check_interval=1
    )
"""

import logging
import time
import hashlib
from typing import Callable, Optional, Any, Dict
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

logger = logging.getLogger(__name__)


class PollingTimeoutError(Exception):
    """Raised when polling times out before condition is met."""
    pass


class ConditionPoller:
    """
    Event-driven condition polling without blocking.

    Stores polling state in cache/database, allowing non-blocking checks.
    Suitable for async operations, Celery tasks, and long-running processes.
    """

    CACHE_PREFIX = 'condition_poll'

    def __init__(
        self,
        poll_id: str,
        condition_func: Callable[[], bool],
        timeout_seconds: int = 30,
        check_interval: int = 1
    ):
        """
        Initialize condition poller.

        Args:
            poll_id: Unique identifier for this polling operation
            condition_func: Function that returns True when condition is met
            timeout_seconds: Maximum time to poll
            check_interval: Minimum time between checks (for rate limiting)
        """
        self.poll_id = poll_id
        self.condition_func = condition_func
        self.timeout_seconds = timeout_seconds
        self.check_interval = check_interval
        self.poll_key = f"{self.CACHE_PREFIX}:{poll_id}"

    def check_condition(self) -> Tuple[bool, Optional[Any]]:
        """
        Check if condition is met (non-blocking).

        Returns:
            Tuple of (condition_met: bool, result: Any)
        """
        # Get polling state from cache
        poll_state = cache.get(self.poll_key) or {
            'started_at': timezone.now().isoformat(),
            'last_check': None,
            'check_count': 0
        }

        # Check if timeout exceeded
        started_at = timezone.fromisoformat(poll_state['started_at'])
        elapsed = (timezone.now() - started_at).total_seconds()

        if elapsed > self.timeout_seconds:
            cache.delete(self.poll_key)
            raise PollingTimeoutError(
                f"Condition polling timed out after {elapsed:.1f}s (timeout: {self.timeout_seconds}s)"
            )

        # Rate limiting: Check if minimum interval elapsed
        if poll_state.get('last_check'):
            last_check = timezone.fromisoformat(poll_state['last_check'])
            since_last = (timezone.now() - last_check).total_seconds()

            if since_last < self.check_interval:
                logger.debug(
                    f"Poll rate limited for {self.poll_id}",
                    extra={'since_last': since_last, 'interval': self.check_interval}
                )
                return False, None

        # Execute condition check
        try:
            result = self.condition_func()

            # Update poll state
            poll_state['last_check'] = timezone.now().isoformat()
            poll_state['check_count'] += 1
            cache.set(self.poll_key, poll_state, timeout=self.timeout_seconds)

            if result:
                # Condition met - clear state
                cache.delete(self.poll_key)
                logger.info(
                    f"Condition met for {self.poll_id}",
                    extra={
                        'checks': poll_state['check_count'],
                        'elapsed': elapsed
                    }
                )
                return True, result

            return False, None

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                f"Condition check failed for {self.poll_id}",
                extra={'error': str(e)},
                exc_info=True
            )
            cache.delete(self.poll_key)
            raise

    def poll_sync(self) -> Any:
        """
        Synchronous polling with blocking (for Celery tasks only).

        NOTE: This uses time.sleep() but ONLY in Celery worker context,
        which is acceptable per .claude/rules.md (not in request paths).
        """
        logger.info(f"Starting synchronous polling for {self.poll_id}")

        while True:
            try:
                condition_met, result = self.check_condition()
                if condition_met:
                    return result

                # Sleep in Celery context is acceptable
                time.sleep(self.check_interval)

            except PollingTimeoutError:
                raise


def poll_until_condition(
    condition_func: Callable[[], bool],
    timeout_seconds: int = 30,
    check_interval: int = 1,
    poll_id: Optional[str] = None,
    blocking: bool = False
) -> Any:
    """
    Poll until condition is met (non-blocking by default).

    Args:
        condition_func: Function that returns True when condition is met
        timeout_seconds: Maximum time to poll
        check_interval: Time between checks
        poll_id: Optional unique identifier (auto-generated if not provided)
        blocking: If True, use synchronous polling (Celery tasks only)

    Returns:
        Result from condition_func when condition is met

    Raises:
        PollingTimeoutError: If timeout exceeded before condition met

    Usage:
        # Non-blocking (for Django views - returns immediately)
        try:
            result = poll_until_condition(
                condition_func=lambda: Job.objects.filter(id=job_id, status='COMPLETED').exists(),
                timeout_seconds=60,
                blocking=False
            )
        except PollingTimeoutError:
            return JsonResponse({'status': 'processing'}, status=202)

        # Blocking (for Celery tasks only)
        result = poll_until_condition(
            condition_func=lambda: external_api_ready(),
            timeout_seconds=300,
            blocking=True  # Only use in Celery worker context
        )
    """
    if poll_id is None:
        poll_id = hashlib.sha256(
            f"{condition_func.__name__}:{time.time()}".encode()
        ).hexdigest()[:16]

    poller = ConditionPoller(
        poll_id=poll_id,
        condition_func=condition_func,
        timeout_seconds=timeout_seconds,
        check_interval=check_interval
    )

    if blocking:
        # Synchronous polling (Celery tasks only)
        return poller.poll_sync()
    else:
        # Non-blocking single check (Django views)
        condition_met, result = poller.check_condition()
        if condition_met:
            return result
        raise PollingTimeoutError(f"Condition not yet met (poll_id: {poll_id})")


def poll_with_celery_retry(task_instance, condition_func: Callable, max_countdown: int = 60):
    """
    Helper for Celery tasks to retry with countdown instead of sleep.

    Replaces:
        while not is_ready():
            time.sleep(5)  # ❌ BLOCKS WORKER

    With:
        if not is_ready():
            raise self.retry(countdown=5)  # ✅ RELEASES WORKER

    Usage:
        @shared_task(bind=True, max_retries=10)
        def wait_for_completion(self, job_id):
            poll_with_celery_retry(
                self,
                condition_func=lambda: Job.objects.get(id=job_id).status == 'COMPLETED',
                max_countdown=300
            )
            # Condition met - continue processing
            return process_completed_job(job_id)
    """
    if not condition_func():
        # Condition not met - retry with exponential backoff
        current_retry = task_instance.request.retries
        countdown = min(2 ** current_retry, max_countdown)

        logger.info(
            f"Condition not met, retrying in {countdown}s",
            extra={
                'task': task_instance.name,
                'retry': current_retry,
                'countdown': countdown
            }
        )

        raise task_instance.retry(countdown=countdown)

    # Condition met - continue execution
    logger.info(
        f"Condition met for {task_instance.name}",
        extra={'task': task_instance.name}
    )


__all__ = [
    'poll_until_condition',
    'poll_with_celery_retry',
    'ConditionPoller',
    'PollingTimeoutError'
]
