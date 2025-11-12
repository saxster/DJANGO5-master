"""
Onboarding Utilities Package

Provides utilities for onboarding workflows including:
- Multi-step wizard form processing and state management
- Form field initialization and validation
- User session initialization and capability management
- Import instructions and bulk data handling
"""

from .wizard import (
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

from .forms import (
    initailize_form_fields,
    apply_error_classes,
    get_instance_for_update,
    get_model_obj,
)

from .session import (
    save_capsinfo_inside_session,
    save_user_session,
)

from .instructions import (
    JobFields,
    Instructions,
)

from .utilities import (
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
