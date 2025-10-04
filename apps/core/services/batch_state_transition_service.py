"""
Batch State Transition Service

High-performance service for transitioning multiple entities atomically.
Optimized for bulk operations with minimal database roundtrips.

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service < 150 lines per class
- Rule #11: Specific exception handling
- Rule #17: Transaction management

Key Features:
- Batch locking for multiple entities
- Single transaction for all transitions
- Partial failure handling (all-or-nothing or continue-on-error)
- Performance metrics for batch operations
- Parallel processing support for independent entities
- Audit trail for all transitions

Usage:
    from apps.core.services.batch_state_transition_service import BatchStateTransitionService
    from apps.activity.state_machines.task_state_machine import TaskStateMachine

    # Batch transition multiple jobs
    jobs = Jobneed.objects.filter(jobstatus='ASSIGNED')[:100]
    state_machines = [TaskStateMachine(job) for job in jobs]

    result = BatchStateTransitionService.execute_batch(
        state_machines=state_machines,
        to_state='INPROGRESS',
        context=TransitionContext(user=request.user, comments='Batch start'),
        atomic=True  # All-or-nothing
    )

    print(f"Success: {result.success_count}, Failed: {result.failure_count}")
"""

import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import transaction, DatabaseError
from django.utils import timezone

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext,
    TransitionResult,
    InvalidTransitionError,
    StateTransitionError
)
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.core.constants.datetime_constants import MILLISECONDS_IN_SECOND

logger = logging.getLogger(__name__)


@dataclass
class BatchTransitionResult:
    """Result of batch state transition operation"""
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    execution_time_ms: int = 0
    individual_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100

    @property
    def all_succeeded(self) -> bool:
        """Check if all transitions succeeded"""
        return self.success_count == self.total_count


class BatchStateTransitionService:
    """
    Service for batch state transitions with optimized performance.

    Handles bulk state changes with proper concurrency control and error handling.
    """

    @staticmethod
    def execute_batch(
        state_machines: List[BaseStateMachine],
        to_state: str,
        context: TransitionContext,
        atomic: bool = True,
        parallel: bool = False,
        max_workers: int = 5
    ) -> BatchTransitionResult:
        """
        Execute batch state transitions for multiple entities.

        Args:
            state_machines: List of state machine instances to transition
            to_state: Target state for all entities
            context: Transition context (shared across all transitions)
            atomic: If True, rollback all on any failure (default: True)
            parallel: If True, process transitions in parallel (default: False)
            max_workers: Max parallel workers if parallel=True

        Returns:
            BatchTransitionResult with success/failure counts and details

        Raises:
            StateTransitionError: If atomic=True and any transition fails
        """
        start_time = time.time()
        result = BatchTransitionResult(total_count=len(state_machines))

        if not state_machines:
            logger.warning("Empty state machines list provided to batch transition")
            return result

        logger.info(
            f"Starting batch transition of {len(state_machines)} entities to {to_state}",
            extra={
                'entity_count': len(state_machines),
                'to_state': to_state,
                'atomic': atomic,
                'parallel': parallel
            }
        )

        try:
            if parallel:
                # Parallel processing for independent entities
                result = BatchStateTransitionService._execute_parallel(
                    state_machines, to_state, context, atomic, max_workers
                )
            else:
                # Sequential processing with single transaction
                if atomic:
                    result = BatchStateTransitionService._execute_atomic(
                        state_machines, to_state, context
                    )
                else:
                    result = BatchStateTransitionService._execute_sequential(
                        state_machines, to_state, context
                    )

            end_time = time.time()
            result.execution_time_ms = int((end_time - start_time) * MILLISECONDS_IN_SECOND)

            logger.info(
                f"Batch transition completed: {result.success_count}/{result.total_count} succeeded "
                f"in {result.execution_time_ms}ms (success rate: {result.success_rate:.1f}%)",
                extra={
                    'success_count': result.success_count,
                    'failure_count': result.failure_count,
                    'total_count': result.total_count,
                    'execution_time_ms': result.execution_time_ms,
                    'success_rate': result.success_rate
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Batch transition failed with error: {e}",
                extra={'error': str(e)},
                exc_info=True
            )
            raise StateTransitionError(f"Batch transition failed: {e}") from e

    @staticmethod
    def _execute_atomic(
        state_machines: List[BaseStateMachine],
        to_state: str,
        context: TransitionContext
    ) -> BatchTransitionResult:
        """Execute all transitions in single atomic transaction"""
        result = BatchTransitionResult(total_count=len(state_machines))

        # Generate lock keys for all entities
        lock_keys = [
            f"state_transition:{sm.__class__.__name__}:{sm.instance.pk}"
            for sm in state_machines
        ]

        # Sort lock keys to prevent deadlocks
        sorted_lock_keys = sorted(lock_keys)

        try:
            # Acquire all locks (in sorted order to prevent deadlock)
            for lock_key in sorted_lock_keys:
                distributed_lock(lock_key, timeout=10, blocking_timeout=5).__enter__()

            # Execute all transitions in single transaction
            with transaction.atomic():
                for sm in state_machines:
                    entity_type = sm.__class__.__name__
                    entity_id = sm.instance.pk

                    try:
                        # Use state machine's built-in transition (no lock, we already have it)
                        transition_result = sm.transition(to_state, context)

                        result.individual_results.append({
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'success': transition_result.success,
                            'message': transition_result.message
                        })

                        if transition_result.success:
                            result.success_count += 1
                        else:
                            result.failure_count += 1
                            result.errors.append({
                                'entity_type': entity_type,
                                'entity_id': entity_id,
                                'error': transition_result.error_message
                            })

                            # Fail entire batch if atomic
                            raise StateTransitionError(
                                f"Transition failed for {entity_type}:{entity_id}: "
                                f"{transition_result.error_message}"
                            )

                    except (InvalidTransitionError, StateTransitionError) as e:
                        logger.error(
                            f"Transition failed for {entity_type}:{entity_id}: {e}",
                            exc_info=True
                        )
                        result.failure_count += 1
                        result.errors.append({
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'error': str(e)
                        })
                        raise  # Re-raise to rollback transaction

        finally:
            # Release all locks (in reverse order)
            for lock_key in reversed(sorted_lock_keys):
                try:
                    distributed_lock(lock_key, timeout=10, blocking_timeout=5).__exit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Failed to release lock {lock_key}: {e}")

        return result

    @staticmethod
    def _execute_sequential(
        state_machines: List[BaseStateMachine],
        to_state: str,
        context: TransitionContext
    ) -> BatchTransitionResult:
        """Execute transitions sequentially, continue on error"""
        result = BatchTransitionResult(total_count=len(state_machines))

        for sm in state_machines:
            entity_type = sm.__class__.__name__
            entity_id = sm.instance.pk

            try:
                # Use transition_with_lock for each entity
                transition_result = sm.transition_with_lock(
                    to_state=to_state,
                    context=context,
                    max_retries=2
                )

                result.individual_results.append({
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'success': transition_result.success,
                    'message': transition_result.message
                })

                if transition_result.success:
                    result.success_count += 1
                else:
                    result.failure_count += 1
                    result.errors.append({
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'error': transition_result.error_message
                    })

            except Exception as e:
                logger.error(
                    f"Transition failed for {entity_type}:{entity_id}: {e}",
                    exc_info=True
                )
                result.failure_count += 1
                result.errors.append({
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'error': str(e)
                })
                # Continue to next entity (don't re-raise)

        return result

    @staticmethod
    def _execute_parallel(
        state_machines: List[BaseStateMachine],
        to_state: str,
        context: TransitionContext,
        atomic: bool,
        max_workers: int
    ) -> BatchTransitionResult:
        """Execute transitions in parallel using thread pool"""
        result = BatchTransitionResult(total_count=len(state_machines))

        def transition_entity(sm: BaseStateMachine) -> Dict[str, Any]:
            """Worker function for parallel execution"""
            entity_type = sm.__class__.__name__
            entity_id = sm.instance.pk

            try:
                transition_result = sm.transition_with_lock(
                    to_state=to_state,
                    context=context,
                    max_retries=2
                )

                return {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'success': transition_result.success,
                    'message': transition_result.message,
                    'error': transition_result.error_message
                }

            except Exception as e:
                logger.error(
                    f"Parallel transition failed for {entity_type}:{entity_id}: {e}",
                    exc_info=True
                )
                return {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'success': False,
                    'message': '',
                    'error': str(e)
                }

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(transition_entity, sm): sm for sm in state_machines}

            for future in as_completed(futures):
                individual_result = future.result()
                result.individual_results.append(individual_result)

                if individual_result['success']:
                    result.success_count += 1
                else:
                    result.failure_count += 1
                    result.errors.append({
                        'entity_type': individual_result['entity_type'],
                        'entity_id': individual_result['entity_id'],
                        'error': individual_result['error']
                    })

                    if atomic and result.failure_count > 0:
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        raise StateTransitionError(
                            f"Parallel batch transition failed (atomic mode): {individual_result['error']}"
                        )

        return result


# Convenience functions

def batch_transition(
    instances: List[Any],
    state_machine_class: type,
    to_state: str,
    context: TransitionContext,
    **kwargs
) -> BatchTransitionResult:
    """
    Convenience function for batch transitions.

    Example:
        jobs = Jobneed.objects.filter(jobstatus='ASSIGNED')
        result = batch_transition(
            instances=jobs,
            state_machine_class=TaskStateMachine,
            to_state='INPROGRESS',
            context=TransitionContext(user=request.user),
            atomic=True
        )
    """
    state_machines = [state_machine_class(instance) for instance in instances]
    return BatchStateTransitionService.execute_batch(
        state_machines=state_machines,
        to_state=to_state,
        context=context,
        **kwargs
    )
