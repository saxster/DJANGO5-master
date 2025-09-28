"""
Core Mixins Package

Reusable mixins for eliminating code duplication across views and forms.

Following .claude/rules.md:
- DRY (Don't Repeat Yourself) principle
- Single Responsibility Principle
- Methods < 30 lines (Rule 8)
- Specific exception handling (Rule 11)
"""

from .optimistic_locking import (
    OptimisticLockingMixin,
    StaleObjectError,
    with_optimistic_lock,
)
from .crud_action_mixin import (
    CRUDActionMixin,
    ActionNotImplementedError,
)
from .exception_handling_mixin import (
    ExceptionHandlingMixin,
    with_exception_handling,
)
from .tenant_aware_form_mixin import (
    TenantAwareFormMixin,
    TypeAssistFilterMixin,
)
from .validated_form_mixin import (
    ValidatedFormProcessingMixin,
    StandardFormProcessingMixin,
)

__all__ = [
    'OptimisticLockingMixin',
    'StaleObjectError',
    'with_optimistic_lock',
    'CRUDActionMixin',
    'ActionNotImplementedError',
    'ExceptionHandlingMixin',
    'with_exception_handling',
    'TenantAwareFormMixin',
    'TypeAssistFilterMixin',
    'ValidatedFormProcessingMixin',
    'StandardFormProcessingMixin',
]