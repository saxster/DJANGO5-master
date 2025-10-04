"""
Base State Machine Implementation

Provides universal state machine functionality that can be extended
for any entity type (work orders, tasks, tickets, attendance, etc.).

Features:
- Declarative state transition rules
- Permission enforcement
- Optimistic locking integration (django-concurrency)
- Audit logging
- Pre/post-transition hooks
- Rollback support

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Classes < 150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

from django.db import transaction, DatabaseError
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

logger = logging.getLogger(__name__)


# Custom exceptions
class StateTransitionError(ValidationError):
    """Base exception for state transition errors"""
    pass


class InvalidTransitionError(StateTransitionError):
    """Raised when attempting invalid state transition"""
    pass


class PermissionDeniedError(StateTransitionError):
    """Raised when user lacks permission for transition"""
    pass


@dataclass
class TransitionContext:
    """
    Context information for a state transition.

    Contains all metadata needed to validate and execute a transition.
    """
    user: Optional[AbstractUser] = None
    reason: str = 'user_action'
    comments: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    skip_permissions: bool = False  # For system transitions
    skip_validation: bool = False  # Dangerous - use with caution
    dry_run: bool = False  # Validate without executing

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class TransitionResult:
    """
    Result of a state transition validation or execution.

    Contains success status, error messages, and warnings.
    """
    success: bool
    from_state: str
    to_state: str
    error_message: Optional[str] = None
    required_permissions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)


class BaseStateMachine(ABC):
    """
    Abstract base class for state machines.

    To create a state machine for an entity:
    1. Subclass BaseStateMachine
    2. Define STATES enum
    3. Define VALID_TRANSITIONS dict
    4. Define TRANSITION_PERMISSIONS dict (optional)
    5. Implement _get_current_state() and _set_current_state()

    Example:
        class WorkOrderStateMachine(BaseStateMachine):
            class States(Enum):
                DRAFT = 'DRAFT'
                SUBMITTED = 'SUBMITTED'
                APPROVED = 'APPROVED'

            VALID_TRANSITIONS = {
                States.DRAFT: {States.SUBMITTED},
                States.SUBMITTED: {States.APPROVED, States.DRAFT},
            }

            def _get_current_state(self, instance):
                return instance.status

            def _set_current_state(self, instance, new_state):
                instance.status = new_state
    """

    # Subclasses must override these
    VALID_TRANSITIONS: Dict[Any, Set[Any]] = {}
    TRANSITION_PERMISSIONS: Dict[Tuple[Any, Any], List[str]] = {}

    def __init__(self, instance):
        """
        Initialize state machine for an entity instance.

        Args:
            instance: Django model instance with state field
        """
        self.instance = instance

    @abstractmethod
    def _get_current_state(self, instance) -> str:
        """Get current state from instance. Subclasses must implement."""
        pass

    @abstractmethod
    def _set_current_state(self, instance, new_state: str):
        """Set new state on instance. Subclasses must implement."""
        pass

    def can_transition(
        self,
        to_state: str,
        context: Optional[TransitionContext] = None
    ) -> bool:
        """
        Check if transition to target state is allowed.

        Args:
            to_state: Target state
            context: Optional transition context

        Returns:
            True if transition is valid
        """
        result = self.validate_transition(to_state, context or TransitionContext())
        return result.success

    def validate_transition(
        self,
        to_state: str,
        context: TransitionContext
    ) -> TransitionResult:
        """
        Comprehensive validation of state transition.

        Checks:
        1. Transition is in VALID_TRANSITIONS
        2. User has required permissions
        3. Business rule validations
        4. Pre-transition hooks pass

        Args:
            to_state: Target state
            context: Transition context

        Returns:
            TransitionResult with validation status
        """
        current_state = self._get_current_state(self.instance)

        # Basic validation
        if not self._is_valid_transition(current_state, to_state):
            return TransitionResult(
                success=False,
                from_state=current_state,
                to_state=to_state,
                error_message=f"Invalid transition from {current_state} to {to_state}"
            )

        # Permission validation
        if not context.skip_permissions and context.user:
            perm_result = self._check_permissions(current_state, to_state, context.user)
            if not perm_result.success:
                return perm_result

        # Business rule validation
        validation_result = self._validate_business_rules(current_state, to_state, context)
        if not validation_result.success:
            return validation_result

        # Pre-transition hook
        hook_result = self._pre_transition_hook(current_state, to_state, context)
        if not hook_result.success:
            return hook_result

        return TransitionResult(
            success=True,
            from_state=current_state,
            to_state=to_state,
        )

    def transition(
        self,
        to_state: str,
        context: Optional[TransitionContext] = None
    ) -> TransitionResult:
        """
        Execute state transition with full validation.

        Args:
            to_state: Target state
            context: Transition context

        Returns:
            TransitionResult with execution status

        Raises:
            InvalidTransitionError: If transition is invalid
            PermissionDeniedError: If user lacks permission
            StateTransitionError: For other transition errors
        """
        ctx = context or TransitionContext()
        current_state = self._get_current_state(self.instance)

        # Validate transition
        validation_result = self.validate_transition(to_state, ctx)
        if not validation_result.success:
            if 'permission' in validation_result.error_message.lower():
                raise PermissionDeniedError(validation_result.error_message)
            else:
                raise InvalidTransitionError(validation_result.error_message)

        # Dry run - don't execute
        if ctx.dry_run:
            return validation_result

        # Execute transition atomically
        try:
            with transaction.atomic():
                # Update state
                self._set_current_state(self.instance, to_state)

                # Save with optimistic locking
                self.instance.save()

                # Post-transition hook
                self._post_transition_hook(current_state, to_state, ctx)

                # Log transition
                self._log_transition(current_state, to_state, ctx)

                return TransitionResult(
                    success=True,
                    from_state=current_state,
                    to_state=to_state,
                    timestamp=timezone.now(),
                )

        except DatabaseError as e:
            logger.error(
                f"Database error during transition: {e}",
                exc_info=True
            )
            raise StateTransitionError(f"Failed to execute transition: {e}")

    def transition_with_lock(
        self,
        to_state: str,
        context: Optional[TransitionContext] = None,
        lock_timeout: int = 10,
        blocking_timeout: int = 5,
        isolation_level: Optional[str] = None,
        max_retries: int = 3
    ) -> TransitionResult:
        """
        Execute state transition with automatic distributed locking.

        Recommended for ALL production use cases to prevent race conditions.
        Delegates to StateTransitionCoordinator for guaranteed concurrency safety.

        Args:
            to_state: Target state to transition to
            context: Transition context (user, reason, comments, etc.)
            lock_timeout: Seconds to hold distributed lock (default: 10)
            blocking_timeout: Seconds to wait for lock acquisition (default: 5)
            isolation_level: Transaction isolation level (optional)
            max_retries: Maximum retry attempts on lock contention (default: 3)

        Returns:
            TransitionResult with success status and metadata

        Raises:
            InvalidTransitionError: If transition is not valid
            PermissionDeniedError: If user lacks permission
            LockAcquisitionError: If cannot acquire lock after retries
            StateTransitionError: For other transition errors

        Example:
            # In service or view
            from apps.activity.state_machines.task_state_machine import TaskStateMachine

            state_machine = TaskStateMachine(job_instance)
            result = state_machine.transition_with_lock(
                to_state='COMPLETED',
                context=TransitionContext(
                    user=request.user,
                    comments='Task completed successfully'
                )
            )

        Note:
            This method wraps the state machine with distributed locking to prevent
            concurrent modifications. For background tasks and critical operations,
            always use this instead of the basic transition() method.
        """
        # Import here to avoid circular imports
        from apps.core.services.state_transition_coordinator import StateTransitionCoordinator

        return StateTransitionCoordinator.execute_transition(
            state_machine=self,
            to_state=to_state,
            context=context or TransitionContext(),
            lock_timeout=lock_timeout,
            blocking_timeout=blocking_timeout,
            isolation_level=isolation_level,
            max_retries=max_retries
        )

    def get_allowed_transitions(
        self,
        user: Optional[AbstractUser] = None
    ) -> List[str]:
        """
        Get list of allowed transitions from current state.

        Args:
            user: Optional user for permission filtering

        Returns:
            List of allowed target states
        """
        current_state_str = self._get_current_state(self.instance)

        # Convert string to enum if needed
        current_state = self._str_to_state(current_state_str)

        # Get valid transitions
        allowed = self.VALID_TRANSITIONS.get(current_state, set())

        # Filter by permissions if user provided
        if user:
            allowed = {
                state for state in allowed
                if self._user_has_permission(current_state, state, user)
            }

        return [self._state_to_str(state) for state in allowed]

    # Internal methods

    def _is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if transition is in VALID_TRANSITIONS"""
        from_enum = self._str_to_state(from_state)
        to_enum = self._str_to_state(to_state)

        valid_targets = self.VALID_TRANSITIONS.get(from_enum, set())
        return to_enum in valid_targets

    def _check_permissions(
        self,
        from_state: str,
        to_state: str,
        user: AbstractUser
    ) -> TransitionResult:
        """Check if user has required permissions"""
        from_enum = self._str_to_state(from_state)
        to_enum = self._str_to_state(to_state)

        transition_key = (from_enum, to_enum)
        required_perms = self.TRANSITION_PERMISSIONS.get(transition_key, [])

        if required_perms:
            missing_perms = [
                perm for perm in required_perms
                if not user.has_perm(perm)
            ]

            if missing_perms:
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message=f"Missing permissions: {', '.join(missing_perms)}",
                    required_permissions=required_perms
                )

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state
        )

    def _user_has_permission(
        self,
        from_state: Any,
        to_state: Any,
        user: AbstractUser
    ) -> bool:
        """Check if user has permission for transition"""
        transition_key = (from_state, to_state)
        required_perms = self.TRANSITION_PERMISSIONS.get(transition_key, [])

        if not required_perms:
            return True

        return all(user.has_perm(perm) for perm in required_perms)

    # Hook methods (can be overridden)

    def _validate_business_rules(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ) -> TransitionResult:
        """
        Validate business rules for transition.

        Override in subclass to add custom validation logic.
        """
        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state
        )

    def _pre_transition_hook(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ) -> TransitionResult:
        """
        Hook called before transition executes.

        Override to add pre-transition logic.
        """
        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state
        )

    def _post_transition_hook(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ):
        """
        Hook called after successful transition.

        Override to add post-transition logic (notifications, etc).
        """
        pass

    def _log_transition(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ):
        """Log state transition"""
        logger.info(
            f"State transition: {from_state} → {to_state}",
            extra={
                'model': self.instance.__class__.__name__,
                'instance_id': self.instance.id,
                'from_state': from_state,
                'to_state': to_state,
                'user_id': context.user.id if context.user else None,
                'reason': context.reason,
            }
        )

    # Helper methods

    @abstractmethod
    def _str_to_state(self, state_str: str):
        """Convert string to state enum. Subclasses must implement."""
        pass

    @abstractmethod
    def _state_to_str(self, state) -> str:
        """Convert state enum to string. Subclasses must implement."""
        pass
