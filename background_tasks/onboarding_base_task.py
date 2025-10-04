"""
Base Task Class for Onboarding Celery Tasks with DLQ Integration

Provides standardized error handling, DLQ integration, and retry logic
for all onboarding background tasks.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management

Author: Claude Code
Date: 2025-10-01
"""

import logging
import traceback
import uuid
from typing import Dict, Any, Optional, Callable, Tuple
from datetime import datetime

from celery import Task
from django.conf import settings
from django.db import transaction, DatabaseError, OperationalError, IntegrityError
from django.core.exceptions import ValidationError

# Resilience imports
from background_tasks.onboarding_retry_strategies import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    LLM_API_EXCEPTIONS,
    VALIDATION_EXCEPTIONS,
)
from background_tasks.dead_letter_queue import dlq_handler

logger = logging.getLogger("django")
task_logger = logging.getLogger("celery.task")


class OnboardingBaseTask(Task):
    """
    Base class for onboarding Celery tasks with DLQ integration

    Provides:
    - Automatic DLQ sending on final retry
    - Exception categorization and handling
    - Correlation ID tracking
    - State management helpers
    - Structured logging

    Usage:
        @shared_task(bind=True, base=OnboardingBaseTask, **llm_api_task_config())
        def my_task(self, arg1, arg2, correlation_id=None):
            correlation_id = self.get_correlation_id(correlation_id)
            try:
                # Task logic here
                result = do_work(arg1, arg2)
                return self.task_success(result, correlation_id)
            except Exception as e:
                return self.handle_task_error(
                    e,
                    correlation_id=correlation_id,
                    context={'arg1': arg1, 'arg2': arg2}
                )
    """

    # Task categorization for different retry strategies
    task_category = 'general'  # Override in subclass: 'database', 'llm_api', 'network'

    # Custom exception handlers
    custom_handlers = {}  # Override in subclass to add custom exception handling

    def get_correlation_id(self, provided_id: Optional[str] = None) -> str:
        """
        Get or generate correlation ID for tracking

        Args:
            provided_id: Optional correlation ID from caller

        Returns:
            Correlation ID string
        """
        if provided_id:
            return provided_id

        # Try to get from task request
        if hasattr(self, 'request') and hasattr(self.request, 'id'):
            return str(self.request.id)

        # Generate new ID
        return str(uuid.uuid4())

    def task_success(
        self,
        result: Any,
        correlation_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Standard success response format

        Args:
            result: Task result data
            correlation_id: Correlation ID
            metadata: Optional additional metadata

        Returns:
            Standardized success response
        """
        response = {
            'status': 'completed',
            'result': result,
            'correlation_id': correlation_id,
            'completed_at': datetime.now().isoformat(),
        }

        if metadata:
            response['metadata'] = metadata

        task_logger.info(
            f"Task {self.name} completed successfully",
            extra={
                'correlation_id': correlation_id,
                'task_name': self.name
            }
        )

        return response

    def task_failure(
        self,
        error_message: str,
        correlation_id: str,
        error_type: str = 'unknown',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Standard failure response format

        Args:
            error_message: Error description
            correlation_id: Correlation ID
            error_type: Type of error
            metadata: Optional additional metadata

        Returns:
            Standardized failure response
        """
        response = {
            'status': 'failed',
            'error': error_message,
            'error_type': error_type,
            'correlation_id': correlation_id,
            'failed_at': datetime.now().isoformat(),
        }

        if metadata:
            response['metadata'] = metadata

        return response

    def handle_task_error(
        self,
        exception: Exception,
        correlation_id: str,
        context: Optional[Dict[str, Any]] = None,
        retryable: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive error handling with DLQ integration

        Args:
            exception: Exception that occurred
            correlation_id: Correlation ID for tracking
            context: Additional context data
            retryable: Override retryable determination

        Returns:
            Error response dict
        """
        error_type = type(exception).__name__
        error_message = str(exception)

        # Log error with context
        task_logger.error(
            f"Task {self.name} encountered error: {error_type}",
            extra={
                'correlation_id': correlation_id,
                'task_name': self.name,
                'error_type': error_type,
                'error_message': error_message,
                'context': context
            },
            exc_info=True
        )

        # Determine if this is the final retry
        is_final_retry = self._is_final_retry()

        # Send to DLQ if final retry
        if is_final_retry:
            self._send_to_dlq(
                exception=exception,
                correlation_id=correlation_id,
                context=context
            )

        # Determine if retryable
        if retryable is None:
            retryable = self._is_retryable_exception(exception)

        # Re-raise for automatic retry if retryable and not final
        if retryable and not is_final_retry:
            raise exception

        # Return failure response for non-retryable or final retry
        return self.task_failure(
            error_message=error_message,
            correlation_id=correlation_id,
            error_type=error_type,
            metadata={
                'retryable': retryable,
                'final_retry': is_final_retry,
                'retry_count': getattr(self.request, 'retries', 0) if hasattr(self, 'request') else 0
            }
        )

    def _is_final_retry(self) -> bool:
        """Check if this is the final retry attempt"""
        if not hasattr(self, 'request'):
            return False

        current_retries = getattr(self.request, 'retries', 0)
        max_retries = getattr(self, 'max_retries', 3)

        return current_retries >= max_retries

    def _is_retryable_exception(self, exception: Exception) -> bool:
        """
        Determine if exception is retryable

        Args:
            exception: Exception to check

        Returns:
            True if retryable
        """
        # Database exceptions are retryable
        if isinstance(exception, DATABASE_EXCEPTIONS):
            # Except IntegrityError (usually not transient)
            if isinstance(exception, IntegrityError):
                return False
            return True

        # Network/LLM API exceptions are retryable
        if isinstance(exception, (NETWORK_EXCEPTIONS, LLM_API_EXCEPTIONS)):
            return True

        # Validation exceptions are NOT retryable
        if isinstance(exception, VALIDATION_EXCEPTIONS):
            return False

        # Unknown exceptions - default to non-retryable for safety
        return False

    def _send_to_dlq(
        self,
        exception: Exception,
        correlation_id: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Send failed task to Dead Letter Queue

        Args:
            exception: Exception that caused failure
            correlation_id: Correlation ID
            context: Additional context data
        """
        try:
            task_logger.critical(
                f"Sending task {self.name} to DLQ after max retries",
                extra={
                    'correlation_id': correlation_id,
                    'task_name': self.name,
                    'exception_type': type(exception).__name__
                }
            )

            # Get task args and kwargs
            task_args = getattr(self.request, 'args', ()) if hasattr(self, 'request') else ()
            task_kwargs = getattr(self.request, 'kwargs', {}) if hasattr(self, 'request') else {}

            # Add context to kwargs for DLQ
            if context:
                task_kwargs['context'] = context

            # Send to DLQ
            dlq_handler.send_to_dlq(
                task_id=str(getattr(self.request, 'id', correlation_id)) if hasattr(self, 'request') else correlation_id,
                task_name=self.name,
                args=task_args,
                kwargs=task_kwargs,
                exception=exception,
                retry_count=getattr(self.request, 'retries', 0) if hasattr(self, 'request') else 0,
                correlation_id=correlation_id
            )

        except Exception as dlq_error:
            task_logger.error(
                f"Failed to send task to DLQ: {str(dlq_error)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )

    def with_transaction(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function within database transaction

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        with transaction.atomic():
            return func(*args, **kwargs)

    def safe_execute(
        self,
        func: Callable,
        fallback_value: Any = None,
        log_error: bool = True,
        *args,
        **kwargs
    ) -> Tuple[Any, Optional[Exception]]:
        """
        Safely execute function with error handling

        Args:
            func: Function to execute
            fallback_value: Value to return on error
            log_error: Whether to log errors
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (result, exception)
        """
        try:
            result = func(*args, **kwargs)
            return result, None
        except Exception as e:
            if log_error:
                task_logger.warning(
                    f"Safe execution failed: {str(e)}",
                    extra={'function': func.__name__},
                    exc_info=True
                )
            return fallback_value, e


# =============================================================================
# SPECIALIZED BASE TASKS
# =============================================================================

class OnboardingDatabaseTask(OnboardingBaseTask):
    """Base task for database-heavy operations"""
    task_category = 'database'


class OnboardingLLMTask(OnboardingBaseTask):
    """Base task for LLM API operations"""
    task_category = 'llm_api'


class OnboardingNetworkTask(OnboardingBaseTask):
    """Base task for network/API operations"""
    task_category = 'network'


# =============================================================================
# TASK DECORATORS
# =============================================================================

def with_dlq_integration(task_func):
    """
    Decorator to add DLQ integration to task functions

    Usage:
        @shared_task
        @with_dlq_integration
        def my_task(arg1, arg2):
            # Task logic
            pass
    """
    def wrapper(self, *args, **kwargs):
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))

        try:
            result = task_func(self, *args, **kwargs)
            return result

        except Exception as e:
            # Check if final retry
            if hasattr(self, 'request') and self.request.retries >= self.max_retries:
                # Send to DLQ
                dlq_handler.send_to_dlq(
                    task_id=str(self.request.id),
                    task_name=self.name,
                    args=args,
                    kwargs=kwargs,
                    exception=e,
                    retry_count=self.request.retries,
                    correlation_id=correlation_id
                )

            # Re-raise for retry
            raise

    return wrapper


__all__ = [
    'OnboardingBaseTask',
    'OnboardingDatabaseTask',
    'OnboardingLLMTask',
    'OnboardingNetworkTask',
    'with_dlq_integration',
]
