"""
Smart Retry Policy Engine

Context-aware retry strategies that adapt based on:
- Failure type classification
- Historical success rates
- External service status
- System resource availability

Features:
- Adaptive retry delays based on failure patterns
- Circuit breaker integration for failing services
- Cost-optimized retry scheduling
- A/B testing for retry strategies

Usage:
    from apps.core.tasks.smart_retry import SmartRetryEngine

    engine = SmartRetryEngine()
    policy = engine.get_retry_policy(task_name, exception, context)
    retry_delay = engine.calculate_next_retry(policy, retry_count)

Related Files:
- apps/core/tasks/failure_taxonomy.py - Failure classification
- apps/core/tasks/base.py - Base task classes
- background_tasks/dead_letter_queue.py - DLQ integration
"""

import logging
import random
import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from apps.core.tasks.failure_taxonomy import FailureTaxonomy, FailureType
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR

logger = logging.getLogger('celery.smart_retry')


# ============================================================================
# Retry Policy Configuration
# ============================================================================

@dataclass
class RetryPolicy:
    """
    Adaptive retry policy based on failure analysis.

    Attributes:
        max_retries: Maximum retry attempts
        initial_delay: First retry delay (seconds)
        backoff_strategy: 'exponential', 'linear', or 'fibonacci'
        backoff_factor: Multiplier for delay calculation
        max_delay: Maximum retry delay (seconds)
        jitter: Add randomization to prevent thundering herd (0.0-1.0)
        circuit_breaker_threshold: Failures before circuit opens
        circuit_breaker_timeout: Seconds before circuit reset
    """
    max_retries: int
    initial_delay: int
    backoff_strategy: str
    backoff_factor: float
    max_delay: int
    jitter: float
    circuit_breaker_threshold: int
    circuit_breaker_timeout: int


# ============================================================================
# Smart Retry Engine
# ============================================================================

class SmartRetryEngine:
    """
    Intelligent retry policy engine with adaptive strategies.

    Analyzes failure patterns and system state to determine optimal
    retry timing and strategy for each task failure.
    """

    # Default policies by failure type
    DEFAULT_POLICIES = {
        FailureType.TRANSIENT_DATABASE: RetryPolicy(
            max_retries=5,
            initial_delay=30,
            backoff_strategy='exponential',
            backoff_factor=2.0,
            max_delay=3600,
            jitter=0.2,
            circuit_breaker_threshold=10,
            circuit_breaker_timeout=300,
        ),
        FailureType.TRANSIENT_NETWORK: RetryPolicy(
            max_retries=3,
            initial_delay=60,
            backoff_strategy='exponential',
            backoff_factor=2.0,
            max_delay=1800,
            jitter=0.3,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=600,
        ),
        FailureType.TRANSIENT_RATE_LIMIT: RetryPolicy(
            max_retries=3,
            initial_delay=300,
            backoff_strategy='linear',
            backoff_factor=1.5,
            max_delay=3600,
            jitter=0.1,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=900,
        ),
        FailureType.EXTERNAL_API_DOWN: RetryPolicy(
            max_retries=2,
            initial_delay=900,
            backoff_strategy='fibonacci',
            backoff_factor=1.0,
            max_delay=7200,
            jitter=0.15,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=1800,
        ),
        FailureType.EXTERNAL_TIMEOUT: RetryPolicy(
            max_retries=2,
            initial_delay=300,
            backoff_strategy='exponential',
            backoff_factor=3.0,
            max_delay=3600,
            jitter=0.2,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=600,
        ),
    }

    def __init__(self):
        """Initialize smart retry engine."""
        self.cache_prefix = 'smart_retry:'
        self.metrics_prefix = 'retry_metrics:'

    def get_retry_policy(
        self,
        task_name: str,
        exception: Exception,
        task_context: Optional[Dict[str, Any]] = None
    ) -> RetryPolicy:
        """
        Get adaptive retry policy for task failure.

        Args:
            task_name: Name of failed task
            exception: Exception that caused failure
            task_context: Task execution context

        Returns:
            RetryPolicy optimized for the failure scenario
        """
        # Classify failure
        classification = FailureTaxonomy.classify(exception, task_context)

        # Get base policy
        policy = self.DEFAULT_POLICIES.get(
            classification.failure_type,
            RetryPolicy(  # Conservative default
                max_retries=1,
                initial_delay=300,
                backoff_strategy='exponential',
                backoff_factor=2.0,
                max_delay=1800,
                jitter=0.2,
                circuit_breaker_threshold=3,
                circuit_breaker_timeout=600,
            )
        )

        # Adapt based on historical success rate
        policy = self._adapt_to_history(task_name, classification.failure_type, policy)

        # Adapt based on system load
        policy = self._adapt_to_system_load(policy)

        # Check circuit breaker
        if self._is_circuit_open(task_name, classification.failure_type):
            logger.warning(
                f"Circuit breaker open for {task_name} ({classification.failure_type.value})",
                extra={'task_name': task_name, 'failure_type': classification.failure_type.value}
            )
            # Extend delay when circuit is open
            policy.initial_delay *= 2
            policy.max_delay *= 2

        return policy

    def calculate_next_retry(
        self,
        policy: RetryPolicy,
        retry_count: int,
        failure_timestamp: Optional[float] = None
    ) -> int:
        """
        Calculate optimal next retry delay.

        Args:
            policy: Retry policy to apply
            retry_count: Current retry attempt number (0-indexed)
            failure_timestamp: When failure occurred (for rate limit reset)

        Returns:
            Delay in seconds until next retry
        """
        if retry_count >= policy.max_retries:
            return 0  # No more retries

        # Calculate base delay
        if policy.backoff_strategy == 'exponential':
            delay = policy.initial_delay * (policy.backoff_factor ** retry_count)
        elif policy.backoff_strategy == 'linear':
            delay = policy.initial_delay * (1 + policy.backoff_factor * retry_count)
        elif policy.backoff_strategy == 'fibonacci':
            delay = policy.initial_delay * self._fibonacci(retry_count + 1)
        else:
            delay = policy.initial_delay

        # Cap at max delay
        delay = min(delay, policy.max_delay)

        # Add jitter to prevent thundering herd
        if policy.jitter > 0:
            jitter_range = delay * policy.jitter
            jitter = random.uniform(-jitter_range, jitter_range)
            delay += jitter

        # Ensure minimum delay
        delay = max(delay, 1)

        logger.debug(
            f"Calculated retry delay: {delay:.1f}s (attempt {retry_count + 1}/{policy.max_retries})",
            extra={
                'retry_count': retry_count,
                'delay_seconds': delay,
                'backoff_strategy': policy.backoff_strategy
            }
        )

        return int(delay)

    def record_retry_attempt(
        self,
        task_name: str,
        failure_type: FailureType,
        success: bool
    ):
        """
        Record retry attempt for adaptive learning.

        Args:
            task_name: Name of retried task
            failure_type: Type of failure that was retried
            success: Whether retry succeeded
        """
        cache_key = f"{self.metrics_prefix}{task_name}:{failure_type.value}"

        metrics = cache.get(cache_key, {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'last_updated': timezone.now().isoformat()
        })

        metrics['total_retries'] += 1
        if success:
            metrics['successful_retries'] += 1
        else:
            metrics['failed_retries'] += 1
        metrics['last_updated'] = timezone.now().isoformat()

        cache.set(cache_key, metrics, timeout=SECONDS_IN_HOUR * 24 * 7)  # 7 days

        # Update circuit breaker
        self._update_circuit_breaker(task_name, failure_type, success)

    def get_retry_statistics(self, task_name: str) -> Dict[str, Any]:
        """
        Get retry statistics for monitoring.

        Args:
            task_name: Task to get statistics for

        Returns:
            Statistics dict with success rates by failure type
        """
        stats = {}

        for failure_type in FailureType:
            cache_key = f"{self.metrics_prefix}{task_name}:{failure_type.value}"
            metrics = cache.get(cache_key)

            if metrics:
                total = metrics['total_retries']
                successful = metrics['successful_retries']
                success_rate = (successful / total * 100) if total > 0 else 0

                stats[failure_type.value] = {
                    'total_retries': total,
                    'successful_retries': successful,
                    'failed_retries': metrics['failed_retries'],
                    'success_rate': round(success_rate, 2),
                    'last_updated': metrics['last_updated']
                }

        return stats

    def _adapt_to_history(
        self,
        task_name: str,
        failure_type: FailureType,
        policy: RetryPolicy
    ) -> RetryPolicy:
        """Adapt policy based on historical success rates."""
        cache_key = f"{self.metrics_prefix}{task_name}:{failure_type.value}"
        metrics = cache.get(cache_key)

        if not metrics or metrics['total_retries'] < 10:
            return policy  # Not enough data

        success_rate = metrics['successful_retries'] / metrics['total_retries']

        # If success rate is high, reduce delays
        if success_rate > 0.8:
            policy.initial_delay = int(policy.initial_delay * 0.7)
            policy.max_delay = int(policy.max_delay * 0.7)
            logger.debug(f"Reduced retry delays for {task_name} (high success rate: {success_rate:.2%})")

        # If success rate is low, increase delays and reduce retries
        elif success_rate < 0.3:
            policy.initial_delay = int(policy.initial_delay * 1.5)
            policy.max_delay = int(policy.max_delay * 1.5)
            policy.max_retries = max(1, policy.max_retries - 1)
            logger.debug(f"Increased retry delays for {task_name} (low success rate: {success_rate:.2%})")

        return policy

    def _adapt_to_system_load(self, policy: RetryPolicy) -> RetryPolicy:
        """Adapt policy based on current system load."""
        # Get worker queue depth
        queue_depth_key = 'celery:queue_depth'
        queue_depth = cache.get(queue_depth_key, 0)

        # If system is heavily loaded, extend delays
        if queue_depth > 100:
            policy.initial_delay = int(policy.initial_delay * 1.3)
            policy.max_delay = int(policy.max_delay * 1.3)
            logger.debug(f"Increased retry delays due to system load (queue depth: {queue_depth})")

        return policy

    def _is_circuit_open(self, task_name: str, failure_type: FailureType) -> bool:
        """Check if circuit breaker is open for this task/failure combination."""
        circuit_key = f"{self.cache_prefix}circuit:{task_name}:{failure_type.value}"
        circuit_state = cache.get(circuit_key)

        if circuit_state and circuit_state['state'] == 'open':
            # Check if timeout expired
            open_time = circuit_state['opened_at']
            if (time.time() - open_time) < circuit_state['timeout']:
                return True

            # Timeout expired, transition to half-open
            circuit_state['state'] = 'half-open'
            cache.set(circuit_key, circuit_state, timeout=SECONDS_IN_HOUR)

        return False

    def _update_circuit_breaker(
        self,
        task_name: str,
        failure_type: FailureType,
        success: bool
    ):
        """Update circuit breaker state based on retry result."""
        circuit_key = f"{self.cache_prefix}circuit:{task_name}:{failure_type.value}"
        circuit_state = cache.get(circuit_key, {
            'state': 'closed',
            'failure_count': 0,
            'success_count': 0,
            'opened_at': None,
            'timeout': 600
        })

        if success:
            circuit_state['success_count'] += 1
            circuit_state['failure_count'] = 0  # Reset failure count

            # If in half-open and success, close circuit
            if circuit_state['state'] == 'half-open':
                circuit_state['state'] = 'closed'
                logger.info(f"Circuit breaker closed for {task_name} ({failure_type.value})")

        else:
            circuit_state['failure_count'] += 1
            circuit_state['success_count'] = 0

            # Get policy to check threshold
            policy = self.DEFAULT_POLICIES.get(failure_type)
            if policy and circuit_state['failure_count'] >= policy.circuit_breaker_threshold:
                circuit_state['state'] = 'open'
                circuit_state['opened_at'] = time.time()
                circuit_state['timeout'] = policy.circuit_breaker_timeout
                logger.warning(f"Circuit breaker opened for {task_name} ({failure_type.value})")

        cache.set(circuit_key, circuit_state, timeout=SECONDS_IN_HOUR * 24)

    @staticmethod
    def _fibonacci(n: int) -> int:
        """Calculate nth Fibonacci number for backoff."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b


# ============================================================================
# Cost-Optimized Retry Scheduler
# ============================================================================

class CostOptimizedRetryScheduler:
    """
    Schedule retries to minimize infrastructure costs.

    Features:
    - Batch retries during off-peak hours
    - Consolidate retries to reduce worker churn
    - Prioritize based on business value
    """

    # Peak hours (more expensive)
    PEAK_HOURS = list(range(9, 18))  # 9 AM - 6 PM

    def __init__(self):
        """Initialize cost optimizer."""
        self.cache_prefix = 'cost_optimizer:'

    def should_defer_retry(
        self,
        task_name: str,
        priority: str,
        estimated_cost: float = 0.0
    ) -> Tuple[bool, int]:
        """
        Determine if retry should be deferred to off-peak hours.

        Args:
            task_name: Name of task
            priority: Task priority (critical, high, normal, low)
            estimated_cost: Estimated compute cost

        Returns:
            Tuple of (should_defer, defer_seconds)
        """
        current_hour = timezone.now().hour

        # Never defer critical tasks
        if priority == 'critical':
            return False, 0

        # Check if currently in peak hours
        in_peak = current_hour in self.PEAK_HOURS

        # Defer low-priority tasks during peak
        if priority == 'low' and in_peak:
            # Calculate seconds until off-peak
            if current_hour < 18:
                next_offpeak = 18
            else:
                next_offpeak = 9 + 24  # Next morning

            hours_until_offpeak = (next_offpeak - current_hour) % 24
            defer_seconds = hours_until_offpeak * 3600

            logger.info(
                f"Deferring low-priority retry to off-peak: {task_name}",
                extra={
                    'task_name': task_name,
                    'defer_hours': hours_until_offpeak
                }
            )

            return True, defer_seconds

        return False, 0

    def get_cost_savings_estimate(self, task_name: str) -> Dict[str, Any]:
        """
        Estimate cost savings from optimization.

        Args:
            task_name: Task to analyze

        Returns:
            Cost savings estimate
        """
        cache_key = f"{self.cache_prefix}savings:{task_name}"
        savings = cache.get(cache_key, {
            'deferred_count': 0,
            'peak_hour_savings': 0.0,
            'total_cost_avoided': 0.0
        })

        return savings


# Global engine instance
retry_engine = SmartRetryEngine()
cost_optimizer = CostOptimizedRetryScheduler()
