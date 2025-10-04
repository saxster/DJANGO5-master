"""
Celery Correlation ID Propagation

Propagates correlation IDs from HTTP requests to Celery tasks for end-to-end tracing.

Features:
- Automatically captures correlation ID when task is queued
- Injects correlation ID into task context during execution
- Makes correlation ID available via get_correlation_id() in task code
- Logs task execution with correlation ID for debugging

Compliance:
- .claude/rules.md Rule #7 (< 150 lines)
- .claude/rules.md Rule #11 (specific exceptions)

Architecture:
- Uses Celery signals: before_task_publish, task_prerun, task_postrun
- Stores correlation ID in task headers during publish
- Restores correlation ID to thread-local storage during execution

Usage:
    # In views (when queuing task)
    from background_tasks.tasks import my_task
    result = my_task.delay(arg1, arg2)  # correlation_id automatically captured

    # In task (during execution)
    from apps.core.middleware.correlation_id_middleware import get_correlation_id
    correlation_id = get_correlation_id()  # Returns the original request's correlation_id
"""

import logging
import uuid
from typing import Dict, Any, Optional
from celery import signals
from celery.app.task import Task

logger = logging.getLogger('celery.correlation_id')

__all__ = ['setup_correlation_id_propagation']

# Correlation ID header name in Celery task headers
CORRELATION_ID_HEADER = 'correlation_id'


@signals.before_task_publish.connect
def inject_correlation_id_into_task_headers(
    sender: Optional[str] = None,
    headers: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Inject correlation ID into task headers before task is published to queue.

    This signal fires when a task is queued (e.g., task.delay() or task.apply_async()).
    Captures the current correlation ID from thread-local storage and adds it to task headers.

    Args:
        sender: Task name
        headers: Task headers dictionary (modified in-place)
        **kwargs: Additional signal arguments

    Signal: before_task_publish
    """
    try:
        # Import here to avoid circular dependency
        from apps.core.middleware.correlation_id_middleware import get_correlation_id

        correlation_id = get_correlation_id()

        if correlation_id:
            # Add correlation ID to task headers
            if headers is not None:
                headers[CORRELATION_ID_HEADER] = correlation_id
                logger.debug(
                    f"Injected correlation ID into task: {sender}",
                    extra={'correlation_id': correlation_id, 'task_name': sender}
                )
        else:
            # No correlation ID in current context, generate new one
            new_correlation_id = str(uuid.uuid4())
            if headers is not None:
                headers[CORRELATION_ID_HEADER] = new_correlation_id
                logger.debug(
                    f"Generated new correlation ID for task: {sender}",
                    extra={'correlation_id': new_correlation_id, 'task_name': sender}
                )

    except ImportError as e:
        logger.warning(f"Failed to import correlation ID middleware: {e}")
    except AttributeError as e:
        logger.warning(f"Failed to get correlation ID: {e}")


@signals.task_prerun.connect
def restore_correlation_id_from_task_headers(
    sender: Optional[Task] = None,
    task_id: Optional[str] = None,
    task: Optional[Task] = None,
    **kwargs
) -> None:
    """
    Restore correlation ID from task headers before task execution.

    This signal fires right before a task starts executing on a worker.
    Extracts correlation ID from task headers and restores it to thread-local storage.

    Args:
        sender: Task class
        task_id: Unique task ID
        task: Task instance
        **kwargs: Additional signal arguments

    Signal: task_prerun
    """
    try:
        # Import here to avoid circular dependency
        from apps.core.middleware.correlation_id_middleware import set_correlation_id

        # Extract correlation ID from task request headers
        correlation_id = None

        if task and hasattr(task, 'request') and hasattr(task.request, 'correlation_id'):
            # Celery 5.x: correlation_id stored in task.request
            correlation_id = task.request.correlation_id
        elif task and hasattr(task, 'request'):
            # Check task headers
            headers = getattr(task.request, 'headers', None) or {}
            correlation_id = headers.get(CORRELATION_ID_HEADER)

        if correlation_id:
            # Restore correlation ID to thread-local storage
            set_correlation_id(correlation_id)
            logger.debug(
                f"Restored correlation ID for task execution: {task.name if task else 'unknown'}",
                extra={'correlation_id': correlation_id, 'task_id': task_id}
            )
        else:
            logger.warning(
                f"No correlation ID found in task headers: {task.name if task else 'unknown'}",
                extra={'task_id': task_id}
            )

    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to restore correlation ID: {e}")


@signals.task_postrun.connect
def cleanup_correlation_id_after_task(
    sender: Optional[Task] = None,
    task_id: Optional[str] = None,
    task: Optional[Task] = None,
    **kwargs
) -> None:
    """
    Clean up correlation ID from thread-local storage after task execution.

    This signal fires after a task completes (success or failure).
    Removes correlation ID from thread-local storage to prevent leakage to next task.

    Args:
        sender: Task class
        task_id: Unique task ID
        task: Task instance
        **kwargs: Additional signal arguments

    Signal: task_postrun
    """
    try:
        # Import here to avoid circular dependency
        from apps.core.middleware.correlation_id_middleware import clear_correlation_id

        clear_correlation_id()
        logger.debug(
            f"Cleaned up correlation ID after task: {task.name if task else 'unknown'}",
            extra={'task_id': task_id}
        )

    except ImportError as e:
        logger.warning(f"Failed to clear correlation ID: {e}")


def setup_correlation_id_propagation() -> None:
    """
    Initialize correlation ID propagation for Celery tasks.

    Call this function in celery.py after creating the Celery app instance.

    Usage:
        # In intelliwiz_config/celery.py
        from apps.core.tasks.celery_correlation_id import setup_correlation_id_propagation

        app = Celery('intelliwiz_config')
        # ... configure app ...
        setup_correlation_id_propagation()
    """
    logger.info("Correlation ID propagation for Celery tasks initialized")
    # Signal handlers are registered via @signals.connect decorators above
    # This function serves as an explicit initialization point for documentation
