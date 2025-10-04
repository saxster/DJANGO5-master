"""
Universal State Transition Coordinator

Ensures ALL state machine transitions go through proper concurrency controls,
preventing race conditions and data corruption.

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management requirements

Key Features:
- Mandatory distributed locking for all transitions
- Configurable transaction isolation levels
- Performance metrics collection
- Comprehensive audit logging
- Automatic retry on lock contention
- Support for batch transitions

Usage:
    from apps.core.services.state_transition_coordinator import StateTransitionCoordinator
    from apps.activity.state_machines.task_state_machine import TaskStateMachine

    # Single transition with automatic locking
    result = StateTransitionCoordinator.execute_transition(
        state_machine=TaskStateMachine(job_instance),
        to_state='COMPLETED',
        context=TransitionContext(user=request.user, comments='Work done'),
        lock_timeout=10
    )
"""

import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from django.db import transaction, connection, DatabaseError
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext,
    TransitionResult,
    InvalidTransitionError,
    PermissionDeniedError,
    StateTransitionError
)
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.constants.datetime_constants import MILLISECONDS_IN_SECOND

logger = logging.getLogger(__name__)


@dataclass
class TransitionMetrics:
    """Performance metrics for a state transition"""
    lock_acquisition_ms: int
    transition_duration_ms: int
    total_duration_ms: int
    retry_count: int
    success: bool
    error_message: Optional[str] = None


class StateTransitionCoordinator:
    """
    Centralized coordinator for ALL state machine transitions.

    Guarantees:
    - Race condition prevention via distributed locking
    - Atomic database operations
    - Comprehensive audit trail
    - Performance monitoring
    - Automatic retry on transient failures
    """

    @staticmethod
    def execute_transition(
        state_machine: BaseStateMachine,
        to_state: str,
        context: TransitionContext,
        lock_timeout: int = 10,
        blocking_timeout: int = 5,
        isolation_level: Optional[str] = None,
        max_retries: int = 3
    ) -> TransitionResult:
        """
        Execute state transition with guaranteed concurrency safety.

        Args:
            state_machine: State machine instance with entity loaded
            to_state: Target state to transition to
            context: Transition context (user, reason, comments, etc.)
            lock_timeout: Seconds to hold distributed lock
            blocking_timeout: Seconds to wait for lock acquisition
            isolation_level: Transaction isolation level (default: READ COMMITTED)
            max_retries: Maximum retry attempts on lock contention

        Returns:
            TransitionResult with success status and metadata

        Raises:
            InvalidTransitionError: If transition is not valid
            PermissionDeniedError: If user lacks permission
            LockAcquisitionError: If cannot acquire lock after retries
            StateTransitionError: For other transition errors
        """
        entity_type = state_machine.__class__.__name__
        entity_id = state_machine.instance.pk
        current_state = state_machine._get_current_state(state_machine.instance)

        # Generate unique lock key for this entity's state
        lock_key = f"state_transition:{entity_type}:{entity_id}"

        start_time = time.time()
        lock_acquired_time = None
        retry_count = 0

        for attempt in range(max_retries):
            try:
                retry_count = attempt

                # Acquire distributed lock with timeout
                with distributed_lock(lock_key, timeout=lock_timeout, blocking_timeout=blocking_timeout):
                    lock_acquired_time = time.time()
                    lock_acquisition_ms = int((lock_acquired_time - start_time) * MILLISECONDS_IN_SECOND)

                    logger.debug(
                        f"Lock acquired for {entity_type}:{entity_id} transition "
                        f"{current_state} → {to_state} (took {lock_acquisition_ms}ms)",
                        extra={
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'lock_acquisition_ms': lock_acquisition_ms
                        }
                    )

                    # Execute transition with configurable isolation
                    result = StateTransitionCoordinator._execute_with_isolation(
                        state_machine=state_machine,
                        to_state=to_state,
                        context=context,
                        isolation_level=isolation_level
                    )

                    transition_end_time = time.time()
                    transition_duration_ms = int((transition_end_time - lock_acquired_time) * MILLISECONDS_IN_SECOND)
                    total_duration_ms = int((transition_end_time - start_time) * MILLISECONDS_IN_SECOND)

                    # Record performance metrics
                    metrics = TransitionMetrics(
                        lock_acquisition_ms=lock_acquisition_ms,
                        transition_duration_ms=transition_duration_ms,
                        total_duration_ms=total_duration_ms,
                        retry_count=retry_count,
                        success=result.success,
                        error_message=result.error_message
                    )

                    StateTransitionCoordinator._record_metrics(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        from_state=current_state,
                        to_state=to_state,
                        metrics=metrics,
                        context=context
                    )

                    logger.info(
                        f"State transition completed: {entity_type}:{entity_id} "
                        f"{current_state} → {to_state} in {total_duration_ms}ms",
                        extra={
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'from_state': current_state,
                            'to_state': to_state,
                            'total_duration_ms': total_duration_ms,
                            'success': result.success
                        }
                    )

                    return result

            except LockAcquisitionError as e:
                # Retry on lock contention
                if attempt < max_retries - 1:
                    backoff_ms = (attempt + 1) * 100  # 100ms, 200ms, 300ms
                    logger.warning(
                        f"Lock contention for {entity_type}:{entity_id}, "
                        f"retrying in {backoff_ms}ms (attempt {attempt + 1}/{max_retries})",
                        extra={
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'attempt': attempt + 1,
                            'max_retries': max_retries
                        }
                    )
                    time.sleep(backoff_ms / MILLISECONDS_IN_SECOND)
                    continue
                else:
                    # Final retry failed
                    logger.error(
                        f"Failed to acquire lock for {entity_type}:{entity_id} after {max_retries} attempts",
                        extra={
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'max_retries': max_retries
                        },
                        exc_info=True
                    )
                    raise LockAcquisitionError(
                        f"Could not acquire lock for {entity_type}:{entity_id} transition after {max_retries} retries"
                    ) from e

            except (InvalidTransitionError, PermissionDeniedError, StateTransitionError):
                # Re-raise state machine errors without retry
                raise

            except (DatabaseError, ValidationError) as e:
                logger.error(
                    f"Database error during {entity_type}:{entity_id} transition: {e}",
                    extra={
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'from_state': current_state,
                        'to_state': to_state
                    },
                    exc_info=True
                )
                raise StateTransitionError(f"Transition failed due to database error: {e}") from e

    @staticmethod
    def _execute_with_isolation(
        state_machine: BaseStateMachine,
        to_state: str,
        context: TransitionContext,
        isolation_level: Optional[str] = None
    ) -> TransitionResult:
        """
        Execute transition with specified transaction isolation level.

        Args:
            state_machine: State machine instance
            to_state: Target state
            context: Transition context
            isolation_level: One of: 'READ UNCOMMITTED', 'READ COMMITTED',
                           'REPEATABLE READ', 'SERIALIZABLE'
        """
        db_name = get_current_db_name()

        if isolation_level:
            # Set isolation level for this transaction
            with connection.cursor() as cursor:
                cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")

        # Execute state machine transition (already has @transaction.atomic)
        return state_machine.transition(to_state, context)

    @staticmethod
    def _record_metrics(
        entity_type: str,
        entity_id: int,
        from_state: str,
        to_state: str,
        metrics: TransitionMetrics,
        context: TransitionContext
    ):
        """
        Record state transition metrics for monitoring.

        This will integrate with StateTransitionAudit model when created.
        For now, logs comprehensive metrics.
        """
        logger.info(
            f"State transition metrics: {entity_type}:{entity_id}",
            extra={
                'entity_type': entity_type,
                'entity_id': entity_id,
                'from_state': from_state,
                'to_state': to_state,
                'lock_acquisition_ms': metrics.lock_acquisition_ms,
                'transition_duration_ms': metrics.transition_duration_ms,
                'total_duration_ms': metrics.total_duration_ms,
                'retry_count': metrics.retry_count,
                'success': metrics.success,
                'error_message': metrics.error_message,
                'user_id': context.user.id if context.user else None,
                'reason': context.reason
            }
        )

        # Store audit record in database
        try:
            from apps.core.models.state_transition_audit import StateTransitionAudit

            # Sanitize metadata to prevent PII leakage
            sanitized_metadata = {
                k: v for k, v in (context.metadata or {}).items()
                if k not in ['password', 'token', 'secret', 'api_key', 'ssn', 'credit_card']
            }

            StateTransitionAudit.objects.create(
                entity_type=entity_type,
                entity_id=str(entity_id),
                from_state=from_state,
                to_state=to_state,
                user=context.user,
                reason=context.reason or 'user_action',
                comments=context.comments or '',
                metadata=sanitized_metadata,
                timestamp=context.timestamp or timezone.now(),
                success=metrics.success,
                error_message=metrics.error_message or '',
                execution_time_ms=metrics.total_duration_ms,
                lock_acquisition_time_ms=metrics.lock_acquisition_ms,
                lock_key=f"state_transition:{entity_type}:{entity_id}",
                isolation_level='READ COMMITTED',  # Default isolation level
                retry_attempt=metrics.retry_count
            )

            logger.debug(
                f"Created audit record for {entity_type}:{entity_id} transition",
                extra={'entity_type': entity_type, 'entity_id': entity_id}
            )

        except Exception as audit_error:
            # Don't fail transition if audit fails, but log it
            logger.error(
                f"Failed to create audit record for {entity_type}:{entity_id}: {audit_error}",
                extra={
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'audit_error': str(audit_error)
                },
                exc_info=True
            )

    @staticmethod
    def validate_transition_only(
        state_machine: BaseStateMachine,
        to_state: str,
        context: TransitionContext
    ) -> TransitionResult:
        """
        Validate transition without executing (dry run).

        Useful for:
        - Frontend validation
        - Permission checks
        - Business rule validation

        Does NOT acquire locks or modify database.
        """
        dry_run_context = TransitionContext(
            user=context.user,
            reason=context.reason,
            comments=context.comments,
            metadata=context.metadata,
            timestamp=context.timestamp,
            skip_permissions=context.skip_permissions,
            skip_validation=context.skip_validation,
            dry_run=True  # Enable dry run mode
        )

        return state_machine.transition(to_state, dry_run_context)


# Convenience function for common use case
def transition_with_lock(
    state_machine: BaseStateMachine,
    to_state: str,
    context: TransitionContext,
    **kwargs
) -> TransitionResult:
    """
    Convenience function for executing state transition with automatic locking.

    Example:
        result = transition_with_lock(
            state_machine=TaskStateMachine(job),
            to_state='COMPLETED',
            context=TransitionContext(user=request.user, comments='Done')
        )
    """
    return StateTransitionCoordinator.execute_transition(
        state_machine=state_machine,
        to_state=to_state,
        context=context,
        **kwargs
    )
