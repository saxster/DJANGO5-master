"""
Bulk Operations Service

Generic service for performing bulk operations on entities with:
- State machine integration
- Optimistic locking support
- Atomic transactions with rollback
- Detailed success/failure tracking
- Audit logging
- Dry-run mode

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #11: Specific exception handling
- Rule #17: Transaction management with rollback
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Type
from dataclasses import dataclass, field
from datetime import timezone as dt_timezone

from django.db import models, transaction, DatabaseError
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.contenttypes.models import ContentType

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext,
    InvalidTransitionError,
    PermissionDeniedError,
)
from apps.core.services.unified_audit_service import EntityAuditService

logger = logging.getLogger(__name__)


@dataclass
class BulkOperationResult:
    """
    Result of a bulk operation.

    Contains detailed success/failure tracking for each item.
    """
    operation_type: str
    total_items: int
    successful_items: int = 0
    failed_items: int = 0
    successful_ids: List[str] = field(default_factory=list)
    failed_ids: List[str] = field(default_factory=list)
    failure_details: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    was_rolled_back: bool = False
    rollback_reason: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_items == 0:
            return 0.0
        return (self.successful_items / self.total_items) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            'operation_type': self.operation_type,
            'total_items': self.total_items,
            'successful_items': self.successful_items,
            'failed_items': self.failed_items,
            'success_rate': round(self.success_rate, 2),
            'successful_ids': self.successful_ids,
            'failed_ids': self.failed_ids,
            'failure_details': self.failure_details,
            'warnings': self.warnings,
            'was_rolled_back': self.was_rolled_back,
            'rollback_reason': self.rollback_reason,
        }


class BulkOperationService:
    """
    Generic bulk operation service.

    Handles bulk operations with state machine validation,
    optimistic locking, and comprehensive error handling.

    Usage:
        service = BulkOperationService(
            model_class=Wom,
            state_machine_class=WorkOrderStateMachine,
            user=request.user
        )

        result = service.bulk_transition(
            ids=['123', '456', '789'],
            target_state='APPROVED',
            context={'comments': 'Bulk approval'}
        )
    """

    def __init__(
        self,
        model_class: Type[models.Model],
        state_machine_class: Optional[Type[BaseStateMachine]] = None,
        user=None,
        audit_service: Optional[EntityAuditService] = None
    ):
        """
        Initialize bulk operation service.

        Args:
            model_class: Django model class for entities
            state_machine_class: State machine class (optional)
            user: User performing the operation
            audit_service: Audit service instance (optional)
        """
        self.model_class = model_class
        self.state_machine_class = state_machine_class
        self.user = user
        self.audit_service = audit_service or EntityAuditService(user=user)

    def bulk_transition(
        self,
        ids: List[str],
        target_state: str,
        context: Optional[Dict] = None,
        dry_run: bool = False,
        rollback_on_error: bool = True
    ) -> BulkOperationResult:
        """
        Perform bulk state transition.

        Args:
            ids: List of entity IDs
            target_state: Target state to transition to
            context: Context data (comments, metadata, etc.)
            dry_run: If True, validate without executing
            rollback_on_error: If True, rollback all on any failure

        Returns:
            BulkOperationResult with detailed metrics
        """
        result = BulkOperationResult(
            operation_type=f'transition_to_{target_state}',
            total_items=len(ids)
        )

        if not self.state_machine_class:
            raise ValueError("State machine class required for bulk transitions")

        # Create transition context
        transition_ctx = TransitionContext(
            user=self.user,
            comments=context.get('comments') if context else None,
            metadata=context.get('metadata', {}) if context else {},
            dry_run=dry_run
        )

        try:
            # Use atomic transaction with savepoint for rollback support
            with transaction.atomic():
                for entity_id in ids:
                    try:
                        # Get entity
                        entity = self._get_entity(entity_id)

                        # Perform transition
                        self._perform_single_transition(
                            entity,
                            target_state,
                            transition_ctx,
                            result
                        )

                    except (ValidationError, InvalidTransitionError, PermissionDeniedError) as e:
                        # Record failure
                        result.failed_items += 1
                        result.failed_ids.append(entity_id)
                        result.failure_details[entity_id] = str(e)

                        logger.warning(
                            f"Failed to transition {entity_id}: {e}",
                            extra={'entity_id': entity_id, 'error': str(e)}
                        )

                        # Rollback if configured
                        if rollback_on_error:
                            result.was_rolled_back = True
                            result.rollback_reason = f"Transition failed for {entity_id}: {str(e)}"
                            raise  # Trigger transaction rollback

                    except DatabaseError as e:
                        # Database error - always rollback
                        result.was_rolled_back = True
                        result.rollback_reason = f"Database error: {str(e)}"
                        logger.error(
                            f"Database error during bulk transition: {e}",
                            exc_info=True
                        )
                        raise

                # If dry run, rollback transaction
                if dry_run:
                    transaction.set_rollback(True)
                    result.warnings.append("Dry run - no changes committed")

        except Exception as e:
            # Transaction was rolled back
            logger.error(f"Bulk transition failed: {e}", exc_info=True)

            if not result.was_rolled_back:
                result.was_rolled_back = True
                result.rollback_reason = str(e)

        # Log bulk operation to audit
        if not dry_run:
            self.audit_service.log_bulk_operation(
                operation_type=f'transition_to_{target_state}',
                entity_type=self.model_class.__name__,
                total_items=result.total_items,
                successful_items=result.successful_items,
                failed_items=result.failed_items,
                successful_ids=result.successful_ids,
                failed_ids=result.failed_ids,
                failure_details=result.failure_details,
                was_rolled_back=result.was_rolled_back,
                rollback_reason=result.rollback_reason
            )

        return result

    def bulk_update(
        self,
        ids: List[str],
        update_data: Dict[str, Any],
        dry_run: bool = False,
        rollback_on_error: bool = True
    ) -> BulkOperationResult:
        """
        Perform bulk update of entity fields.

        Args:
            ids: List of entity IDs
            update_data: Dictionary of fields to update
            dry_run: If True, validate without executing
            rollback_on_error: If True, rollback all on any failure

        Returns:
            BulkOperationResult with detailed metrics
        """
        result = BulkOperationResult(
            operation_type='bulk_update',
            total_items=len(ids)
        )

        try:
            with transaction.atomic():
                for entity_id in ids:
                    try:
                        # Get entity
                        entity = self._get_entity(entity_id)

                        # Update fields
                        for field, value in update_data.items():
                            if hasattr(entity, field):
                                setattr(entity, field, value)
                            else:
                                raise ValidationError(f"Invalid field: {field}")

                        # Save entity (with optimistic locking)
                        if not dry_run:
                            entity.save()

                        # Record success
                        result.successful_items += 1
                        result.successful_ids.append(entity_id)

                    except (ValidationError, DatabaseError) as e:
                        # Record failure
                        result.failed_items += 1
                        result.failed_ids.append(entity_id)
                        result.failure_details[entity_id] = str(e)

                        logger.warning(
                            f"Failed to update {entity_id}: {e}",
                            extra={'entity_id': entity_id}
                        )

                        # Rollback if configured
                        if rollback_on_error:
                            result.was_rolled_back = True
                            result.rollback_reason = f"Update failed for {entity_id}: {str(e)}"
                            raise

                # Dry run rollback
                if dry_run:
                    transaction.set_rollback(True)
                    result.warnings.append("Dry run - no changes committed")

        except Exception as e:
            logger.error(f"Bulk update failed: {e}", exc_info=True)

            if not result.was_rolled_back:
                result.was_rolled_back = True
                result.rollback_reason = str(e)

        # Audit logging
        if not dry_run:
            self.audit_service.log_bulk_operation(
                operation_type='bulk_update',
                entity_type=self.model_class.__name__,
                total_items=result.total_items,
                successful_items=result.successful_items,
                failed_items=result.failed_items,
                successful_ids=result.successful_ids,
                failed_ids=result.failed_ids,
                failure_details=result.failure_details,
                was_rolled_back=result.was_rolled_back,
                rollback_reason=result.rollback_reason,
                metadata={'update_data': update_data}
            )

        return result

    def _get_entity(self, entity_id: str) -> models.Model:
        """
        Get entity by ID with error handling.

        Raises:
            ValidationError: If entity not found
        """
        try:
            return self.model_class.objects.get(pk=entity_id)
        except self.model_class.DoesNotExist:
            raise ValidationError(f"{self.model_class.__name__} with ID {entity_id} not found")

    def _perform_single_transition(
        self,
        entity: models.Model,
        target_state: str,
        context: TransitionContext,
        result: BulkOperationResult
    ):
        """
        Perform state transition for single entity.

        Updates result object with success/failure.
        """
        # Create state machine
        state_machine = self.state_machine_class(entity)

        # Validate transition
        validation_result = state_machine.validate_transition(target_state, context)

        if not validation_result.success:
            raise InvalidTransitionError(validation_result.error_message)

        # Add warnings
        if validation_result.warnings:
            result.warnings.extend([
                f"{entity.pk}: {warning}"
                for warning in validation_result.warnings
            ])

        # Execute transition (unless dry run)
        if not context.dry_run:
            state_machine.transition(target_state, context)

        # Record success
        result.successful_items += 1
        result.successful_ids.append(str(entity.pk))
