"""
Universal Idempotency Service for Background Tasks

Provides comprehensive idempotency support for ALL Celery tasks with:
- Automatic key generation from task signatures
- Redis-based distributed locks (faster than DB)
- Configurable TTL per task type
- Metrics tracking for duplicate detection
- Graceful fallback to database when Redis unavailable

Observability Enhancement (2025-10-01):
- Added Prometheus counters for dedupe hits/misses
- Tracks task-level idempotency effectiveness
- Enables duplicate task pattern detection

Extends the existing IdempotencyService for sync operations while
adding task-specific features for background job deduplication.

Usage:
    # Automatic idempotency via decorator
    @shared_task
    @with_idempotency(ttl_seconds=7200)
    def my_task(data):
        pass

    # Manual idempotency control
    service = UniversalIdempotencyService()
    if not service.check_duplicate(key):
        result = execute_task()
        service.store_result(key, result)
"""

import hashlib
import json
import logging
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.conf import settings

from apps.core.models.sync_idempotency import SyncIdempotencyRecord
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY

# Prometheus metrics integration
try:
    from monitoring.services.prometheus_metrics import prometheus
    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False

logger = logging.getLogger('celery.idempotency')


class UniversalIdempotencyService:
    """
    Universal idempotency service for all background tasks.

    Features:
    - Redis-first with database fallback
    - Distributed lock support
    - Automatic key generation
    - Configurable TTL
    - Metrics tracking
    """

    # Default TTL values by task category
    DEFAULT_TTL = {
        'default': SECONDS_IN_HOUR,           # 1 hour
        'critical': SECONDS_IN_HOUR * 4,      # 4 hours (autoclose, escalation)
        'report': SECONDS_IN_DAY,             # 24 hours (reports)
        'email': SECONDS_IN_HOUR * 2,         # 2 hours (emails)
        'mutation': SECONDS_IN_HOUR * 6,      # 6 hours (GraphQL mutations)
        'maintenance': SECONDS_IN_HOUR * 12,  # 12 hours (cleanup tasks)
    }

    # Lock timeout to prevent deadlocks
    LOCK_TIMEOUT = 300  # 5 minutes

    # Metric keys
    METRIC_DUPLICATE_DETECTED = 'task_idempotency:duplicate_detected'
    METRIC_LOCK_ACQUIRED = 'task_idempotency:lock_acquired'
    METRIC_LOCK_FAILED = 'task_idempotency:lock_failed'

    @classmethod
    def generate_task_key(
        cls,
        task_name: str,
        args: tuple = None,
        kwargs: dict = None,
        scope: str = 'global'
    ) -> str:
        """
        Generate deterministic idempotency key from task signature.

        Args:
            task_name: Name of the Celery task
            args: Task positional arguments
            kwargs: Task keyword arguments
            scope: Scope of idempotency ('global', 'user', 'tenant')

        Returns:
            SHA256 hash string (64 chars)

        Example:
            key = generate_task_key('auto_close_jobs', args=(job_id,))
            # Returns: 'task:auto_close_jobs:a3f2b1c...'
        """
        try:
            # Build payload for hashing
            payload = {
                'task': task_name,
                'args': args or (),
                'kwargs': kwargs or {},
                'scope': scope
            }

            # Create deterministic JSON string
            payload_str = json.dumps(payload, sort_keys=True, default=str)

            # Generate SHA256 hash
            hash_obj = hashlib.sha256(payload_str.encode('utf-8'))
            hash_hex = hash_obj.hexdigest()[:64]

            # Prefix for easy identification
            return f"task:{task_name}:{hash_hex}"

        except (TypeError, ValueError) as e:
            logger.error(f"Failed to generate task key: {e}", exc_info=True)
            # Fallback to simple key
            return f"task:{task_name}:{hash(str(args))}{hash(str(kwargs))}"

    @classmethod
    def check_duplicate(
        cls,
        idempotency_key: str,
        use_redis: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Check if task was already executed (idempotency check).

        Args:
            idempotency_key: Unique key for the task
            use_redis: Try Redis first before database

        Returns:
            Cached result if duplicate, None otherwise

        Implementation:
            1. Check Redis cache (fast path)
            2. Fallback to database if Redis unavailable
            3. Update metrics on duplicate detection
        """
        try:
            # Try Redis first (10-50x faster than DB)
            if use_redis:
                cached_result = cls._check_redis_cache(idempotency_key)
                if cached_result is not None:
                    cls._increment_metric(cls.METRIC_DUPLICATE_DETECTED)
                    # OBSERVABILITY: Record dedupe HIT in Prometheus
                    cls._record_prometheus_dedupe(idempotency_key, result='hit', source='redis')
                    logger.info(f"Duplicate task detected (Redis): {idempotency_key[:32]}...")
                    return cached_result

            # Fallback to database
            db_result = cls._check_database(idempotency_key)
            if db_result is not None:
                cls._increment_metric(cls.METRIC_DUPLICATE_DETECTED)
                # OBSERVABILITY: Record dedupe HIT in Prometheus
                cls._record_prometheus_dedupe(idempotency_key, result='hit', source='database')
                logger.info(f"Duplicate task detected (DB): {idempotency_key[:32]}...")

                # Warm Redis cache for future checks
                if use_redis:
                    cls._cache_to_redis(idempotency_key, db_result, ttl=SECONDS_IN_HOUR)

                return db_result

            # OBSERVABILITY: Record dedupe MISS (new task) in Prometheus
            cls._record_prometheus_dedupe(idempotency_key, result='miss', source='new')
            return None

        except ConnectionError as e:
            logger.warning(f"Redis connection error, using database only: {e}")
            return cls._check_database(idempotency_key)
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error checking idempotency: {e}", exc_info=True)
            return None

    @classmethod
    def store_result(
        cls,
        idempotency_key: str,
        result_data: Dict[str, Any],
        ttl_seconds: int = None,
        task_name: str = '',
        user_id: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> bool:
        """
        Store task result for future idempotency checks.

        Args:
            idempotency_key: Unique key for the task
            result_data: Result to cache
            ttl_seconds: Time-to-live in seconds
            task_name: Name of task (for logging)
            user_id: User ID (for scoping)
            device_id: Device ID (for scoping)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            ttl = ttl_seconds or cls.DEFAULT_TTL['default']

            # Store in Redis (fast)
            redis_success = cls._cache_to_redis(idempotency_key, result_data, ttl=ttl)

            # Store in database (persistent)
            db_success = cls._store_to_database(
                idempotency_key,
                result_data,
                ttl_seconds=ttl,
                task_name=task_name,
                user_id=user_id,
                device_id=device_id
            )

            if redis_success or db_success:
                logger.debug(f"Stored idempotency result: {idempotency_key[:32]}... (TTL: {ttl}s)")
                return True

            return False

        except (ConnectionError, DatabaseError, IntegrityError, ValidationError) as e:
            logger.error(f"Failed to store idempotency result: {e}", exc_info=True)
            return False

    @classmethod
    @contextmanager
    def acquire_distributed_lock(
        cls,
        lock_key: str,
        timeout: int = None,
        blocking: bool = True
    ):
        """
        Context manager for distributed lock acquisition.

        Args:
            lock_key: Unique lock identifier
            timeout: Lock timeout in seconds
            blocking: Wait for lock if already held

        Yields:
            True if lock acquired, raises otherwise

        Usage:
            with acquire_distributed_lock('schedule:create:job123'):
                create_scheduled_job(job_id=123)

        Implementation:
            - Redis lock with automatic expiration
            - Fallback to database lock if Redis unavailable
            - Automatic cleanup on context exit
        """
        lock = None
        lock_timeout = timeout or cls.LOCK_TIMEOUT
        full_lock_key = f"lock:{lock_key}"

        try:
            # Try Redis lock first (preferred)
            lock = cls._acquire_redis_lock(full_lock_key, lock_timeout, blocking)

            if lock:
                cls._increment_metric(cls.METRIC_LOCK_ACQUIRED)
                logger.debug(f"Acquired distributed lock: {lock_key}")
                yield True
            else:
                cls._increment_metric(cls.METRIC_LOCK_FAILED)
                raise RuntimeError(f"Failed to acquire lock: {lock_key}")

        except ConnectionError as e:
            # Fallback to database lock
            logger.warning(f"Redis unavailable, using database lock: {e}")
            with cls._acquire_database_lock(lock_key, lock_timeout):
                yield True

        finally:
            # Release lock
            if lock:
                cls._release_redis_lock(lock)
                logger.debug(f"Released distributed lock: {lock_key}")

    # Private helper methods

    @staticmethod
    def _check_redis_cache(key: str) -> Optional[Dict[str, Any]]:
        """Check Redis for cached result"""
        try:
            cached = cache.get(key)
            return cached if isinstance(cached, dict) else None
        except ConnectionError:
            return None

    @staticmethod
    def _check_database(key: str) -> Optional[Dict[str, Any]]:
        """Check database for stored result"""
        try:
            record = SyncIdempotencyRecord.objects.filter(
                idempotency_key=key,
                expires_at__gt=timezone.now()
            ).first()

            if record:
                # Update hit tracking
                record.hit_count += 1
                record.last_hit_at = timezone.now()
                record.save(update_fields=['hit_count', 'last_hit_at'])

                return record.response_data

            return None
        except (DatabaseError, IntegrityError):
            return None

    @staticmethod
    def _cache_to_redis(key: str, data: Dict[str, Any], ttl: int) -> bool:
        """Cache result to Redis"""
        try:
            cache.set(key, data, timeout=ttl)
            return True
        except ConnectionError:
            return False

    @staticmethod
    def _store_to_database(
        key: str,
        data: Dict[str, Any],
        ttl_seconds: int,
        task_name: str = '',
        user_id: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> bool:
        """Store result to database"""
        try:
            with transaction.atomic():
                SyncIdempotencyRecord.objects.create(
                    idempotency_key=key,
                    scope='task',
                    request_hash=hashlib.sha256(str(data).encode()).hexdigest()[:64],
                    response_data=data,
                    user_id=user_id,
                    device_id=device_id,
                    endpoint=task_name,
                    expires_at=timezone.now() + timedelta(seconds=ttl_seconds)
                )
            return True
        except IntegrityError:
            # Duplicate key - another concurrent request beat us
            return False
        except (DatabaseError, ValidationError):
            return False

    @staticmethod
    def _acquire_redis_lock(key: str, timeout: int, blocking: bool):
        """Acquire Redis lock"""
        try:
            from django.core.cache.backends.redis import RedisCache

            if isinstance(cache, RedisCache):
                # Use Redis native locking
                return cache.client.get_client().lock(
                    key,
                    timeout=timeout,
                    blocking=blocking,
                    blocking_timeout=timeout if blocking else 0
                )
            else:
                # Use cache-based locking (slower but works)
                if cache.add(key, 'locked', timeout=timeout):
                    return key  # Return key as lock handle
                return None

        except (ConnectionError, AttributeError):
            return None

    @staticmethod
    def _release_redis_lock(lock):
        """Release Redis lock"""
        try:
            if hasattr(lock, 'release'):
                lock.release()
            elif isinstance(lock, str):
                cache.delete(lock)
        except (ConnectionError, AttributeError):
            pass

    @staticmethod
    @contextmanager
    def _acquire_database_lock(lock_key: str, timeout: int):
        """Fallback database lock using advisory locks"""
        from django.db import connection

        # Convert lock_key to integer for PostgreSQL advisory lock
        lock_id = abs(hash(lock_key)) % (2**31)

        try:
            with connection.cursor() as cursor:
                # Try to acquire lock
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
                acquired = cursor.fetchone()[0]

                if not acquired:
                    raise RuntimeError(f"Failed to acquire database lock: {lock_key}")

                yield True

        finally:
            # Release lock
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
            except (DatabaseError, IntegrityError):
                pass

    @staticmethod
    def _increment_metric(metric_name: str, value: int = 1):
        """Increment metric counter"""
        try:
            current = cache.get(metric_name, 0)
            cache.set(metric_name, current + value, timeout=SECONDS_IN_DAY)
        except ConnectionError:
            pass

    @classmethod
    def _record_prometheus_dedupe(cls, idempotency_key: str, result: str, source: str):
        """
        Record idempotency dedupe result in Prometheus.

        Observability Enhancement (2025-10-01):
        Tracks dedupe effectiveness:
        - Result: 'hit' (duplicate detected) or 'miss' (new task)
        - Source: 'redis', 'database', or 'new'
        - Task name extracted from idempotency key

        Enables analysis:
        - Dedupe rate: hit/(hit+miss) - ideal < 5% in steady state
        - Cache effectiveness: redis_hits/total_hits - ideal > 90%

        Args:
            idempotency_key: Idempotency key (contains task name)
            result: 'hit' or 'miss'
            source: 'redis', 'database', or 'new'
        """
        if not PROMETHEUS_ENABLED:
            return

        try:
            # Extract task name from key (format: 'task:task_name:hash')
            parts = idempotency_key.split(':', 2)
            task_name = parts[1] if len(parts) > 1 else 'unknown'

            # Record dedupe counter
            prometheus.increment_counter(
                'celery_idempotency_dedupe_total',
                labels={
                    'task_name': task_name,
                    'result': result,  # 'hit' or 'miss'
                    'source': source   # 'redis', 'database', 'new'
                },
                help_text='Total idempotency checks for Celery tasks (dedupe hits and misses)'
            )

            logger.debug(
                f"Recorded Prometheus dedupe metric: task={task_name}, result={result}, source={source}"
            )

        except Exception as e:
            # Don't fail task execution if metrics fail
            logger.warning(f"Failed to record Prometheus dedupe metric: {e}")

    @classmethod
    def get_metrics(cls) -> Dict[str, int]:
        """
        Get current idempotency metrics from Redis cache.

        Returns:
            Dictionary with metric counts:
            - duplicate_detected: Number of duplicate tasks detected
            - lock_acquired: Number of locks successfully acquired
            - lock_failed: Number of failed lock attempts

        Usage:
            metrics = UniversalIdempotencyService.get_metrics()
            print(f"Duplicates: {metrics['duplicate_detected']}")
        """
        try:
            return {
                'duplicate_detected': cache.get(cls.METRIC_DUPLICATE_DETECTED, 0),
                'lock_acquired': cache.get(cls.METRIC_LOCK_ACQUIRED, 0),
                'lock_failed': cache.get(cls.METRIC_LOCK_FAILED, 0)
            }
        except ConnectionError as e:
            logger.warning(f"Failed to retrieve idempotency metrics from cache: {e}")
            return {
                'duplicate_detected': 0,
                'lock_acquired': 0,
                'lock_failed': 0
            }


def with_idempotency(
    ttl_seconds: int = None,
    scope: str = 'global',
    key_generator: Optional[Callable] = None
):
    """
    Decorator for automatic task idempotency.

    Args:
        ttl_seconds: Time-to-live for idempotency cache
        scope: Idempotency scope ('global', 'user', 'tenant')
        key_generator: Custom key generation function

    Returns:
        Decorated function with automatic idempotency

    Usage:
        @shared_task
        @with_idempotency(ttl_seconds=7200, scope='user')
        def my_task(user_id, data):
            # Task logic here
            return result

    Behavior:
        1. Generate idempotency key from task signature
        2. Check if task already executed
        3. Return cached result if duplicate
        4. Execute task if new
        5. Cache result for future checks
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            service = UniversalIdempotencyService()

            # Generate idempotency key
            if key_generator:
                idempotency_key = key_generator(*args, **kwargs)
            else:
                task_name = func.__name__
                idempotency_key = service.generate_task_key(
                    task_name, args, kwargs, scope
                )

            # Check for duplicate
            cached_result = service.check_duplicate(idempotency_key)
            if cached_result is not None:
                logger.info(
                    f"Returning cached result for {func.__name__}",
                    extra={'idempotency_key': idempotency_key[:32]}
                )
                return cached_result.get('result')

            # Execute task
            try:
                result = func(*args, **kwargs)

                # Cache result
                service.store_result(
                    idempotency_key,
                    {'result': result, 'status': 'success'},
                    ttl_seconds=ttl_seconds,
                    task_name=func.__name__
                )

                return result

            except Exception as exc:
                # Cache error to prevent retry storms
                service.store_result(
                    idempotency_key,
                    {'error': str(exc), 'status': 'failed'},
                    ttl_seconds=ttl_seconds or SECONDS_IN_HOUR,  # Shorter TTL for errors
                    task_name=func.__name__
                )
                raise

        return wrapper
    return decorator
