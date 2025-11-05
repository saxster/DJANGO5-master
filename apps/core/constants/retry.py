"""
Retry and Backoff Strategy Constants

Centralized retry configuration for resilient operations. Includes:
- Retry attempt counts
- Exponential backoff multipliers
- Maximum delay caps
- Jitter ranges

Usage:
    from apps.core.constants.retry import (
        MAX_RETRIES_STANDARD,
        RETRY_BACKOFF_MULTIPLIER,
        RETRY_MAX_DELAY
    )

    @with_retry(
        max_retries=MAX_RETRIES_STANDARD,
        retry_policy='DATABASE_OPERATION'
    )
    def save_user(user):
        user.save()

Compliance:
- Eliminates hardcoded retry counts (typically 3, 5, 10)
- Provides consistent exponential backoff across application
- Prevents worker starvation with bounded delays
"""

from typing import Final

# =============================================================================
# RETRY ATTEMPT COUNTS
# =============================================================================

# Maximum retries for different operation types
MAX_RETRIES_MINIMAL: Final[int] = 1  # Single retry only
MAX_RETRIES_SHORT: Final[int] = 3  # Standard quick operations
MAX_RETRIES_STANDARD: Final[int] = 5  # Default for most operations
MAX_RETRIES_LONG: Final[int] = 10  # Long-running/critical operations
MAX_RETRIES_VERY_LONG: Final[int] = 15  # Network operations that may recover

# Database operation specific retries
DATABASE_RETRY_COUNT: Final[int] = 3  # Short-lived database contention
DATABASE_CONNECTION_RETRY_COUNT: Final[int] = 5  # Connection pool issues

# Network operation retries
NETWORK_RETRY_COUNT: Final[int] = 5  # HTTP requests, API calls
WEBHOOK_RETRY_COUNT: Final[int] = 3  # Webhook delivery attempts

# Task/Celery retries
CELERY_TASK_RETRY_COUNT: Final[int] = 5  # Standard Celery task retries
CELERY_CRITICAL_TASK_RETRY_COUNT: Final[int] = 10  # Critical tasks get more retries
CELERY_IDEMPOTENT_TASK_RETRY_COUNT: Final[int] = 3  # Idempotent tasks - quick retry

# Cache operation retries
CACHE_OPERATION_RETRY_COUNT: Final[int] = 2  # Redis/cache retries

# Authentication/Security retries
AUTH_RETRY_COUNT: Final[int] = 2  # Limit auth retries (security)
PASSWORD_VERIFICATION_RETRY_COUNT: Final[int] = 3  # Allow some tolerance

# =============================================================================
# EXPONENTIAL BACKOFF CONFIGURATION
# =============================================================================

# Exponential backoff multiplier (delay = base_delay * (multiplier ** attempt))
RETRY_BACKOFF_MULTIPLIER: Final[float] = 2.0  # Double delay each retry

# Alternative backoff multiplier (gentler growth)
RETRY_BACKOFF_MULTIPLIER_GENTLE: Final[float] = 1.5  # 50% increase per retry

# Linear backoff multiplier (for rate-limited operations)
RETRY_BACKOFF_MULTIPLIER_LINEAR: Final[float] = 1.0  # Same delay each time

# =============================================================================
# INITIAL DELAY & MAXIMUM DELAY (in seconds)
# =============================================================================

# Starting delay for first retry
RETRY_INITIAL_DELAY_SHORT: Final[int] = 1  # 1 second
RETRY_INITIAL_DELAY_MEDIUM: Final[int] = 2  # 2 seconds
RETRY_INITIAL_DELAY_LONG: Final[int] = 5  # 5 seconds

# Maximum delay cap to prevent worker starvation
RETRY_MAX_DELAY_SHORT: Final[int] = 60  # Cap at 1 minute
RETRY_MAX_DELAY_MEDIUM: Final[int] = 300  # Cap at 5 minutes
RETRY_MAX_DELAY_LONG: Final[int] = 900  # Cap at 15 minutes
RETRY_MAX_DELAY_VERY_LONG: Final[int] = 3600  # Cap at 1 hour

# =============================================================================
# JITTER CONFIGURATION (in seconds)
# =============================================================================

# Add randomness to prevent thundering herd
RETRY_JITTER_RANGE_SMALL: Final[tuple] = (0, 1)  # 0-1 second
RETRY_JITTER_RANGE_MEDIUM: Final[tuple] = (0, 5)  # 0-5 seconds
RETRY_JITTER_RANGE_LARGE: Final[tuple] = (0, 30)  # 0-30 seconds

# =============================================================================
# OPERATION-SPECIFIC RETRY POLICIES
# =============================================================================

# Database Operations
DATABASE_OPERATION_RETRY = {
    'max_retries': DATABASE_RETRY_COUNT,
    'initial_delay': RETRY_INITIAL_DELAY_SHORT,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER,
    'max_delay': RETRY_MAX_DELAY_SHORT,
    'jitter': RETRY_JITTER_RANGE_SMALL,
}

# Database Connection
DATABASE_CONNECTION_RETRY = {
    'max_retries': DATABASE_CONNECTION_RETRY_COUNT,
    'initial_delay': RETRY_INITIAL_DELAY_MEDIUM,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER,
    'max_delay': RETRY_MAX_DELAY_MEDIUM,
    'jitter': RETRY_JITTER_RANGE_MEDIUM,
}

# Network Operations
NETWORK_OPERATION_RETRY = {
    'max_retries': NETWORK_RETRY_COUNT,
    'initial_delay': RETRY_INITIAL_DELAY_MEDIUM,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER,
    'max_delay': RETRY_MAX_DELAY_MEDIUM,
    'jitter': RETRY_JITTER_RANGE_MEDIUM,
}

# Rate-Limited Operations (gentle backoff)
RATE_LIMITED_OPERATION_RETRY = {
    'max_retries': MAX_RETRIES_STANDARD,
    'initial_delay': RETRY_INITIAL_DELAY_SHORT,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER_GENTLE,
    'max_delay': RETRY_MAX_DELAY_LONG,
    'jitter': RETRY_JITTER_RANGE_LARGE,
}

# Webhook Delivery
WEBHOOK_DELIVERY_RETRY = {
    'max_retries': WEBHOOK_RETRY_COUNT,
    'initial_delay': RETRY_INITIAL_DELAY_SHORT,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER,
    'max_delay': RETRY_MAX_DELAY_MEDIUM,
    'jitter': RETRY_JITTER_RANGE_SMALL,
}

# Celery Tasks (Standard)
CELERY_TASK_RETRY = {
    'max_retries': CELERY_TASK_RETRY_COUNT,
    'initial_delay': RETRY_INITIAL_DELAY_SHORT,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER,
    'max_delay': RETRY_MAX_DELAY_MEDIUM,
    'jitter': RETRY_JITTER_RANGE_SMALL,
}

# Celery Critical Tasks
CELERY_CRITICAL_TASK_RETRY = {
    'max_retries': CELERY_CRITICAL_TASK_RETRY_COUNT,
    'initial_delay': RETRY_INITIAL_DELAY_SHORT,
    'backoff_multiplier': RETRY_BACKOFF_MULTIPLIER,
    'max_delay': RETRY_MAX_DELAY_LONG,
    'jitter': RETRY_JITTER_RANGE_MEDIUM,
}

# =============================================================================
# CIRCUIT BREAKER THRESHOLDS
# =============================================================================

# Circuit breaker: number of failures before opening
CIRCUIT_BREAKER_FAILURE_THRESHOLD: Final[int] = 5

# Circuit breaker: time window for counting failures (in seconds)
CIRCUIT_BREAKER_FAILURE_WINDOW: Final[int] = 300  # 5 minutes

# Circuit breaker: time to wait before attempting recovery (in seconds)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Final[int] = 60  # 1 minute

# Circuit breaker: success threshold to close circuit
CIRCUIT_BREAKER_SUCCESS_THRESHOLD: Final[int] = 2

# =============================================================================
# DEADLINE EXTENSION (for long-running operations)
# =============================================================================

# How much time to add to deadline when retrying
RETRY_DEADLINE_EXTENSION: Final[int] = 300  # 5 minutes additional per retry

# Maximum total deadline (don't retry past this)
MAX_TOTAL_DEADLINE: Final[int] = 3600  # 1 hour max

# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Retry counts
    'MAX_RETRIES_MINIMAL',
    'MAX_RETRIES_SHORT',
    'MAX_RETRIES_STANDARD',
    'MAX_RETRIES_LONG',
    'MAX_RETRIES_VERY_LONG',
    'DATABASE_RETRY_COUNT',
    'DATABASE_CONNECTION_RETRY_COUNT',
    'NETWORK_RETRY_COUNT',
    'WEBHOOK_RETRY_COUNT',
    'CELERY_TASK_RETRY_COUNT',
    'CELERY_CRITICAL_TASK_RETRY_COUNT',
    'CELERY_IDEMPOTENT_TASK_RETRY_COUNT',
    'CACHE_OPERATION_RETRY_COUNT',
    'AUTH_RETRY_COUNT',
    'PASSWORD_VERIFICATION_RETRY_COUNT',

    # Backoff configuration
    'RETRY_BACKOFF_MULTIPLIER',
    'RETRY_BACKOFF_MULTIPLIER_GENTLE',
    'RETRY_BACKOFF_MULTIPLIER_LINEAR',

    # Initial and maximum delays
    'RETRY_INITIAL_DELAY_SHORT',
    'RETRY_INITIAL_DELAY_MEDIUM',
    'RETRY_INITIAL_DELAY_LONG',
    'RETRY_MAX_DELAY_SHORT',
    'RETRY_MAX_DELAY_MEDIUM',
    'RETRY_MAX_DELAY_LONG',
    'RETRY_MAX_DELAY_VERY_LONG',

    # Jitter
    'RETRY_JITTER_RANGE_SMALL',
    'RETRY_JITTER_RANGE_MEDIUM',
    'RETRY_JITTER_RANGE_LARGE',

    # Operation-specific policies
    'DATABASE_OPERATION_RETRY',
    'DATABASE_CONNECTION_RETRY',
    'NETWORK_OPERATION_RETRY',
    'RATE_LIMITED_OPERATION_RETRY',
    'WEBHOOK_DELIVERY_RETRY',
    'CELERY_TASK_RETRY',
    'CELERY_CRITICAL_TASK_RETRY',

    # Circuit breaker
    'CIRCUIT_BREAKER_FAILURE_THRESHOLD',
    'CIRCUIT_BREAKER_FAILURE_WINDOW',
    'CIRCUIT_BREAKER_RECOVERY_TIMEOUT',
    'CIRCUIT_BREAKER_SUCCESS_THRESHOLD',

    # Deadline extension
    'RETRY_DEADLINE_EXTENSION',
    'MAX_TOTAL_DEADLINE',
]
