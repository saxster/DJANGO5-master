"""
State Machine Framework

Universal state machine implementation for all entities:
- Work Orders
- Tasks/Jobs
- Attendance
- Tickets (enhanced)

Features:
- Permission-based transition validation
- Optimistic locking integration
- Audit logging
- Rollback support
"""

from .base import (
    BaseStateMachine,
    TransitionContext,
    TransitionResult,
    StateTransitionError,
    InvalidTransitionError,
    PermissionDeniedError,
)

__all__ = [
    'BaseStateMachine',
    'TransitionContext',
    'TransitionResult',
    'StateTransitionError',
    'InvalidTransitionError',
    'PermissionDeniedError',
]
