"""
Celery retry strategies for conversational onboarding tasks.

Provides enterprise-grade retry policies with exponential backoff, jitter,
and specific exception handling for different failure scenarios.

Following .claude/rules.md:
- Rule #11: Specific exception handling (no bare except)
- Rule #17: Transaction management for critical operations
"""

import logging
import random
from typing import Dict, Any, Optional, Tuple, Type
from datetime import timedelta

from django.db import DatabaseError, OperationalError, IntegrityError
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# Define exception categories for different retry strategies
DATABASE_EXCEPTIONS = (
    DatabaseError,
    OperationalError,
    IntegrityError,
)

NETWORK_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network-related OS errors
)

LLM_API_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    # Add specific LLM provider exceptions when available
)

VALIDATION_EXCEPTIONS = (
    ValidationError,
    ValueError,
    TypeError,
)


class RetryStrategy:
    """
    Base class for retry strategies with exponential backoff and jitter.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: int = 2,  # seconds
        max_delay: int = 600,  # 10 minutes
        exponential_base: int = 2,
        jitter: bool = True
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for first retry
            max_delay: Maximum delay in seconds (cap for exponential backoff)
            exponential_base: Base for exponential calculation (2 = doubling)
            jitter: Add random jitter to prevent thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, retry_count: int) -> int:
        """
        Calculate delay for given retry attempt with exponential backoff.

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = base_delay * (exponential_base ^ retry_count)
        delay = self.base_delay * (self.exponential_base ** retry_count)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter:
            # Random jitter: 50-100% of calculated delay
            jitter_factor = random.uniform(0.5, 1.0)
            delay = int(delay * jitter_factor)

        return delay

    def should_retry(
        self,
        exception: Exception,
        retry_count: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if task should be retried based on exception and retry count.

        Args:
            exception: Exception that caused task failure
            retry_count: Current retry attempt number

        Returns:
            (should_retry: bool, reason: str)
        """
        if retry_count >= self.max_retries:
            return False, f"Max retries ({self.max_retries}) exceeded"

        return True, None


class DatabaseRetryStrategy(RetryStrategy):
    """
    Retry strategy for database operations with transaction awareness.
    """

    def __init__(self):
        super().__init__(
            max_retries=3,
            base_delay=1,  # Start with 1 second
            max_delay=30,  # Cap at 30 seconds for DB operations
            exponential_base=2,
            jitter=True
        )
        self.retryable_exceptions = DATABASE_EXCEPTIONS

    def should_retry(
        self,
        exception: Exception,
        retry_count: int
    ) -> Tuple[bool, Optional[str]]:
        """Check if database exception is retryable."""
        if retry_count >= self.max_retries:
            return False, f"Max DB retries ({self.max_retries}) exceeded"

        if not isinstance(exception, self.retryable_exceptions):
            return False, f"Non-retryable DB exception: {type(exception).__name__}"

        # Specific handling for different DB errors
        if isinstance(exception, IntegrityError):
            # Integrity errors usually not transient - don't retry
            return False, "IntegrityError not retryable"

        if isinstance(exception, OperationalError):
            # Operational errors (deadlock, timeout) are retryable
            return True, "Retrying OperationalError"

        return True, None


class NetworkRetryStrategy(RetryStrategy):
    """
    Retry strategy for network/API operations with longer delays.
    """

    def __init__(self):
        super().__init__(
            max_retries=5,  # More retries for network issues
            base_delay=3,   # Start with 3 seconds
            max_delay=300,  # Cap at 5 minutes
            exponential_base=2,
            jitter=True
        )
        self.retryable_exceptions = NETWORK_EXCEPTIONS


class LLMAPIRetryStrategy(RetryStrategy):
    """
    Retry strategy specifically for LLM API calls (OpenAI, Anthropic, etc.)
    with rate limit handling.
    """

    def __init__(self):
        super().__init__(
            max_retries=4,
            base_delay=5,   # Start with 5 seconds for API calls
            max_delay=600,  # Cap at 10 minutes (API rate limits)
            exponential_base=3,  # Faster exponential for API limits
            jitter=True
        )
        self.retryable_exceptions = LLM_API_EXCEPTIONS

    def should_retry(
        self,
        exception: Exception,
        retry_count: int
    ) -> Tuple[bool, Optional[str]]:
        """Check if LLM API exception is retryable."""
        if retry_count >= self.max_retries:
            return False, f"Max LLM API retries ({self.max_retries}) exceeded"

        # Check for rate limit indicators in exception message
        error_msg = str(exception).lower()
        if 'rate limit' in error_msg or '429' in error_msg:
            # Rate limit - definitely retry with longer delay
            return True, "Rate limit hit - retrying with backoff"

        if 'timeout' in error_msg or isinstance(exception, TimeoutError):
            return True, "Timeout - retrying"

        if isinstance(exception, self.retryable_exceptions):
            return True, "Retryable LLM API exception"

        return False, f"Non-retryable exception: {type(exception).__name__}"


class ValidationRetryStrategy(RetryStrategy):
    """
    Retry strategy for validation errors (usually NOT retryable).
    """

    def __init__(self):
        super().__init__(
            max_retries=1,  # Minimal retries for validation
            base_delay=1,
            max_delay=5,
            exponential_base=2,
            jitter=False  # No jitter needed for validation
        )

    def should_retry(
        self,
        exception: Exception,
        retry_count: int
    ) -> Tuple[bool, Optional[str]]:
        """Validation errors are usually not retryable."""
        # Only retry once in case of transient validation issues
        if retry_count >= 1:
            return False, "Validation errors not retryable"

        return False, f"ValidationError not retryable: {str(exception)}"


# Registry of retry strategies by name
RETRY_STRATEGIES = {
    'database': DatabaseRetryStrategy(),
    'network': NetworkRetryStrategy(),
    'llm_api': LLMAPIRetryStrategy(),
    'validation': ValidationRetryStrategy(),
}


def get_retry_strategy(strategy_name: str) -> RetryStrategy:
    """
    Get retry strategy by name.

    Args:
        strategy_name: Name of strategy (database, network, llm_api, validation)

    Returns:
        RetryStrategy instance

    Raises:
        ValueError: If strategy name not found
    """
    if strategy_name not in RETRY_STRATEGIES:
        raise ValueError(
            f"Unknown retry strategy: {strategy_name}. "
            f"Available: {list(RETRY_STRATEGIES.keys())}"
        )

    return RETRY_STRATEGIES[strategy_name]


def create_celery_retry_config(
    strategy_name: str,
    custom_exceptions: Optional[Tuple[Type[Exception], ...]] = None
) -> Dict[str, Any]:
    """
    Create Celery task retry configuration from strategy.

    Args:
        strategy_name: Name of retry strategy to use
        custom_exceptions: Optional custom exceptions to retry on

    Returns:
        Dict of Celery task configuration parameters
    """
    strategy = get_retry_strategy(strategy_name)

    config = {
        'max_retries': strategy.max_retries,
        'retry_backoff': strategy.base_delay,
        'retry_backoff_max': strategy.max_delay,
        'retry_jitter': strategy.jitter,
    }

    # Add exceptions to retry on
    if custom_exceptions:
        config['autoretry_for'] = custom_exceptions
    elif strategy_name == 'database':
        config['autoretry_for'] = DATABASE_EXCEPTIONS
    elif strategy_name == 'network':
        config['autoretry_for'] = NETWORK_EXCEPTIONS
    elif strategy_name == 'llm_api':
        config['autoretry_for'] = LLM_API_EXCEPTIONS

    return config


# Pre-configured task decorators for common scenarios
def database_task_config() -> Dict[str, Any]:
    """Get Celery config for database-heavy tasks."""
    return create_celery_retry_config('database')


def network_task_config() -> Dict[str, Any]:
    """Get Celery config for network/API tasks."""
    return create_celery_retry_config('network')


def llm_api_task_config() -> Dict[str, Any]:
    """Get Celery config for LLM API tasks."""
    return create_celery_retry_config('llm_api')
