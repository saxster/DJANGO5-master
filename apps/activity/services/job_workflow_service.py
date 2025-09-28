"""
Job Workflow Service - Atomic state management with race condition prevention

This service centralizes job workflow operations to prevent race conditions
in parent-child job updates and status transitions.

Following .claude/rules.md:
- Service layer pattern (Rule 8: View Method Size Limits)
- Specific exception handling (Rule 11)
- Database query optimization (Rule 12)
- Transaction.atomic() for consistency
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.activity.models.job_model import Job, Jobneed
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class InvalidWorkflowTransitionError(ValidationError):
    """Raised when attempting invalid job status transition"""
    pass


class JobWorkflowService:
    """
    Atomic job workflow state management service

    Prevents race conditions in:
    - Parent-child job updates
    - Job status transitions
    - Concurrent checkpoint modifications
    """

    # Valid job status transitions
    VALID_TRANSITIONS = {
        'ASSIGNED': ['INPROGRESS', 'AUTOCLOSED'],
        'INPROGRESS': ['COMPLETED', 'PARTIALLYCOMPLETED', 'AUTOCLOSED'],
        'COMPLETED': [],  # Terminal state
        'AUTOCLOSED': [],  # Terminal state
        'PARTIALLYCOMPLETED': ['COMPLETED', 'AUTOCLOSED'],
        'MAINTENANCE': ['WORKING', 'STANDBY'],
        'STANDBY': ['WORKING', 'MAINTENANCE'],
        'WORKING': ['MAINTENANCE', 'COMPLETED']
    }

    @classmethod
    @transaction.atomic
    def update_checkpoint_with_parent(
        cls,
        child_id: int,
        updates: Dict[str, Any],
        parent_id: int,
        user
    ) -> Tuple[Job, Job]:
        """
        Atomically update child checkpoint AND parent job timestamp

        Prevents race condition where concurrent child updates corrupt parent state.
        Uses distributed lock + select_for_update for multi-layer protection.

        Args:
            child_id: ID of child checkpoint to update
            updates: Dictionary of field updates for child
            parent_id: ID of parent job
            user: User performing the update

        Returns:
            Tuple of (updated_child, updated_parent)

        Raises:
            LockAcquisitionError: If cannot acquire distributed lock
            Job.DoesNotExist: If child or parent not found
            IntegrityError: If update violates database constraints
        """
        lock_key = f"parent_job_update:{parent_id}"

        with distributed_lock(lock_key, timeout=15, blocking_timeout=10):
            try:
                # Lock both parent and child for exclusive access
                parent = Job.objects.select_for_update().get(pk=parent_id)
                child = Job.objects.select_for_update().get(pk=child_id)

                # Apply updates to child
                for field, value in updates.items():
                    setattr(child, field, value)

                child.muser = user
                child.mdtz = timezone.now()
                child.save()

                # Update parent timestamp atomically
                parent.mdtz = timezone.now()
                parent.muser = user
                parent.save(update_fields=['mdtz', 'muser'])

                logger.info(
                    f"Updated child job {child_id} and parent {parent_id}",
                    extra={'child_id': child_id, 'parent_id': parent_id}
                )

                return child, parent

            except Job.DoesNotExist as e:
                logger.error(
                    f"Job not found: child={child_id}, parent={parent_id}",
                    exc_info=True
                )
                raise
            except IntegrityError as e:
                logger.error(
                    f"Integrity error updating job {child_id}",
                    exc_info=True
                )
                raise

    @classmethod
    @transaction.atomic
    def transition_jobneed_status(
        cls,
        jobneed_id: int,
        new_status: str,
        user,
        validate_transition: bool = True
    ) -> Jobneed:
        """
        Atomically transition jobneed to new status with validation

        Args:
            jobneed_id: ID of jobneed to update
            new_status: Target status
            user: User performing transition
            validate_transition: Whether to validate state transition

        Returns:
            Updated jobneed instance

        Raises:
            InvalidWorkflowTransitionError: If transition invalid
            LockAcquisitionError: If cannot acquire lock
        """
        lock_key = f"jobneed_status:{jobneed_id}"

        with distributed_lock(lock_key, timeout=10, blocking_timeout=5):
            try:
                jobneed = Jobneed.objects.select_for_update().get(pk=jobneed_id)
                old_status = jobneed.jobstatus

                # Validate transition if required
                if validate_transition:
                    if not cls._is_valid_transition(old_status, new_status):
                        raise InvalidWorkflowTransitionError(
                            f"Invalid status transition: {old_status} → {new_status}"
                        )

                # Apply status update
                jobneed.jobstatus = new_status
                jobneed.muser = user
                jobneed.mdtz = timezone.now()
                jobneed.save(update_fields=['jobstatus', 'muser', 'mdtz'])

                logger.info(
                    f"Jobneed {jobneed_id} status: {old_status} → {new_status}",
                    extra={
                        'jobneed_id': jobneed_id,
                        'old_status': old_status,
                        'new_status': new_status
                    }
                )

                return jobneed

            except Jobneed.DoesNotExist:
                logger.error(f"Jobneed {jobneed_id} not found")
                raise

    @classmethod
    def _is_valid_transition(cls, current_status: str, new_status: str) -> bool:
        """
        Check if status transition is valid

        Args:
            current_status: Current job status
            new_status: Target status

        Returns:
            True if transition is valid
        """
        if current_status not in cls.VALID_TRANSITIONS:
            logger.warning(f"Unknown current status: {current_status}")
            return True  # Allow unknown statuses for backwards compatibility

        allowed_transitions = cls.VALID_TRANSITIONS[current_status]
        return new_status in allowed_transitions

    @classmethod
    @transaction.atomic
    def bulk_update_child_checkpoints(
        cls,
        parent_id: int,
        child_updates: List[Dict[str, Any]],
        user
    ) -> List[Job]:
        """
        Atomically update multiple child checkpoints of same parent

        Args:
            parent_id: Parent job ID
            child_updates: List of dicts with 'id' and update fields
            user: User performing updates

        Returns:
            List of updated child jobs
        """
        lock_key = f"parent_bulk_update:{parent_id}"

        with distributed_lock(lock_key, timeout=20, blocking_timeout=15):
            try:
                # Lock parent for exclusive access
                parent = Job.objects.select_for_update().get(pk=parent_id)

                # Lock all children
                child_ids = [update['id'] for update in child_updates]
                children = Job.objects.select_for_update().filter(
                    pk__in=child_ids,
                    parent_id=parent_id
                )

                updated_children = []
                for child in children:
                    # Find matching updates
                    updates = next(
                        (u for u in child_updates if u['id'] == child.id),
                        None
                    )
                    if updates:
                        for field, value in updates.items():
                            if field != 'id':
                                setattr(child, field, value)

                        child.muser = user
                        child.mdtz = timezone.now()
                        child.save()
                        updated_children.append(child)

                # Update parent timestamp once
                parent.mdtz = timezone.now()
                parent.muser = user
                parent.save(update_fields=['mdtz', 'muser'])

                logger.info(
                    f"Bulk updated {len(updated_children)} children of parent {parent_id}"
                )

                return updated_children

            except Job.DoesNotExist:
                logger.error(f"Parent job {parent_id} not found")
                raise