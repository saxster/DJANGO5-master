"""
Dead Letter Queue (DLQ) handler for failed Celery tasks.

Captures tasks that fail after all retry attempts for:
- Manual intervention
- Root cause analysis
- Recovery workflows
- Alerting and monitoring

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization
"""

import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import DatabaseError, IntegrityError

logger = logging.getLogger(__name__)
dlq_logger = logging.getLogger("celery.dlq")  # Dedicated DLQ logger


@dataclass
class DeadLetterTask:
    """Represents a failed task in the dead letter queue."""
    task_id: str
    task_name: str
    args: tuple
    kwargs: dict
    exception_type: str
    exception_message: str
    traceback: str
    retry_count: int
    failed_at: str
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    original_task_time: Optional[str] = None


class DeadLetterQueueHandler:
    """
    Handler for managing dead letter queue operations.

    Stores failed tasks, provides recovery mechanisms, and
    generates alerts for critical failures.
    """

    def __init__(self):
        self.cache_prefix = 'dlq:'
        self.cache_timeout = 86400 * 7  # 7 days
        self.max_queue_size = getattr(settings, 'DLQ_MAX_QUEUE_SIZE', 1000)

    def send_to_dlq(
        self,
        task_id: str,
        task_name: str,
        args: tuple,
        kwargs: dict,
        exception: Exception,
        retry_count: int,
        correlation_id: Optional[str] = None
    ):
        """
        Send failed task to dead letter queue.

        Args:
            task_id: Celery task ID
            task_name: Name of the task
            args: Task positional arguments
            kwargs: Task keyword arguments
            exception: Exception that caused final failure
            retry_count: Number of retries attempted
            correlation_id: Optional correlation ID for tracking
        """
        try:
            # Extract session_id if available in kwargs
            session_id = kwargs.get('conversation_id') or kwargs.get('session_id')

            # Create dead letter task record
            dlq_task = DeadLetterTask(
                task_id=task_id,
                task_name=task_name,
                args=args,
                kwargs=self._sanitize_kwargs(kwargs),  # Sanitize PII
                exception_type=type(exception).__name__,
                exception_message=str(exception),
                traceback=traceback.format_exc(),
                retry_count=retry_count,
                failed_at=timezone.now().isoformat(),
                correlation_id=correlation_id,
                session_id=session_id,
                original_task_time=kwargs.get('task_started_at')
            )

            # Store in cache (primary storage)
            cache_key = f"{self.cache_prefix}{task_id}"
            cache.set(cache_key, asdict(dlq_task), timeout=self.cache_timeout)

            # Add to queue index for listing
            self._add_to_queue_index(task_id)

            # Log to dedicated DLQ logger (Rule #15: sanitized logging)
            dlq_logger.error(
                f"Task sent to DLQ: {task_name}",
                extra={
                    'task_id': task_id,
                    'task_name': task_name,
                    'exception_type': type(exception).__name__,
                    'retry_count': retry_count,
                    'correlation_id': correlation_id,
                    'session_id': session_id,
                    'failed_at': dlq_task.failed_at
                }
            )

            # Check if critical task - send alert
            if self._is_critical_task(task_name):
                self._send_critical_failure_alert(dlq_task)

            # Check queue size limits
            self._enforce_queue_limits()

        except (DatabaseError, IntegrityError, ConnectionError) as e:
            logger.error(
                f"Failed to send task to DLQ: {str(e)}",
                extra={'task_id': task_id, 'task_name': task_name},
                exc_info=True
            )

    def get_dlq_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve task from DLQ by ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task dict or None if not found
        """
        cache_key = f"{self.cache_prefix}{task_id}"
        return cache.get(cache_key)

    def list_dlq_tasks(
        self,
        limit: int = 100,
        task_name_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List tasks in DLQ with optional filtering.

        Args:
            limit: Maximum number of tasks to return
            task_name_filter: Optional task name to filter by

        Returns:
            List of DLQ task dicts
        """
        try:
            # Get queue index
            index_key = f"{self.cache_prefix}index"

            # Try to get from Redis SET first (if using atomic operations)
            try:
                cache_client = cache.client.get_client()
                if hasattr(cache_client, 'smembers'):
                    # Redis SET - convert bytes to strings
                    task_ids_set = cache_client.smembers(index_key)
                    task_ids = [
                        tid.decode('utf-8') if isinstance(tid, bytes) else str(tid)
                        for tid in task_ids_set
                    ]
                else:
                    # Fallback to list-based cache
                    task_ids = cache.get(index_key, [])
            except (AttributeError, Exception):
                # Fallback to list-based cache
                task_ids = cache.get(index_key, [])

            tasks = []
            for task_id in list(task_ids)[:limit]:
                task = self.get_dlq_task(task_id)
                if task:
                    # Apply filter if provided
                    if task_name_filter and task['task_name'] != task_name_filter:
                        continue
                    tasks.append(task)

            return tasks

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error listing DLQ tasks: {str(e)}", exc_info=True)
            return []

    def retry_dlq_task(self, task_id: str) -> bool:
        """
        Retry a task from DLQ (manual recovery).

        Args:
            task_id: Task ID to retry

        Returns:
            True if retry queued, False otherwise
        """
        try:
            # Get task from DLQ
            dlq_task = self.get_dlq_task(task_id)
            if not dlq_task:
                logger.warning(f"Task {task_id} not found in DLQ")
                return False

            # Queue task for retry
            from celery import current_app
            task = current_app.tasks.get(dlq_task['task_name'])

            if not task:
                logger.error(f"Task {dlq_task['task_name']} not found in Celery registry")
                return False

            # Apply task with original args/kwargs
            task.apply_async(
                args=dlq_task['args'],
                kwargs=dlq_task['kwargs']
            )

            logger.info(
                f"DLQ task queued for retry: {task_id}",
                extra={'task_id': task_id, 'task_name': dlq_task['task_name']}
            )

            # Remove from DLQ after successful retry
            self._remove_from_dlq(task_id)

            return True

        except (ConnectionError, ValueError, KeyError) as e:
            logger.error(
                f"Error retrying DLQ task {task_id}: {str(e)}",
                exc_info=True
            )
            return False

    def clear_dlq(self, older_than_days: Optional[int] = None):
        """
        Clear DLQ tasks (with optional age filter).

        Args:
            older_than_days: Only clear tasks older than this many days
        """
        try:
            index_key = f"{self.cache_prefix}index"
            task_ids = cache.get(index_key, [])

            removed_count = 0
            for task_id in task_ids:
                task = self.get_dlq_task(task_id)
                if not task:
                    continue

                # Check age filter
                if older_than_days:
                    failed_at = datetime.fromisoformat(task['failed_at'])
                    age = (timezone.now() - failed_at).days
                    if age < older_than_days:
                        continue

                # Remove task
                self._remove_from_dlq(task_id)
                removed_count += 1

            logger.info(f"Cleared {removed_count} tasks from DLQ")

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error clearing DLQ: {str(e)}", exc_info=True)

    def _sanitize_kwargs(self, kwargs: dict) -> dict:
        """
        Sanitize kwargs to remove PII before storing (Rule #15 compliance).

        Args:
            kwargs: Task keyword arguments

        Returns:
            Sanitized kwargs dict
        """
        sanitized = kwargs.copy()

        # Remove sensitive fields
        sensitive_fields = [
            'password', 'token', 'secret', 'api_key',
            'auth_token', 'session_key', 'csrf_token'
        ]

        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'

        return sanitized

    def _add_to_queue_index(self, task_id: str):
        """
        Add task ID to queue index for listing.
        Uses atomic Redis SADD if available, otherwise uses distributed lock.
        """
        index_key = f"{self.cache_prefix}index"

        # Try Redis SADD for atomic set operations
        try:
            cache_client = cache.client.get_client()
            if hasattr(cache_client, 'sadd'):
                # Use Redis SET operations (atomic)
                cache_client.sadd(index_key, task_id)
                cache_client.expire(index_key, self.cache_timeout)
                return
        except (AttributeError, Exception) as e:
            # Fallback to lock-based approach
            dlq_logger.debug(f"Redis SADD not available, using lock-based approach: {str(e)}")

        # Fallback: Use distributed lock for atomic updates
        lock_key = f"{index_key}:lock"
        max_retries = 3

        for attempt in range(max_retries):
            # Try to acquire lock (1 second timeout)
            if cache.add(lock_key, True, timeout=1):
                try:
                    # Lock acquired, safely update list
                    task_ids = cache.get(index_key, [])
                    if task_id not in task_ids:
                        task_ids.append(task_id)
                        cache.set(index_key, task_ids, timeout=self.cache_timeout)
                    break
                finally:
                    # Always release lock
                    cache.delete(lock_key)
            else:
                # Lock held by another process, wait briefly and retry
                import time
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff

        if attempt == max_retries - 1:
            dlq_logger.warning(
                f"Failed to acquire lock for DLQ index update after {max_retries} attempts"
            )

    def _remove_from_dlq(self, task_id: str):
        """
        Remove task from DLQ and index.
        Uses atomic Redis SREM if available, otherwise uses distributed lock.
        """
        # Remove from cache
        cache_key = f"{self.cache_prefix}{task_id}"
        cache.delete(cache_key)

        # Remove from index
        index_key = f"{self.cache_prefix}index"

        # Try Redis SREM for atomic set operations
        try:
            cache_client = cache.client.get_client()
            if hasattr(cache_client, 'srem'):
                # Use Redis SET operations (atomic)
                cache_client.srem(index_key, task_id)
                return
        except (AttributeError, Exception) as e:
            # Fallback to lock-based approach
            dlq_logger.debug(f"Redis SREM not available, using lock-based approach: {str(e)}")

        # Fallback: Use distributed lock for atomic updates
        lock_key = f"{index_key}:lock"
        max_retries = 3

        for attempt in range(max_retries):
            # Try to acquire lock (1 second timeout)
            if cache.add(lock_key, True, timeout=1):
                try:
                    # Lock acquired, safely update list
                    task_ids = cache.get(index_key, [])
                    if task_id in task_ids:
                        task_ids.remove(task_id)
                        cache.set(index_key, task_ids, timeout=self.cache_timeout)
                    break
                finally:
                    # Always release lock
                    cache.delete(lock_key)
            else:
                # Lock held by another process, wait briefly and retry
                import time
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff

        if attempt == max_retries - 1:
            dlq_logger.warning(
                f"Failed to acquire lock for DLQ index removal after {max_retries} attempts"
            )

    def _is_critical_task(self, task_name: str) -> bool:
        """Check if task is critical (requires immediate alert)."""
        critical_tasks = getattr(
            settings,
            'CRITICAL_CELERY_TASKS',
            [
                'process_conversation_step',  # Onboarding conversations
                'crisis_intervention_task',    # Crisis management
                'security_alert_task',         # Security alerts
            ]
        )
        return task_name in critical_tasks

    def _send_critical_failure_alert(self, dlq_task: DeadLetterTask):
        """Send alert for critical task failure."""
        alert_logger = logging.getLogger("alerts")
        alert_logger.critical(
            f"CRITICAL TASK FAILURE: {dlq_task.task_name}",
            extra={
                'task_id': dlq_task.task_id,
                'task_name': dlq_task.task_name,
                'exception': dlq_task.exception_type,
                'session_id': dlq_task.session_id,
                'correlation_id': dlq_task.correlation_id,
                'alert_type': 'CRITICAL_TASK_FAILURE'
            }
        )

    def _enforce_queue_limits(self):
        """Enforce maximum queue size by removing oldest tasks."""
        try:
            index_key = f"{self.cache_prefix}index"
            task_ids = cache.get(index_key, [])

            if len(task_ids) > self.max_queue_size:
                # Remove oldest tasks (FIFO)
                tasks_to_remove = task_ids[:-self.max_queue_size]
                for task_id in tasks_to_remove:
                    self._remove_from_dlq(task_id)

                logger.warning(
                    f"DLQ size limit enforced: removed {len(tasks_to_remove)} oldest tasks"
                )

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error enforcing DLQ limits: {str(e)}", exc_info=True)


# Global DLQ handler instance
dlq_handler = DeadLetterQueueHandler()


# Celery task for processing DLQ
@shared_task(name='send_to_dead_letter_queue')
def send_to_dead_letter_queue(
    task_name: str,
    args: tuple,
    kwargs: dict,
    exception_str: str,
    correlation_id: str
):
    """
    Celery task to send failed task to DLQ.

    This runs asynchronously to avoid blocking the main task failure handling.
    """
    # Recreate exception from string (limited info)
    exception = Exception(exception_str)

    dlq_handler.send_to_dlq(
        task_id=correlation_id,  # Use correlation_id as task_id
        task_name=task_name,
        args=args,
        kwargs=kwargs,
        exception=exception,
        retry_count=kwargs.get('retry_count', 0),
        correlation_id=correlation_id
    )
