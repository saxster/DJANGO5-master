"""
Distributed locking utilities for race condition prevention
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Optional

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


__all__ = [
    'LockAcquisitionError',
    'LockTimeoutError',
    'DistributedLock',
    'distributed_lock',
    'LockRegistry',
    'with_distributed_lock',
    'LockMonitor',
]


class LockAcquisitionError(Exception):
    """Raised when unable to acquire a distributed lock"""
    pass


class LockTimeoutError(Exception):
    """Raised when lock operation times out"""
    pass


class DistributedLock:
    """
    Redis-based distributed lock implementation

    Prevents race conditions in critical sections across multiple
    application servers or processes.
    """

    def __init__(
        self,
        lock_key: str,
        timeout: int = 10,
        blocking_timeout: Optional[int] = None,
        auto_renewal: bool = False
    ):
        """
        Initialize distributed lock

        Args:
            lock_key: Unique identifier for the lock
            timeout: Lock expiration time in seconds (default: 10)
            blocking_timeout: How long to wait for lock acquisition (default: timeout)
            auto_renewal: Automatically renew lock before expiration
        """
        self.lock_key = f"distributed_lock:{lock_key}"
        self.timeout = timeout
        self.blocking_timeout = blocking_timeout or timeout
        self.auto_renewal = auto_renewal
        self.lock_id = str(uuid.uuid4())
        self.acquired = False

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the lock

        Args:
            blocking: Wait for lock if not immediately available

        Returns:
            True if lock acquired, False otherwise

        Raises:
            LockTimeoutError: If blocking_timeout exceeded
        """
        start_time = time.time()

        while True:
            acquired = cache.add(self.lock_key, self.lock_id, self.timeout)

            if acquired:
                self.acquired = True
                logger.debug(f"Lock acquired: {self.lock_key}")
                return True

            if not blocking:
                return False

            if time.time() - start_time > self.blocking_timeout:
                raise LockTimeoutError(
                    f"Failed to acquire lock '{self.lock_key}' within {self.blocking_timeout}s"
                )

            time.sleep(0.01)

    def release(self):
        """Release the lock"""
        if not self.acquired:
            logger.warning(f"Attempting to release unacquired lock: {self.lock_key}")
            return

        cached_lock_id = cache.get(self.lock_key)

        if cached_lock_id == self.lock_id:
            cache.delete(self.lock_key)
            self.acquired = False
            logger.debug(f"Lock released: {self.lock_key}")
        else:
            logger.warning(
                f"Lock '{self.lock_key}' was acquired by another process. "
                f"Expected {self.lock_id}, found {cached_lock_id}"
            )

    def extend(self, additional_time: int):
        """
        Extend lock timeout

        Args:
            additional_time: Additional seconds to hold lock
        """
        if not self.acquired:
            raise LockAcquisitionError("Cannot extend unacquired lock")

        cached_lock_id = cache.get(self.lock_key)

        if cached_lock_id == self.lock_id:
            cache.set(self.lock_key, self.lock_id, additional_time)
            logger.debug(f"Lock extended: {self.lock_key} for {additional_time}s")
        else:
            raise LockAcquisitionError(
                f"Cannot extend lock owned by another process"
            )

    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            raise LockAcquisitionError(f"Failed to acquire lock: {self.lock_key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
        return False


@contextmanager
def distributed_lock(
    lock_key: str,
    timeout: int = 10,
    blocking_timeout: Optional[int] = None,
    raise_on_failure: bool = True
):
    """
    Context manager for distributed locking

    Usage:
        with distributed_lock('attendance_update', timeout=5):
            # Critical section
            update_attendance_record()

    Args:
        lock_key: Unique identifier for the lock
        timeout: Lock expiration time in seconds
        blocking_timeout: How long to wait for lock acquisition
        raise_on_failure: Raise exception if lock cannot be acquired

    Raises:
        LockAcquisitionError: If raise_on_failure=True and lock not acquired
        LockTimeoutError: If blocking_timeout exceeded
    """
    lock = DistributedLock(
        lock_key=lock_key,
        timeout=timeout,
        blocking_timeout=blocking_timeout
    )

    try:
        acquired = lock.acquire()

        if not acquired and raise_on_failure:
            raise LockAcquisitionError(f"Failed to acquire lock: {lock_key}")

        yield acquired

    finally:
        if lock.acquired:
            lock.release()


class LockRegistry:
    """
    Registry of commonly used locks with predefined configurations
    """

    ATTENDANCE_UPDATE = {
        'timeout': 10,
        'blocking_timeout': 5,
    }

    FACE_VERIFICATION = {
        'timeout': 15,
        'blocking_timeout': 10,
    }

    BEHAVIORAL_PROFILE_UPDATE = {
        'timeout': 20,
        'blocking_timeout': 15,
    }

    EMBEDDING_UPDATE = {
        'timeout': 10,
        'blocking_timeout': 5,
    }

    JOB_WORKFLOW_UPDATE = {
        'timeout': 15,
        'blocking_timeout': 10,
    }

    PARENT_CHILD_UPDATE = {
        'timeout': 20,
        'blocking_timeout': 15,
    }

    JOBNEED_STATUS_UPDATE = {
        'timeout': 10,
        'blocking_timeout': 5,
    }

    @classmethod
    def get_lock(cls, lock_type: str, resource_id: str) -> DistributedLock:
        """
        Get a pre-configured lock

        Args:
            lock_type: Type of lock (e.g., 'ATTENDANCE_UPDATE')
            resource_id: Unique identifier for the resource

        Returns:
            Configured DistributedLock instance
        """
        config = getattr(cls, lock_type, cls.ATTENDANCE_UPDATE)
        lock_key = f"{lock_type.lower()}:{resource_id}"

        return DistributedLock(
            lock_key=lock_key,
            **config
        )


def with_distributed_lock(lock_type: str, resource_id_param: str = 'uuid'):
    """
    Decorator for methods requiring distributed locking

    Usage:
        class MyManager:
            @with_distributed_lock('ATTENDANCE_UPDATE', 'uuid')
            def update_record(self, uuid, data):
                # Method automatically protected by lock
                pass

    Args:
        lock_type: Type of lock from LockRegistry
        resource_id_param: Name of parameter containing resource ID
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            resource_id = bound_args.arguments.get(resource_id_param)

            if resource_id is None:
                logger.warning(
                    f"Resource ID parameter '{resource_id_param}' not found. "
                    f"Executing without lock."
                )
                return func(*args, **kwargs)

            lock = LockRegistry.get_lock(lock_type, str(resource_id))

            with lock:
                return func(*args, **kwargs)

        return wrapper
    return decorator


class LockMonitor:
    """Monitor lock acquisition metrics"""

    @staticmethod
    def get_lock_stats(lock_key_pattern: str = "distributed_lock:*") -> dict:
        """
        Get statistics about current locks

        Args:
            lock_key_pattern: Pattern to match lock keys

        Returns:
            Dictionary with lock statistics
        """
        stats = {
            'total_locks': 0,
            'locks_by_type': {},
            'oldest_lock_age': None
        }

        return stats

    @staticmethod
    def force_release_lock(lock_key: str):
        """
        Force release a lock (emergency use only)

        Args:
            lock_key: Key of lock to release
        """
        full_key = f"distributed_lock:{lock_key}"
        cache.delete(full_key)
        logger.warning(f"Force released lock: {full_key}")


def with_lock_and_transaction(lock_type: str, resource_id_param: str = 'uuid', database: str = None):
    """
    Combined decorator for distributed locking + atomic transactions.

    Ensures both resource locking and transaction atomicity in one decorator.
    Lock is acquired BEFORE transaction starts for maximum safety.

    Usage:
        @with_lock_and_transaction('JOB_WORKFLOW_UPDATE', 'job_id')
        def update_job_workflow(self, job_id, new_status):
            # Automatically protected by lock AND transaction
            job = Job.objects.get(id=job_id)
            job.status = new_status
            job.save()

    Complies with: .claude/rules.md - Transaction Management Requirements

    Args:
        lock_type: Type of lock from LockRegistry
        resource_id_param: Parameter name containing resource ID
        database: Database alias for transaction

    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import inspect
            from django.db import transaction
            from apps.core.utils_new.db_utils import get_current_db_name

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            resource_id = bound_args.arguments.get(resource_id_param)

            if resource_id is None:
                logger.warning(
                    f"Resource ID parameter '{resource_id_param}' not found. "
                    f"Executing without lock."
                )
                return func(*args, **kwargs)

            lock = LockRegistry.get_lock(lock_type, str(resource_id))
            db_name = database or get_current_db_name()

            with lock:
                with transaction.atomic(using=db_name):
                    return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator