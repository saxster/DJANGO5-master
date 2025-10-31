"""
Question Admin Module - Backward Compatibility Layer.

This module provides 100% backward compatibility for the refactored question admin.
All resource classes, admin classes, widgets, and validators are re-exported.

Migration Date: 2025-10-10
Original File: apps/activity/admin/question_admin.py (2,048 lines)
New Structure: 10 domain-focused modules

Before Refactoring:
- 1 monolithic file (2,048 lines - 10.2x over limit)
- 8 Resource classes + 5 Widgets + 1 Admin class
- Duplicate validation logic across classes
- Hard to navigate and maintain

After Refactoring:
- 10 focused modules (avg 200 lines per file)
- Shared validation logic (validators.py)
- Centralized constants (base.py)
- Reusable widgets (widgets.py)
- Clear separation: CREATE vs UPDATE resources

Usage:
    # Old import (still works via this __init__.py):
    from apps.activity.admin.question_admin import QuestionResource

    # New import (recommended for clarity):
    from apps.activity.admin.question.question_create import QuestionResource
"""

# ============================================================================
# Base Utilities and Constants
# ============================================================================

from .base import (
    default_ta,
    AUTHORIZED_ANSWER_TYPES,
    AUTHORIZED_QUESTIONSET_TYPES,
    VALID_AVPT_TYPES,
)

# Re-export additional helpers from base
from apps.core.utils_new.db_utils import (
    get_or_create_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_qset,
    get_or_create_none_question,
)

# ============================================================================
# Validators (for advanced customization)
# ============================================================================

from .validators import (
    NaNHandler,
    AnswerTypeValidator,
    NumericValidator,
    OptionsValidator,
    AVPTValidator,
)

# ============================================================================
# Custom Widgets
# ============================================================================

from .widgets import (
    ArrayFieldWidget,
    QsetFKW,
    QuesFKW,
    QsetFKWUpdate,
    QuesFKWUpdate,
)

# ============================================================================
# Question Resources and Admin
# ============================================================================

from .question_create import QuestionResource
from .question_update import QuestionResourceUpdate
from .admin import QuestionAdmin

# ============================================================================
# QuestionSet Resources (Admin not registered by default)
# ============================================================================

from .questionset_create import QuestionSetResource
from .questionset_update import QuestionSetResourceUpdate

# ============================================================================
# QuestionSetBelonging Resources (Admin not registered by default)
# ============================================================================

from .belonging_create import QuestionSetBelongingResource
from .belonging_update import QuestionSetBelongingResourceUpdate

# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Base helpers
    "default_ta",
    "get_or_create_none_typeassist",
    "get_or_create_none_bv",
    "get_or_create_none_qset",
    "get_or_create_none_question",
    # Constants
    "AUTHORIZED_ANSWER_TYPES",
    "AUTHORIZED_QUESTIONSET_TYPES",
    "VALID_AVPT_TYPES",
    # Validators
    "NaNHandler",
    "AnswerTypeValidator",
    "NumericValidator",
    "OptionsValidator",
    "AVPTValidator",
    # Widgets
    "ArrayFieldWidget",
    "QsetFKW",
    "QuesFKW",
    "QsetFKWUpdate",
    "QuesFKWUpdate",
    # Question resources
    "QuestionResource",
    "QuestionResourceUpdate",
    "QuestionAdmin",
    # QuestionSet resources
    "QuestionSetResource",
    "QuestionSetResourceUpdate",
    # QuestionSetBelonging resources
    "QuestionSetBelongingResource",
    "QuestionSetBelongingResourceUpdate",
]
