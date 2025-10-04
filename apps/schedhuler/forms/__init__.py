"""
Scheduling Forms Module

This module provides both the original forms and the new refactored forms
for backward compatibility during the transition period.

New forms use base classes and mixins to reduce code duplication.
"""

# Import refactored forms (recommended)
from .refactored_forms import (
    InternalTourForm,
    ExternalTourForm,
    TaskForm,
    InternalTourJobneedForm,
    InternalTourCheckpointForm,
)

# Import base forms for extension
from .base_forms import (
    BaseSchedulingForm,
    BaseTourForm,
    BaseTaskForm,
    BaseJobneedForm,
)

# Legacy compatibility imports - these import the refactored versions
from .refactored_forms import (
    Schd_I_TourJobForm,
    Schd_E_TourJobForm,
    SchdTaskFormJob,
)

# Import original forms for gradual migration
# These will be deprecated once refactoring is complete
try:
    # Use importlib to safely import legacy forms.py without sys.path manipulation
    import importlib.util
    import os

    forms_path = os.path.join(os.path.dirname(__file__), '..', 'forms.py')
    if os.path.exists(forms_path):
        # Load module spec from file path
        spec = importlib.util.spec_from_file_location("schedhuler_legacy_forms", forms_path)
        if spec and spec.loader:
            # Import the module without modifying sys.path
            original_forms = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(original_forms)

            # Make original forms available with _Original suffix
            OriginalInternalTourForm = getattr(original_forms, 'Schd_I_TourJobForm', None)
            OriginalExternalTourForm = getattr(original_forms, 'Schd_E_TourJobForm', None)
            OriginalTaskForm = getattr(original_forms, 'SchdTaskFormJob', None)
        else:
            raise ImportError("Could not load module spec for legacy forms")
    else:
        # Legacy forms.py doesn't exist
        OriginalInternalTourForm = None
        OriginalExternalTourForm = None
        OriginalTaskForm = None

except (ImportError, AttributeError, OSError) as e:
    # Original forms not available - using refactored versions only
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Legacy forms not loaded: {e}")
    OriginalInternalTourForm = None
    OriginalExternalTourForm = None
    OriginalTaskForm = None

__all__ = [
    # New refactored forms (recommended)
    'InternalTourForm',
    'ExternalTourForm',
    'TaskForm',
    'InternalTourJobneedForm',
    'InternalTourCheckpointForm',

    # Base forms for extension
    'BaseSchedulingForm',
    'BaseTourForm',
    'BaseTaskForm',
    'BaseJobneedForm',

    # Legacy compatibility
    'Schd_I_TourJobForm',
    'Schd_E_TourJobForm',
    'SchdTaskFormJob',

    # Original forms for migration comparison
    'OriginalInternalTourForm',
    'OriginalExternalTourForm',
    'OriginalTaskForm',
]