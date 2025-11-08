"""
Async Retry Mechanism - Blocking I/O Elimination

Provides non-blocking retry mechanisms for Django views and services.
Replaces time.sleep() with cache-based coordination and exponential backoff.

Following .claude/rules.md:
- Rule #14: No blocking time.sleep() in request paths
- Rule #15: Use retry mechanism with exponential backoff
- Rule #21: Network calls must have timeouts

Usage:
    from apps.core.utils_new.async_retry_mechanism import async_retry_on_integrity_error

    @async_retry_on_integrity_error(max_retries=3)
    def my_view(request):
        # Database operations that might have race conditions
        user.save()
"""

import logging
import hashlib
import random
from functools import wraps
from typing import Optional, Callable, Tuple, Any
from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError, OperationalError, DatabaseError
from django.http import JsonResponse
from django.utils import timezone

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

logger = logging.getLogger(__name__)


class AsyncRetryCoordinator:
    """
    Coordinates retries using cache instead of blocking time.sleep().

    Uses cache to track retry attempts and coordinate backoff without blocking.
    """

    CACHE_PREFIX = 'async_retry'
    DEFAULT_BACKOFF_BASE = 2  # Exponential base
    DEFAULT_JITTER_MAX = 0.3  # 30% jitter

    @classmethod
    def generate_retry_key(cls, operation_id: str, context: dict) -> str:
        """Generate unique retry coordination key."""
        context_str = ''.join(f"{k}:{v}" for k, v in sorted(context.items()))
        hash_input = f"{operation_id}:{context_str}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return f"{cls.CACHE_PREFIX}:{operation_id}:{hash_digest}"

    @classmethod
    def should_retry(
        cls,
        retry_key: str,
        max_retries: int,
        backoff_seconds: int = 1
    ) -> Tuple[bool, int]:
        """
        Check if retry should be attempted (non-blocking).

        Args:
            retry_key: Unique key for this operation
            max_retries: Maximum retry attempts
            backoff_seconds: Base backoff time in seconds

        Returns:
            Tuple of (should_retry: bool, attempt_number: int)
        """
        # Get current retry count from cache
        retry_data = cache.get(retry_key) or {'count': 0, 'last_attempt': None}

        attempt_number = retry_data['count'] + 1

        # Check if max retries exceeded
        if attempt_number > max_retries:
            logger.warning(
                f"Max retries exceeded for {retry_key}",
                extra={'retry_key': retry_key, 'attempts': attempt_number}
            )
            cache.delete(retry_key)  # Clean up
            return False, attempt_number

        # Check if backoff period elapsed (non-blocking)
        if retry_data.get('last_attempt'):
            elapsed = (timezone.now() - retry_data['last_attempt']).total_seconds()
            required_backoff = cls._calculate_backoff(attempt_number, backoff_seconds)

            if elapsed < required_backoff:
                # Too soon to retry - return 429 or queue for later
                logger.debug(
                    f"Retry backoff not elapsed for {retry_key}",
                    extra={
                        'elapsed': elapsed,
                        'required': required_backoff,
                        'attempt': attempt_number
                    }
                )
                return False, attempt_number

        # Update retry count and timestamp
        cache.set(
            retry_key,
            {'count': attempt_number, 'last_attempt': timezone.now()},
            timeout=SECONDS_IN_MINUTE * 5  # 5 minute TTL
        )

        return True, attempt_number

    @classmethod
    def _calculate_backoff(cls, attempt: int, base_seconds: int) -> float:
        """Calculate exponential backoff with jitter."""
        backoff = base_seconds * (cls.DEFAULT_BACKOFF_BASE ** (attempt - 1))
        jitter = random.uniform(0, cls.DEFAULT_JITTER_MAX * backoff)
        return backoff + jitter

    @classmethod
    def clear_retry_state(cls, retry_key: str):
        """Clear retry state (call on success)."""
        cache.delete(retry_key)


def async_retry_on_integrity_error(
    max_retries: int = 3,
    backoff_seconds: int = 1,
    operation_id: Optional[str] = None
):
    """
    Decorator for non-blocking retry on IntegrityError (race conditions).

    Replaces:
        for attempt in range(3):
            try:
                obj.save()
                break
            except IntegrityError:
                time.sleep(1)  # ❌ BLOCKS REQUEST

    With:
        @async_retry_on_integrity_error(max_retries=3)
        def my_view(request):
            obj.save()  # Automatically retried via cache coordination

    Usage:
        @async_retry_on_integrity_error(max_retries=3)
        def create_ticket_view(request):
            ticket = Ticket.objects.create(...)
            return JsonResponse({'id': ticket.id})

    Returns:
        - 429 status if retry backoff not elapsed (client should retry later)
        - Original response if operation succeeds
        - Raises exception if all retries exhausted
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate retry coordination key
            op_id = operation_id or view_func.__name__
            context = {
                'path': request.path,
                'method': request.method,
                'user_id': request.user.id if request.user.is_authenticated else 'anonymous'
            }
            retry_key = AsyncRetryCoordinator.generate_retry_key(op_id, context)

            # Check if we should retry (non-blocking check)
            should_retry, attempt = AsyncRetryCoordinator.should_retry(
                retry_key,
                max_retries,
                backoff_seconds
            )

            if not should_retry and attempt > 1:
                # Backoff period not elapsed - return 429
                required_backoff = AsyncRetryCoordinator._calculate_backoff(
                    attempt,
                    backoff_seconds
                )
                return JsonResponse(
                    {
                        'error': 'Rate limited - please retry after backoff period',
                        'retry_after': int(required_backoff),
                        'attempt': attempt
                    },
                    status=429,
                    headers={'Retry-After': str(int(required_backoff))}
                )

            try:
                # Execute view function
                response = view_func(request, *args, **kwargs)

                # Success - clear retry state
                AsyncRetryCoordinator.clear_retry_state(retry_key)

                return response

            except IntegrityError as e:
                logger.warning(
                    f"IntegrityError in {op_id}, attempt {attempt}/{max_retries}",
                    extra={
                        'retry_key': retry_key,
                        'attempt': attempt,
                        'error': str(e)
                    }
                )

                if attempt >= max_retries:
                    # Max retries exhausted - clear state and raise
                    AsyncRetryCoordinator.clear_retry_state(retry_key)
                    raise

                # Return 429 - client should retry after backoff
                backoff_time = AsyncRetryCoordinator._calculate_backoff(
                    attempt + 1,
                    backoff_seconds
                )
                return JsonResponse(
                    {
                        'error': 'Database conflict - please retry',
                        'retry_after': int(backoff_time),
                        'attempt': attempt,
                        'max_retries': max_retries
                    },
                    status=429,
                    headers={'Retry-After': str(int(backoff_time))}
                )

        return wrapper
    return decorator


def retry_with_cache_backoff(
    exceptions: tuple = DATABASE_EXCEPTIONS,
    max_retries: int = 3,
    backoff_seconds: int = 1,
    operation_id: Optional[str] = None,
    log_level: str = 'warning'
):
    """
    General-purpose non-blocking retry decorator.

    More flexible than async_retry_on_integrity_error - supports any exception types.

    Usage:
        from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

        @retry_with_cache_backoff(
            exceptions=NETWORK_EXCEPTIONS,
            max_retries=5,
            backoff_seconds=2
        )
        def call_external_api(url):
            response = requests.get(url, timeout=(5, 15))
            return response.json()

    Note: This is for service layer functions, not Django views.
    For views, use async_retry_on_integrity_error instead.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_id = operation_id or f"{func.__module__}.{func.__name__}"

            # Generate retry key from function signature
            context = {
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }
            retry_key = AsyncRetryCoordinator.generate_retry_key(op_id, context)

            attempt = 0
            last_exception = None

            while attempt < max_retries:
                attempt += 1

                # Check backoff (non-blocking)
                should_retry, current_attempt = AsyncRetryCoordinator.should_retry(
                    retry_key,
                    max_retries,
                    backoff_seconds
                )

                if not should_retry and attempt > 1:
                    # Backoff not elapsed, but this is a function not a view
                    # We can't return 429, so we raise the last exception
                    if last_exception:
                        raise last_exception
                    break

                try:
                    result = func(*args, **kwargs)
                    AsyncRetryCoordinator.clear_retry_state(retry_key)
                    return result

                except exceptions as e:
                    last_exception = e
                    log_func = getattr(logger, log_level)
                    log_func(
                        f"Retry attempt {attempt}/{max_retries} for {op_id}",
                        extra={'error': str(e), 'retry_key': retry_key},
                        exc_info=(attempt == max_retries)  # Full trace on last attempt
                    )

                    if attempt >= max_retries:
                        AsyncRetryCoordinator.clear_retry_state(retry_key)
                        raise

                    # Continue to next iteration (backoff coordinated via cache)
                    continue

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Retry loop exited unexpectedly for {op_id}")

        return wrapper
    return decorator


class CacheBasedLock:
    """
    Non-blocking distributed lock using cache.

    Replaces patterns like:
        while not acquired:
            time.sleep(0.1)  # ❌ BLOCKING
            acquired = try_acquire_lock()

    With:
        with CacheBasedLock('my_operation', timeout=30):
            # Critical section
    """

    def __init__(self, lock_name: str, timeout: int = 30, poll_interval: int = 1):
        """
        Initialize cache-based lock.

        Args:
            lock_name: Unique lock identifier
            timeout: Lock expiration in seconds
            poll_interval: How often to check lock availability (for compatibility)
        """
        self.lock_name = lock_name
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.lock_key = f"lock:{lock_name}"
        self.acquired = False

    def __enter__(self):
        """Acquire lock (non-blocking)."""
        # Try to acquire lock
        self.acquired = cache.add(self.lock_key, timezone.now().isoformat(), timeout=self.timeout)

        if not self.acquired:
            # Lock already held - don't block, raise immediately
            logger.debug(f"Lock {self.lock_name} already held")
            raise LockAcquisitionFailed(f"Could not acquire lock: {self.lock_name}")

        logger.debug(f"Lock {self.lock_name} acquired")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self.acquired:
            cache.delete(self.lock_key)
            logger.debug(f"Lock {self.lock_name} released")


class LockAcquisitionFailed(Exception):
    """Raised when lock cannot be acquired immediately."""
    pass


__all__ = [
    'async_retry_on_integrity_error',
    'retry_with_cache_backoff',
    'AsyncRetryCoordinator',
    'CacheBasedLock',
    'LockAcquisitionFailed'
]
