"""
Backward Compatibility Shim for apps.peoples.models

DEPRECATION NOTICE:
This file provides backward compatibility for imports from the old monolithic
models.py file. All model definitions have been moved to the models/ directory
for better maintainability and compliance with .claude/rules.md Rule #7.

New code should import directly from models/ subdirectory:
    from apps.peoples.models import People  # Still works via this shim
    from apps.peoples.models.user_model import People  # Explicit import

Migration Guide: See docs/people-model-migration-guide.md

Timeline: This compatibility shim will be maintained for 6 months (until March 2026)
after which direct imports from models/ directory will be required.

Complies with:
- Rule #7: Model complexity < 150 lines (all models split)
- Rule #14: Utility function size < 50 lines (upload function delegated)
- Rule #16: Explicit __all__ control for wildcard imports
"""

import logging
import warnings
from django.utils import timezone

from . import constants as people_constants

logger = logging.getLogger("django")

# Import all models from the refactored models/ directory
from .models.base_model import BaseModel
from .models.user_model import People
from .models.profile_model import PeopleProfile
from .models.organizational_model import PeopleOrganizational
from .models.group_model import PermissionGroup, Pgroup
from .models.membership_model import Pgbelonging
from .models.capability_model import Capability


def peoplejson():
    """
    DEPRECATED: Default JSON structure for people_extras field.

    This function is maintained for backward compatibility only.
    New code should use default values defined in constants.py
    """
    warnings.warn(
        "peoplejson() is deprecated. Use constants.default_people_extras instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return people_constants.peoplejson()


def upload_peopleimg(instance, filename):
    """
    DEPRECATED: Upload path generator for people images.

    This function has been replaced by SecureFileUploadService for better
    security, maintainability, and compliance with Rule #14 (< 50 lines).

    Args:
        instance: People model instance
        filename: Original uploaded filename

    Returns:
        str: Secure relative path for file storage

    Raises:
        ValidationError: If security validation fails
        RuntimeError: When secure upload delegation is unavailable

    Migration:
        Old: peopleimg = models.ImageField(upload_to=upload_peopleimg)
        New: from apps.peoples.services import SecureFileUploadService
             peopleimg = models.ImageField(
                 upload_to=SecureFileUploadService.generate_secure_upload_path
             )

    Deprecation: This compatibility wrapper will be removed in March 2026.
    """
    warnings.warn(
        "upload_peopleimg() is deprecated. Use SecureFileUploadService.generate_secure_upload_path() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    try:
        from .services.file_upload_service import SecureFileUploadService
        return SecureFileUploadService.generate_secure_upload_path(instance, filename)
    except (ImportError, AttributeError, TypeError, ValueError) as e:
        logger.error(
            "Failed to delegate to SecureFileUploadService; rejecting upload path.",
            extra={
                'error_type': type(e).__name__,
                'instance_id': getattr(instance, 'id', None),
                'filename': filename
            },
            exc_info=True
        )
        raise RuntimeError(
            "Secure file upload service is unavailable; aborting insecure upload path."
        ) from e


def now():
    """
    DEPRECATED: Timezone-aware current datetime without microseconds.

    This function is maintained for backward compatibility only.
    New code should use django.utils.timezone.now() directly.
    """
    warnings.warn(
        "now() is deprecated. Use django.utils.timezone.now() directly.",
        DeprecationWarning,
        stacklevel=2
    )
    return timezone.now().replace(microsecond=0)


# Explicit exports for wildcard imports (Rule #16 compliance)
__all__ = [
    # Models (primary exports)
    'BaseModel',
    'People',
    'PeopleProfile',
    'PeopleOrganizational',
    'PermissionGroup',
    'Pgroup',
    'Pgbelonging',
    'Capability',

    # Deprecated utility functions (for backward compatibility only)
    'peoplejson',
    'upload_peopleimg',
    'now',
]
