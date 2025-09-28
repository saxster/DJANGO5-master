"""
Retry Mechanism for Transient Failures

Provides decorators and utilities for retrying operations that fail
due to transient issues like lock acquisition failures, database deadlocks,
or temporary network issues.

Following .claude/rules.md:
- Specific exception handling (Rule 11)
- Reusable utility functions
- Configurable retry policies
"""

import time
import logging
import functools
from typing import Tuple, Type, Callable, Any, Optional
from apps.core.utils_new.distributed_locks import LockAcquisitionError, LockTimeoutError
from apps.core.mixins.optimistic_locking import StaleObjectError
from django.db import OperationalError, InterfaceError, DatabaseError

logger = logging.getLogger(__name__)


__all__ = [
    'with_retry',
    'exponential_backoff',
    'RetryPolicy',
    'TransientErrorDetector',
]


TRANSIENT_EXCEPTIONS = (
    LockAcquisitionError,
    LockTimeoutError,
    StaleObjectError,
    OperationalError,
    InterfaceError,
)


class RetryPolicy:
    """Configuration for retry behavior"""

    DEFAULT = {
        'max_retries': 3,
        'initial_delay': 0.1,
        'backoff_factor': 2.0,
        'max_delay': 5.0,
        'jitter': True,
    }

    AGGRESSIVE = {
        'max_retries': 5,
        'initial_delay': 0.05,
        'backoff_factor': 1.5,
        'max_delay': 3.0,
        'jitter': True,
    }

    CONSERVATIVE = {
        'max_retries': 2,
        'initial_delay': 0.5,
        'backoff_factor': 2.5,
        'max_delay': 10.0,
        'jitter': False,
    }

    DATABASE_OPERATION = {
        'max_retries': 3,
        'initial_delay': 0.2,
        'backoff_factor': 2.0,
        'max_delay': 4.0,
        'jitter': True,
    }

    LOCK_ACQUISITION = {
        'max_retries': 4,
        'initial_delay': 0.1,
        'backoff_factor': 1.5,
        'max_delay': 2.0,
        'jitter': True,
    }


class TransientErrorDetector:
    """Determines if an error is transient and worth retrying"""

    @staticmethod
    def is_transient(exception: Exception) -> bool:
        """
        Check if exception is transient (temporary, worth retrying).

        Args:
            exception: Exception to check

        Returns:
            True if exception is transient
        """
        if isinstance(exception, TRANSIENT_EXCEPTIONS):
            return True

        if isinstance(exception, DatabaseError):
            error_msg = str(exception).lower()
            transient_keywords = [
                'deadlock',
                'timeout',
                'connection',
                'temporary',
                'unavailable',
                'busy'
            ]
            return any(keyword in error_msg for keyword in transient_keywords)

        return False


def exponential_backoff(
    attempt: int,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    max_delay: float = 5.0,
    jitter: bool = True
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current retry attempt (0-indexed)
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for each retry
        max_delay: Maximum delay in seconds
        jitter: Add random jitter to prevent thundering herd

    Returns:
        Delay in seconds
    """
    delay = min(initial_delay * (backoff_factor ** attempt), max_delay)

    if jitter:
        import random
        jitter_amount = delay * 0.1
        delay += random.uniform(-jitter_amount, jitter_amount)

    return max(0, delay)


def with_retry(
    exceptions: Tuple[Type[Exception], ...] = TRANSIENT_EXCEPTIONS,
    max_retries: int = 3,
    retry_policy: str = 'DEFAULT',
    on_retry: Optional[Callable] = None,
    raise_on_exhausted: bool = True
):
    """
    Decorator to retry function on transient failures.

    Usage:
        @with_retry(max_retries=3)
        def update_job_status(job_id):
            # This will retry up to 3 times on transient errors
            job = Job.objects.get(pk=job_id)
            job.status = 'COMPLETED'
            job.save()

    Args:
        exceptions: Tuple of exception types to catch and retry
        max_retries: Maximum number of retry attempts
        retry_policy: Name of RetryPolicy to use ('DEFAULT', 'AGGRESSIVE', etc.)
        on_retry: Optional callback function called before each retry
        raise_on_exhausted: Whether to raise exception after max retries

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            policy = getattr(RetryPolicy, retry_policy, RetryPolicy.DEFAULT)

            last_exception = None

            for attempt in range(policy['max_retries'] + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == policy['max_retries']:
                        if raise_on_exhausted:
                            logger.error(
                                f"Retry exhausted after {policy['max_retries']} attempts",
                                extra={
                                    'function': func.__name__,
                                    'attempts': attempt + 1,
                                    'error': str(e)
                                },
                                exc_info=True
                            )
                            raise
                        else:
                            logger.warning(
                                f"Retry exhausted, returning None",
                                extra={'function': func.__name__}
                            )
                            return None

                    if not TransientErrorDetector.is_transient(e):
                        logger.info(
                            f"Non-transient error, not retrying: {type(e).__name__}",
                            extra={'function': func.__name__}
                        )
                        raise

                    delay = exponential_backoff(
                        attempt=attempt,
                        initial_delay=policy['initial_delay'],
                        backoff_factor=policy['backoff_factor'],
                        max_delay=policy['max_delay'],
                        jitter=policy['jitter']
                    )

                    logger.info(
                        f"Retrying {func.__name__} after {delay:.2f}s (attempt {attempt + 2}/{policy['max_retries'] + 1})",
                        extra={
                            'function': func.__name__,
                            'attempt': attempt + 2,
                            'delay_seconds': delay,
                            'error_type': type(e).__name__
                        }
                    )

                    if on_retry:
                        on_retry(attempt, e, delay)

                    time.sleep(delay)

            return None

        return wrapper
    return decorator


def retry_on_lock_failure(max_retries: int = 4):
    """
    Specialized retry decorator for lock acquisition failures.

    Uses LOCK_ACQUISITION retry policy optimized for distributed locks.

    Args:
        max_retries: Maximum retry attempts (default: 4)

    Returns:
        Decorator function
    """
    return with_retry(
        exceptions=(LockAcquisitionError, LockTimeoutError),
        max_retries=max_retries,
        retry_policy='LOCK_ACQUISITION',
        raise_on_exhausted=True
    )


def retry_on_stale_object(max_retries: int = 3):
    """
    Specialized retry decorator for optimistic lock failures.

    Args:
        max_retries: Maximum retry attempts (default: 3)

    Returns:
        Decorator function
    """
    return with_retry(
        exceptions=(StaleObjectError,),
        max_retries=max_retries,
        retry_policy='DEFAULT',
        raise_on_exhausted=True
    )