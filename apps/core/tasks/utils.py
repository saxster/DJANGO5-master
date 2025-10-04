"""
Task Utilities and Helper Functions

Provides utility functions for task configuration, argument sanitization,
retry policies, and common task patterns.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from functools import wraps

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from celery.schedules import crontab

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR


logger = logging.getLogger('celery.tasks.utils')


# Standard retry policies for common scenarios
RETRY_POLICIES = {
    'default': {
        'max_retries': 3,
        'default_retry_delay': 60,
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': True,
        'autoretry_for': (ConnectionError, TimeoutError)
    },

    'email': {
        'max_retries': 5,
        'default_retry_delay': 120,
        'retry_backoff': True,
        'retry_backoff_max': 1800,
        'retry_jitter': True,
        'autoretry_for': (ConnectionError, OSError, SMTPException)
    },

    'external_api': {
        'max_retries': 2,
        'default_retry_delay': 300,
        'retry_backoff': True,
        'retry_backoff_max': 900,
        'retry_jitter': True,
        'autoretry_for': (ConnectionError, TimeoutError, OSError)
    },

    'database_heavy': {
        'max_retries': 2,
        'default_retry_delay': 180,
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': False,
        'autoretry_for': (DatabaseError, IntegrityError)
    },

    'maintenance': {
        'max_retries': 1,
        'default_retry_delay': 3600,
        'retry_backoff': False,
        'retry_jitter': False,
        'autoretry_for': ()
    }
}


def task_retry_policy(policy_name: str = 'default') -> Dict[str, Any]:
    """
    Get standardized retry policy configuration for tasks.

    Args:
        policy_name: Name of the retry policy ('default', 'email', 'external_api', etc.)

    Returns:
        Dictionary with retry configuration parameters

    Usage:
        @shared_task(**task_retry_policy('email'))
        def send_email_task():
            pass
    """
    if policy_name not in RETRY_POLICIES:
        logger.warning(f"Unknown retry policy '{policy_name}', using 'default'")
        policy_name = 'default'

    return RETRY_POLICIES[policy_name].copy()


def sanitize_task_args(*args, **kwargs) -> tuple:
    """
    Sanitize task arguments to ensure they're serializable and safe.

    Removes or converts non-serializable objects, truncates large strings,
    and sanitizes sensitive data.

    Returns:
        Tuple of (sanitized_args, sanitized_kwargs)
    """
    max_string_length = 10000  # Truncate very long strings

    def sanitize_value(value):
        if isinstance(value, (str, int, float, bool, type(None))):
            if isinstance(value, str) and len(value) > max_string_length:
                return value[:max_string_length] + '...[truncated]'
            return value

        elif isinstance(value, (list, tuple)):
            return [sanitize_value(item) for item in value]

        elif isinstance(value, dict):
            return {k: sanitize_value(v) for k, v in value.items()}

        elif hasattr(value, '__dict__'):
            # Convert objects to their string representation
            return str(value)

        else:
            return str(value)

    sanitized_args = [sanitize_value(arg) for arg in args]
    sanitized_kwargs = {k: sanitize_value(v) for k, v in kwargs.items()}

    return sanitized_args, sanitized_kwargs


def validate_email_recipients(recipients: Union[str, List[str]]) -> List[str]:
    """
    Validate and sanitize email recipients.

    Args:
        recipients: Single email or list of email addresses

    Returns:
        List of validated email addresses

    Raises:
        ValidationError: If any email address is invalid
    """
    if isinstance(recipients, str):
        recipients = [recipients]

    validated_recipients = []
    for email in recipients:
        try:
            validate_email(email)
            # Additional sanitization
            email = email.strip().lower()
            if email not in validated_recipients:
                validated_recipients.append(email)
        except ValidationError as e:
            logger.error(f"Invalid email address: {email} - {e}")
            raise ValidationError(f"Invalid email address: {email}")

    return validated_recipients


def create_scheduled_task_config(
    task_name: str,
    schedule: Union[crontab, timedelta, int],
    queue: str = 'default',
    expires: Optional[int] = None,
    **task_kwargs
) -> Dict[str, Any]:
    """
    Create a standardized configuration for scheduled tasks (Celery Beat).

    Args:
        task_name: Name of the task to schedule
        schedule: Schedule configuration (crontab, timedelta, or seconds)
        queue: Queue to route the task to
        expires: Task expiration time in seconds
        **task_kwargs: Additional task options

    Returns:
        Dictionary ready for use in CELERY_BEAT_SCHEDULE

    Usage:
        CELERY_BEAT_SCHEDULE = {
            'cleanup-old-files': create_scheduled_task_config(
                'background_tasks.maintenance.cleanup_old_files',
                crontab(hour=2, minute=0),  # Run daily at 2 AM
                queue='maintenance',
                expires=3600
            )
        }
    """
    config = {
        'task': task_name,
        'schedule': schedule,
        'options': {
            'queue': queue,
            'expires': expires or SECONDS_IN_HOUR,
            **task_kwargs
        }
    }

    return config


def task_performance_decorator(metric_name: str):
    """
    Decorator to automatically track task performance metrics.

    Args:
        metric_name: Name of the metric to track

    Usage:
        @task_performance_decorator('email_processing')
        @shared_task
        def process_email():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from .base import TaskMetrics

            start_time = timezone.now()
            try:
                result = func(*args, **kwargs)

                # Record success
                TaskMetrics.increment_counter(f'{metric_name}_success')
                duration = (timezone.now() - start_time).total_seconds() * 1000
                TaskMetrics.record_timing(f'{metric_name}_duration', duration)

                return result

            except Exception as exc:
                # Record failure
                TaskMetrics.increment_counter(f'{metric_name}_failure')
                duration = (timezone.now() - start_time).total_seconds() * 1000
                TaskMetrics.record_timing(f'{metric_name}_duration', duration, {'status': 'failed'})

                raise

        return wrapper
    return decorator


def batch_task_processor(
    items: List[Any],
    process_function: Callable,
    batch_size: int = 100,
    delay_between_batches: float = 0.1
) -> Dict[str, int]:
    """
    Process a list of items in batches with optional delays.

    Args:
        items: List of items to process
        process_function: Function to process each item
        batch_size: Number of items per batch
        delay_between_batches: Delay in seconds between batches

    Returns:
        Dictionary with processing statistics
    """
    import time

    total_items = len(items)
    processed = 0
    failed = 0

    logger.info(f"Starting batch processing of {total_items} items (batch_size={batch_size})")

    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]

        for item in batch:
            try:
                process_function(item)
                processed += 1
            except Exception as exc:
                failed += 1
                logger.error(f"Failed to process item: {exc}")

        # Progress logging
        if i > 0 and i % (batch_size * 10) == 0:
            progress = (i / total_items) * 100
            logger.info(f"Batch processing progress: {progress:.1f}%")

        # Delay between batches to prevent overwhelming the system
        if delay_between_batches > 0 and i + batch_size < total_items:
            time.sleep(delay_between_batches)

    logger.info(f"Batch processing completed: {processed} processed, {failed} failed")
    return {'total': total_items, 'processed': processed, 'failed': failed}


def create_task_signature(
    task_name: str,
    args: List[Any] = None,
    kwargs: Dict[str, Any] = None,
    queue: str = 'default',
    countdown: int = None,
    eta: datetime = None,
    expires: int = None,
    retry: bool = True,
    retry_policy: str = 'default'
) -> Dict[str, Any]:
    """
    Create a standardized task signature for delayed execution.

    Args:
        task_name: Name of the task
        args: Task arguments
        kwargs: Task keyword arguments
        queue: Queue to route task to
        countdown: Delay before execution (seconds)
        eta: Specific execution time
        expires: Task expiration time (seconds)
        retry: Whether to enable retries
        retry_policy: Retry policy to use

    Returns:
        Task signature dictionary
    """
    signature = {
        'task': task_name,
        'args': args or [],
        'kwargs': kwargs or {},
        'options': {
            'queue': queue,
        }
    }

    if countdown:
        signature['options']['countdown'] = countdown

    if eta:
        signature['options']['eta'] = eta

    if expires:
        signature['options']['expires'] = expires

    if retry:
        signature['options'].update(task_retry_policy(retry_policy))

    return signature


def log_task_context(task_name: str, **context):
    """
    Log task execution context in a standardized format.

    Args:
        task_name: Name of the executing task
        **context: Additional context information
    """
    logger.info(
        f"Task context: {task_name}",
        extra={
            'task_name': task_name,
            'timestamp': timezone.now().isoformat(),
            **context
        }
    )


def get_task_queue_stats() -> Dict[str, Any]:
    """
    Get statistics about task queues (if available).

    Returns:
        Dictionary with queue statistics
    """
    try:
        from django_celery_results.models import TaskResult
        from django.db.models import Count, Q
        from datetime import timedelta

        # Get task statistics from the last 24 hours
        since = timezone.now() - timedelta(hours=24)

        stats = TaskResult.objects.filter(date_created__gte=since).aggregate(
            total_tasks=Count('id'),
            successful_tasks=Count('id', filter=Q(status='SUCCESS')),
            failed_tasks=Count('id', filter=Q(status='FAILURE')),
            pending_tasks=Count('id', filter=Q(status='PENDING')),
            retry_tasks=Count('id', filter=Q(status='RETRY'))
        )

        # Calculate success rate
        total = stats['total_tasks'] or 1
        stats['success_rate'] = (stats['successful_tasks'] / total) * 100

        return stats

    except Exception as exc:
        logger.error(f"Failed to get task queue stats: {exc}")
        return {'error': str(exc)}


# Import exceptions that might be needed
try:
    from smtplib import SMTPException
    from django.db import DatabaseError, IntegrityError
except ImportError:
    # Define dummy exceptions if not available
    class SMTPException(Exception):
        pass

    class DatabaseError(Exception):
        pass

    class IntegrityError(Exception):
        pass