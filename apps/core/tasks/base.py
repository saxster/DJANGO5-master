"""
Celery Task Base Classes

Provides standardized base classes for all Celery tasks with consistent:
- Error handling and logging patterns
- Retry mechanisms with exponential backoff
- Monitoring and metrics collection
- Circuit breaker patterns for external services
- Task context and metadata management

Observability Enhancement (2025-10-01):
- Added Prometheus counters for task retry tracking
- Tracks retry reasons and task names
- Enables retry pattern analysis

@ontology(
    domain="infrastructure",
    purpose="Base classes for Celery background tasks with retry, monitoring, and error handling patterns",
    task_base_classes=[
        "BaseTask (generic with exponential backoff)",
        "IdempotentTask (duplicate prevention via Redis)",
        "EmailTask (SMTP retry patterns)",
        "ExternalServiceTask (circuit breaker pattern)",
        "ReportTask (long-running with cleanup)",
        "MaintenanceTask (batch processing)"
    ],
    retry_strategy={
        "algorithm": "exponential_backoff_with_jitter",
        "formula": "min(base_delay * 2^retry_count * random(0.5-1.0), max_delay)",
        "default_max_retries": 3,
        "default_retry_delay": "60s",
        "max_backoff": "600s (10min)"
    },
    monitoring_features=[
        "Task start/success/failure counters",
        "Execution duration histograms",
        "Retry tracking with Prometheus",
        "Circuit breaker state per service"
    ],
    idempotency_implementation={
        "backend": "UniversalIdempotencyService (Redis + DB fallback)",
        "key_generation": "task_name + args/kwargs hash",
        "ttl": "3600s (1hr) default",
        "scope": "global, user, or tenant",
        "caching": "success results and errors (shorter TTL)"
    },
    circuit_breaker={
        "failure_threshold": 5,
        "recovery_timeout": "300s (5min)",
        "tracking": "per-service Redis cache"
    },
    task_lifecycle_hooks=["on_success", "on_failure", "on_retry"],
    performance_impact="~2-5ms overhead per task",
    criticality="critical",
    integration_points=["Prometheus", "Sentry", "Redis", "PostgreSQL"],
    tags=["celery", "background-tasks", "retry-logic", "circuit-breaker", "idempotency"]
)

Usage:
    from apps.core.tasks.base import BaseTask, EmailTask, ExternalServiceTask

    @shared_task(base=BaseTask)
    def my_task(data):
        # Task implementation
        return result
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager
import traceback

from celery import Task
from celery.exceptions import Retry, MaxRetriesExceededError
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db import transaction, IntegrityError, DatabaseError

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR
from apps.core.utils_new.datetime_utilities import get_current_utc

# Prometheus metrics integration
try:
    from monitoring.services.prometheus_metrics import prometheus
    PROMETHEUS_ENABLED = True
except ImportError:
    PROMETHEUS_ENABLED = False


logger = logging.getLogger('celery.tasks')


class TaskMetrics:
    """
    Metrics collection for task monitoring.

    Observability Enhancement (2025-10-01):
    - Added Prometheus counter tracking for retries
    - Tracks retry reasons and task names
    """

    @staticmethod
    def increment_counter(metric_name: str, tags: Dict[str, str] = None):
        """
        Increment a counter metric.

        Metrics are stored in both Redis cache and Prometheus (if enabled).

        Args:
            metric_name: Name of the counter metric
            tags: Optional tags/labels dictionary
        """
        tags = tags or {}
        cache_key = f"task_metrics:{metric_name}"
        if tags:
            cache_key += ":" + ":".join([f"{k}={v}" for k, v in sorted(tags.items())])

        # Store in cache (legacy behavior, 24hr TTL)
        current = cache.get(cache_key, 0)
        cache.set(cache_key, current + 1, timeout=SECONDS_IN_HOUR * 24)

        # OBSERVABILITY: Export to Prometheus
        if PROMETHEUS_ENABLED:
            try:
                prometheus.increment_counter(
                    f"celery_{metric_name}_total",
                    labels=tags,
                    help_text=f"Total count of {metric_name} events"
                )
            except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                logger.debug(f"Failed to record Prometheus counter: {e}", exc_info=True)

    @staticmethod
    def record_timing(metric_name: str, duration_ms: float, tags: Dict[str, str] = None):
        """
        Record timing metric (duration).

        Metrics are stored in both Redis cache (histogram) and Prometheus.

        Args:
            metric_name: Name of the timing metric
            duration_ms: Duration in milliseconds
            tags: Optional tags/labels dictionary
        """
        tags = tags or {}
        cache_key = f"task_timing:{metric_name}"
        if tags:
            cache_key += ":" + ":".join([f"{k}={v}" for k, v in sorted(tags.items())])

        # Store in cache (legacy behavior, last 1000 measurements)
        timings = cache.get(cache_key, [])
        timings.append(duration_ms)

        # Keep only last 1000 measurements
        if len(timings) > 1000:
            timings = timings[-1000:]

        cache.set(cache_key, timings, timeout=SECONDS_IN_HOUR * 24)

        # OBSERVABILITY: Export to Prometheus as histogram
        if PROMETHEUS_ENABLED:
            try:
                # Convert milliseconds to seconds for Prometheus convention
                duration_seconds = duration_ms / 1000.0
                prometheus.observe_histogram(
                    f"celery_{metric_name}_seconds",
                    duration_seconds,
                    labels=tags,
                    help_text=f"Duration histogram for {metric_name} in seconds"
                )
            except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                logger.debug(f"Failed to record Prometheus histogram: {e}", exc_info=True)

    @staticmethod
    def record_retry(task_name: str, reason: str, retry_count: int):
        """
        Record task retry in both cache and Prometheus.

        Observability Enhancement (2025-10-01):
        Tracks retries by:
        - Task name
        - Retry reason (network_error, database_error, rate_limit, etc.)
        - Retry attempt number

        Args:
            task_name: Name of the Celery task
            reason: Reason for retry (exception type or custom reason)
            retry_count: Current retry attempt number
        """
        # Record in cache (existing behavior)
        TaskMetrics.increment_counter('task_retries', {'task': task_name, 'reason': reason})

        # OBSERVABILITY: Record in Prometheus
        if PROMETHEUS_ENABLED:
            try:
                prometheus.increment_counter(
                    'celery_task_retries_total',
                    labels={
                        'task_name': task_name,
                        'reason': reason,
                        'retry_attempt': str(min(retry_count, 10))  # Cap at 10 for cardinality
                    },
                    help_text='Total number of Celery task retries by task and reason'
                )

                logger.debug(
                    f"Recorded Prometheus retry metric: task={task_name}, "
                    f"reason={reason}, attempt={retry_count}"
                )

            except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
                # Don't fail task execution if metrics fail
                logger.warning(f"Failed to record Prometheus retry metric: {e}")


class CircuitBreaker:
    """Circuit breaker pattern for external service calls"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

    def is_circuit_open(self, service_name: str) -> bool:
        """Check if circuit is open for a service"""
        cache_key = f"circuit_breaker:{service_name}"
        circuit_data = cache.get(cache_key, {'failures': 0, 'last_failure': None})

        if circuit_data['failures'] >= self.failure_threshold:
            if circuit_data.get('last_failure'):
                time_since_failure = time.time() - circuit_data['last_failure']
                return time_since_failure < self.recovery_timeout

        return False

    def record_success(self, service_name: str):
        """Record successful call"""
        cache_key = f"circuit_breaker:{service_name}"
        cache.delete(cache_key)

    def record_failure(self, service_name: str):
        """Record failed call"""
        cache_key = f"circuit_breaker:{service_name}"
        circuit_data = cache.get(cache_key, {'failures': 0, 'last_failure': None})
        circuit_data['failures'] += 1
        circuit_data['last_failure'] = time.time()
        cache.set(cache_key, circuit_data, timeout=SECONDS_IN_HOUR * 24)


class BaseTask(Task):
    """
    Base class for all Celery tasks with comprehensive error handling,
    retry logic, and monitoring capabilities.
    """

    # Default configuration
    max_retries = 3
    default_retry_delay = 60  # seconds
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max delay
    retry_jitter = True

    # Monitoring configuration
    track_started = True
    send_events = True

    def __init__(self):
        super().__init__()
        self.circuit_breaker = CircuitBreaker()

    def retry(self, args=None, kwargs=None, exc=None, throw=True, eta=None, countdown=None, max_retries=None, **options):
        """Enhanced retry with exponential backoff and jitter"""
        if countdown is None and eta is None:
            # Calculate exponential backoff with jitter
            retry_count = self.request.retries
            base_delay = self.default_retry_delay

            if self.retry_backoff:
                delay = min(base_delay * (2 ** retry_count), self.retry_backoff_max)

                if self.retry_jitter:
                    import random
                    delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay

                countdown = delay

        # Log retry attempt
        logger.warning(
            f"Task {self.name} retrying (attempt {self.request.retries + 1}/{self.max_retries}): {exc}",
            extra={
                'task_id': self.request.id,
                'task_name': self.name,
                'retry_count': self.request.retries,
                'exception': str(exc) if exc else None
            }
        )

        # Record retry metric
        TaskMetrics.increment_counter('task_retry', {
            'task_name': self.name,
            'retry_count': str(self.request.retries + 1)
        })

        return super().retry(args, kwargs, exc, throw, eta, countdown, max_retries, **options)

    def on_success(self, retval, task_id, args, kwargs):
        """Called on successful task completion"""
        execution_time = getattr(self, '_start_time', None)
        if execution_time:
            duration_ms = (time.time() - execution_time) * 1000
            TaskMetrics.record_timing('task_duration', duration_ms, {'task_name': self.name})

        TaskMetrics.increment_counter('task_success', {'task_name': self.name})

        logger.info(
            f"Task {self.name} completed successfully",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'execution_time_ms': getattr(self, '_start_time', None) and (time.time() - self._start_time) * 1000
            }
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure after all retries exhausted"""
        execution_time = getattr(self, '_start_time', None)
        if execution_time:
            duration_ms = (time.time() - execution_time) * 1000
            TaskMetrics.record_timing('task_duration', duration_ms, {'task_name': self.name, 'status': 'failed'})

        TaskMetrics.increment_counter('task_failure', {'task_name': self.name})

        logger.error(
            f"Task {self.name} failed permanently after {self.request.retries} retries: {exc}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'exception': str(exc),
                'traceback': einfo.traceback,
                'args': args,
                'kwargs': kwargs
            }
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry"""
        logger.info(
            f"Task {self.name} scheduled for retry: {exc}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'retry_count': self.request.retries,
                'exception': str(exc)
            }
        )

    def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                   link=None, link_error=None, shadow=None, **options):
        """Enhanced apply_async with task context"""
        # Add default task metadata
        if 'headers' not in options:
            options['headers'] = {}

        options['headers'].update({
            'task_class': self.__class__.__name__,
            'created_at': get_current_utc().isoformat(),
            'source': 'background_task'
        })

        return super().apply_async(args, kwargs, task_id, producer, link, link_error, shadow, **options)

    @contextmanager
    def task_context(self, **context):
        """Context manager for task execution with automatic cleanup"""
        task_start_time = time.time()
        self._start_time = task_start_time

        # Log task start
        logger.info(
            f"Task {self.name} started",
            extra={
                'task_id': self.request.id,
                'task_name': self.name,
                'context': context
            }
        )

        TaskMetrics.increment_counter('task_started', {'task_name': self.name})

        try:
            yield context
        except Exception as exc:
            # Handle specific exception types
            if isinstance(exc, (DatabaseError, IntegrityError)):
                logger.error(f"Database error in task {self.name}: {exc}")
                raise self.retry(exc=exc, countdown=60)

            elif isinstance(exc, ConnectionError):
                logger.error(f"Connection error in task {self.name}: {exc}")
                raise self.retry(exc=exc, countdown=30)

            else:
                # Log unexpected exceptions
                logger.error(
                    f"Unexpected error in task {self.name}: {exc}",
                    extra={
                        'task_id': self.request.id,
                        'task_name': self.name,
                        'exception_type': exc.__class__.__name__,
                        'traceback': traceback.format_exc()
                    }
                )
                raise


class EmailTask(BaseTask):
    """Specialized base class for email-related tasks"""

    # Email-specific retry configuration
    max_retries = 5
    default_retry_delay = 120  # 2 minutes
    autoretry_for = (ConnectionError, OSError)

    def validate_email_data(self, **email_data):
        """Validate email data before sending"""
        required_fields = ['recipient', 'subject']
        for field in required_fields:
            if field not in email_data or not email_data[field]:
                raise ValueError(f"Missing required email field: {field}")

        # Sanitize email addresses
        from apps.core.utils_new.form_security import InputSanitizer
        if isinstance(email_data['recipient'], list):
            email_data['recipient'] = [InputSanitizer.sanitize_email(email) for email in email_data['recipient']]
        else:
            email_data['recipient'] = InputSanitizer.sanitize_email(email_data['recipient'])

        return email_data


class ExternalServiceTask(BaseTask):
    """Specialized base class for tasks that call external services"""

    # External service specific configuration
    max_retries = 2
    default_retry_delay = 300  # 5 minutes
    autoretry_for = (ConnectionError, OSError, TimeoutError)

    def __init__(self):
        super().__init__()
        self.service_name = None

    @contextmanager
    def external_service_call(self, service_name: str, timeout: int = 30):
        """Context manager for external service calls with circuit breaker"""
        self.service_name = service_name

        # Check circuit breaker
        if self.circuit_breaker.is_circuit_open(service_name):
            logger.error(f"Circuit breaker open for service: {service_name}")
            raise ConnectionError(f"Circuit breaker open for {service_name}")

        start_time = time.time()
        try:
            yield

            # Record success
            self.circuit_breaker.record_success(service_name)
            duration_ms = (time.time() - start_time) * 1000
            TaskMetrics.record_timing('external_service_call', duration_ms, {'service': service_name, 'status': 'success'})

        except Exception as exc:
            # Record failure
            self.circuit_breaker.record_failure(service_name)
            duration_ms = (time.time() - start_time) * 1000
            TaskMetrics.record_timing('external_service_call', duration_ms, {'service': service_name, 'status': 'failed'})

            logger.error(f"External service call failed: {service_name} - {exc}")
            raise self.retry(exc=exc)


class ReportTask(BaseTask):
    """Specialized base class for report generation tasks"""

    # Report-specific configuration
    max_retries = 2
    default_retry_delay = 300
    soft_time_limit = 1800  # 30 minutes
    time_limit = 3600       # 1 hour

    def cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files created during report generation"""
        import os
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up temp file: {file_path}")
            except Exception as exc:
                logger.warning(f"Failed to clean up temp file {file_path}: {exc}")


class MaintenanceTask(BaseTask):
    """Specialized base class for maintenance and cleanup tasks"""

    # Maintenance-specific configuration
    max_retries = 1
    default_retry_delay = 3600  # 1 hour
    soft_time_limit = 3600      # 1 hour
    time_limit = 7200           # 2 hours

    def batch_process(self, items: List[Any], batch_size: int = 100, process_func=None):
        """Process items in batches with progress tracking"""
        if not process_func:
            raise ValueError("process_func is required")

        total_items = len(items)
        processed = 0
        failed = 0

        logger.info(f"Starting batch processing of {total_items} items in batches of {batch_size}")

        for i in range(0, total_items, batch_size):
            batch = items[i:i + batch_size]

            try:
                with transaction.atomic():
                    for item in batch:
                        try:
                            process_func(item)
                            processed += 1
                        except Exception as exc:
                            failed += 1
                            logger.warning(f"Failed to process item {item}: {exc}")

                # Log progress every 10 batches
                if (i // batch_size) % 10 == 0:
                    progress = (i + len(batch)) / total_items * 100
                    logger.info(f"Batch processing progress: {progress:.1f}% ({processed} processed, {failed} failed)")

            except Exception as exc:
                logger.error(f"Batch processing failed for batch starting at index {i}: {exc}")
                failed += len(batch)

        logger.info(f"Batch processing completed: {processed} processed, {failed} failed")
        return {'processed': processed, 'failed': failed}


class IdempotentTask(BaseTask):
    """
    Base class with automatic idempotency for all tasks.

    Prevents duplicate execution of tasks with the same parameters.
    Uses UniversalIdempotencyService for Redis-based caching with
    database fallback.

    Configuration attributes:
        idempotency_enabled (bool): Enable/disable idempotency (default: True)
        idempotency_ttl (int): Cache duration in seconds (default: 3600)
        idempotency_scope (str): Scope level - 'global', 'user', 'tenant' (default: 'global')
        idempotency_key_prefix (str): Custom prefix for idempotency keys

    Usage:
        @shared_task(base=IdempotentTask)
        def my_task(data):
            # Task logic - automatically protected from duplicates
            return result

        # With custom configuration
        @shared_task(base=IdempotentTask, idempotency_ttl=7200)
        def long_running_task(data):
            return result

    Implementation:
        1. Before execution: Check if task already executed
        2. If duplicate: Return cached result immediately
        3. If new: Execute task and cache result
        4. On error: Cache error (short TTL) to prevent retry storms
    """

    # Default configuration
    idempotency_enabled = True
    idempotency_ttl = SECONDS_IN_HOUR  # 1 hour default
    idempotency_scope = 'global'
    idempotency_key_prefix = ''

    def __init__(self):
        super().__init__()
        # Lazy import to avoid circular dependency
        from apps.core.tasks.idempotency_service import UniversalIdempotencyService
        self.idempotency_service = UniversalIdempotencyService

    def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                   link=None, link_error=None, shadow=None, **options):
        """
        Enhanced apply_async with idempotency checking before task queuing.

        Checks idempotency BEFORE queuing the task to prevent unnecessary
        worker load for duplicate requests.
        """
        # Skip idempotency if disabled
        if not self.idempotency_enabled:
            return super().apply_async(
                args, kwargs, task_id, producer, link, link_error, shadow, **options
            )

        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(args, kwargs)

        # Check for duplicate
        cached_result = self.idempotency_service.check_duplicate(idempotency_key)
        if cached_result is not None:
            logger.info(
                f"Duplicate task detected before queuing: {self.name}",
                extra={
                    'task_name': self.name,
                    'idempotency_key': idempotency_key[:32],
                    'cached_result_status': cached_result.get('status', 'unknown')
                }
            )
            # Return mock AsyncResult with cached data
            return self._create_mock_result(task_id or idempotency_key, cached_result)

        # Add idempotency metadata to task headers
        if 'headers' not in options:
            options['headers'] = {}

        options['headers'].update({
            'idempotency_key': idempotency_key,
            'idempotency_enabled': True,
            'idempotency_ttl': self.idempotency_ttl
        })

        return super().apply_async(
            args, kwargs, task_id, producer, link, link_error, shadow, **options
        )

    def __call__(self, *args, **kwargs):
        """
        Execute task with idempotency protection.

        This is called when task actually runs on worker.
        """
        # Skip idempotency if disabled
        if not self.idempotency_enabled:
            return super().__call__(*args, **kwargs)

        # Get idempotency key from headers or generate
        idempotency_key = self.request.get('idempotency_key') or \
                         self._generate_idempotency_key(args, kwargs)

        # Double-check for duplicate (in case queued before check)
        cached_result = self.idempotency_service.check_duplicate(idempotency_key)
        if cached_result is not None:
            logger.info(
                f"Duplicate task detected during execution: {self.name}",
                extra={
                    'task_id': self.request.id,
                    'task_name': self.name,
                    'idempotency_key': idempotency_key[:32]
                }
            )
            return cached_result.get('result')

        # Execute task with result caching
        try:
            result = super().__call__(*args, **kwargs)

            # Cache successful result
            self.idempotency_service.store_result(
                idempotency_key,
                {
                    'result': result,
                    'status': 'success',
                    'task_id': self.request.id,
                    'executed_at': get_current_utc().isoformat()
                },
                ttl_seconds=self.idempotency_ttl,
                task_name=self.name
            )

            logger.debug(
                f"Cached task result: {self.name}",
                extra={'idempotency_key': idempotency_key[:32]}
            )

            return result

        except Exception as exc:
            # Cache error with shorter TTL to allow retries
            error_ttl = min(self.idempotency_ttl, SECONDS_IN_HOUR)

            self.idempotency_service.store_result(
                idempotency_key,
                {
                    'error': str(exc),
                    'status': 'failed',
                    'task_id': self.request.id,
                    'failed_at': get_current_utc().isoformat()
                },
                ttl_seconds=error_ttl,
                task_name=self.name
            )

            logger.error(
                f"Cached task error: {self.name}",
                extra={
                    'idempotency_key': idempotency_key[:32],
                    'error': str(exc)
                }
            )

            raise

    def _generate_idempotency_key(self, args: tuple, kwargs: dict) -> str:
        """Generate idempotency key for task arguments"""
        prefix = self.idempotency_key_prefix or self.name
        return self.idempotency_service.generate_task_key(
            prefix, args, kwargs, self.idempotency_scope
        )

    def _create_mock_result(self, task_id: str, cached_data: dict):
        """Create mock AsyncResult for cached results"""
        from celery.result import AsyncResult

        # Create result object
        result = AsyncResult(task_id)

        # Inject cached data (this is a simplified mock)
        result._cache = cached_data

        return result
# Re-export utility functions for backward compatibility
from .utils import log_task_context
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

__all__ = ['BaseTask', 'IdempotentTask', 'EmailTask', 'ExternalServiceTask', 
           'MaintenanceTask', 'CriticalTask', 'TaskMetrics', 'log_task_context']
