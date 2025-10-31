"""
Saga Context Manager - Distributed Transaction Coordination

Manages saga state persistence for safe distributed transaction rollback.
Integrates with apps.core.models.saga_state.SagaState model.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management

Sprint 3: Saga State Persistence
"""

import logging
from typing import Dict, Any, Optional, Callable
from django.db import transaction, DatabaseError
from apps.core.models import SagaState
from apps.core.exceptions import SystemException

logger = logging.getLogger(__name__)


class SagaContextManager:
    """
    Manage saga state persistence for distributed transactions.

    Provides rollback capability by persisting intermediate state.
    """

    def create_saga(self, saga_id: str, operation_type: str, total_steps: int = 0) -> SagaState:
        """
        Create new saga with persistent state.

        Args:
            saga_id: Unique saga identifier
            operation_type: Type of operation (e.g., 'guard_tour_creation')
            total_steps: Total number of steps

        Returns:
            SagaState instance

        Raises:
            SystemException: If saga creation fails
        """
        try:
            saga = SagaState.objects.create(
                saga_id=saga_id,
                operation_type=operation_type,
                total_steps=total_steps,
                status='created'
            )

            logger.info(f"Created saga {saga_id} for {operation_type}")
            return saga

        except DatabaseError as e:
            logger.error(f"Failed to create saga {saga_id}: {e}")
            raise SystemException(f"Saga creation failed: {str(e)}")

    def record_step(
        self,
        saga_id: str,
        step_name: str,
        step_result: Any,
        step_callback: Optional[Callable] = None
    ) -> bool:
        """
        Record successful step completion with persistent state.

        Args:
            saga_id: Saga identifier
            step_name: Name of completed step
            step_result: Result data to persist
            step_callback: Optional callback for additional processing

        Returns:
            bool: True if recorded successfully

        Raises:
            SystemException: If persistence fails
        """
        try:
            saga = SagaState.objects.get(saga_id=saga_id)

            # Store result in context
            saga.record_step_completion(step_name, step_result)

            # Execute callback if provided
            if step_callback:
                step_callback(step_result)

            logger.debug(f"Recorded step '{step_name}' for saga {saga_id}")
            return True

        except SagaState.DoesNotExist:
            logger.error(f"Saga {saga_id} not found")
            raise SystemException(f"Saga {saga_id} not found")
        except DatabaseError as e:
            logger.error(f"Failed to record step {step_name} for saga {saga_id}: {e}")
            raise SystemException(f"Step recording failed: {str(e)}")

    def get_saga_context(self, saga_id: str) -> Dict[str, Any]:
        """
        Get complete saga context for rollback or recovery.

        Args:
            saga_id: Saga identifier

        Returns:
            Dict containing all step results and metadata

        Raises:
            SystemException: If saga not found
        """
        try:
            saga = SagaState.objects.get(saga_id=saga_id)
            return saga.context_data

        except SagaState.DoesNotExist:
            logger.error(f"Saga {saga_id} not found")
            raise SystemException(f"Saga {saga_id} not found")

    def commit_saga(self, saga_id: str):
        """
        Mark saga as successfully committed.

        Args:
            saga_id: Saga identifier
        """
        try:
            saga = SagaState.objects.get(saga_id=saga_id)
            saga.commit()

            logger.info(f"Saga {saga_id} committed")

        except SagaState.DoesNotExist:
            logger.warning(f"Cannot commit - saga {saga_id} not found")
        except DatabaseError as e:
            logger.error(f"Failed to commit saga {saga_id}: {e}")

    def rollback_saga(self, saga_id: str, error_step: str, error_message: str):
        """
        Mark saga as rolled back and log error.

        Args:
            saga_id: Saga identifier
            error_step: Step where error occurred
            error_message: Error description
        """
        try:
            saga = SagaState.objects.get(saga_id=saga_id)
            saga.rollback(error_step, error_message)

            logger.warning(f"Saga {saga_id} rolled back at step {error_step}")

        except SagaState.DoesNotExist:
            logger.warning(f"Cannot rollback - saga {saga_id} not found")
        except DatabaseError as e:
            logger.error(f"Failed to rollback saga {saga_id}: {e}")

    def cleanup_stale_sagas(self, threshold_days: int = 7) -> int:
        """
        Clean up completed sagas older than threshold.

        Args:
            threshold_days: Days before saga is considered stale

        Returns:
            int: Number of sagas cleaned up
        """
        try:
            stale_sagas = SagaState.objects.filter(
                status__in=['committed', 'rolled_back']
            )

            deleted_count = 0
            for saga in stale_sagas:
                if saga.is_stale(threshold_days):
                    saga.delete()
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} stale sagas")
            return deleted_count

        except DatabaseError as e:
            logger.error(f"Failed to cleanup stale sagas: {e}")
            return 0


# Global saga manager instance
saga_manager = SagaContextManager()
