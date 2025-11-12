"""
Business Logic Utilities Module - DEPRECATED

This module has been refactored into submodules for maintainability.
All imports are preserved for backward compatibility.

NEW STRUCTURE (Phase 4 Refactoring):
  apps/core/utils_new/onboarding/
    ├── wizard.py        - Wizard form processing (257 lines)
    ├── forms.py         - Form utilities (108 lines)
    ├── session.py       - Session management (170 lines)
    ├── instructions.py  - Import instructions (243 lines)
    ├── utilities.py     - Cache and misc utilities (73 lines)
    └── __init__.py      - Package exports (76 lines)

MIGRATION GUIDE:
  OLD: from apps.core.utils_new.business_logic import save_user_session
  NEW: from apps.core.utils_new.onboarding.session import save_user_session
  OR:  from apps.core.utils_new.onboarding import save_user_session

This file will be removed in Q1 2026. Update imports accordingly.
"""

# Re-export all functions from new modules for backward compatibility
from apps.core.utils_new.onboarding.wizard import (
    update_timeline_data,
    update_wizard_form,
    process_wizard_form,
    update_prev_step,
    update_next_step,
    update_other_info,
    update_wizard_steps,
    get_index_for_deletion,
    delete_object,
    delete_unsaved_objects,
)

from apps.core.utils_new.onboarding.forms import (
    initailize_form_fields,
    apply_error_classes,
    get_instance_for_update,
    get_model_obj,
)

from apps.core.utils_new.onboarding.session import (
    save_capsinfo_inside_session,
    save_user_session,
)

from apps.core.utils_new.onboarding.instructions import (
    JobFields,
    Instructions,
)

from apps.core.utils_new.onboarding.utilities import (
    get_appropriate_client_url,
    cache_it,
    get_from_cache,
    save_msg,
)

__all__ = [
    # wizard
    'update_timeline_data',
    'update_wizard_form',
    'process_wizard_form',
    'update_prev_step',
    'update_next_step',
    'update_other_info',
    'update_wizard_steps',
    'get_index_for_deletion',
    'delete_object',
    'delete_unsaved_objects',
    # forms
    'initailize_form_fields',
    'apply_error_classes',
    'get_instance_for_update',
    'get_model_obj',
    # session
    'save_capsinfo_inside_session',
    'save_user_session',
    # instructions
    'JobFields',
    'Instructions',
    # utilities
    'get_appropriate_client_url',
    'cache_it',
    'get_from_cache',
    'save_msg',
]
