"""
People admin module - Modular admin interface structure.

This module provides 100% backward compatibility with the original admin.py file.
All imports like `from apps.peoples.admin import PeopleAdmin` will continue to work.

Structure:
    - base.py: Shared utilities, helper functions, widgets
    - import_export_resources.py: All Resource classes for import/export
    - people_admin.py: People model admin + PeopleResource
    - group_admin.py: Pgroup, Pgbelonging admins + Resources
    - capability_admin.py: Capability admin + Resource
    - device_admin.py: Device trust & security admins (Sprint 1 - Oct 2025)
    - security_admin.py: Login attempt & account lockout admins (existing)
    - session_admin.py: User session & activity log admins (existing)

Compliance:
    - CLAUDE.md architectural limits: Each file <200 lines
    - No breaking changes to existing imports
    - All admin registrations functional
"""

# Import all helper functions and widgets from base
from .base import (
    save_people_passwd,
    clean_value,
    default_ta,
    PgroupFKW,
    PeopleFKW,
    SiteFKW,
)

# Import all Resource classes for import/export
from .import_export_resources import (
    PeopleResource,
    PeopleResourceUpdate,
    GroupResource,
    GroupResourceUpdate,
    GroupBelongingResource,
    GroupBelongingResourceUpdate,
    CapabilityResource,
)

# Import all Admin classes
from .people_admin import PeopleAdmin
from .group_admin import GroupAdmin, PgbelongingAdmin
from .capability_admin import CapabilityAdmin
from .device_admin import (
    DeviceRegistrationAdmin,
    DeviceRiskEventAdmin,
    DeviceRiskEventInline,
)

# Import existing security and session admins (if available)
try:
    from .security_admin import LoginAttemptLogAdmin, AccountLockoutAdmin
except ImportError:
    # Security admin may not exist in all environments
    pass

try:
    from .session_admin import UserSessionAdmin, SessionActivityLogAdmin
except ImportError:
    # Session admin may not exist in all environments
    pass


# Expose all classes for backward compatibility
__all__ = [
    # Helper functions
    "save_people_passwd",
    "clean_value",
    "default_ta",
    # Widgets
    "PgroupFKW",
    "PeopleFKW",
    "SiteFKW",
    # Resources
    "PeopleResource",
    "PeopleResourceUpdate",
    "GroupResource",
    "GroupResourceUpdate",
    "GroupBelongingResource",
    "GroupBelongingResourceUpdate",
    "CapabilityResource",
    # Admin classes
    "PeopleAdmin",
    "GroupAdmin",
    "PgbelongingAdmin",
    "CapabilityAdmin",
    "DeviceRegistrationAdmin",
    "DeviceRiskEventAdmin",
    "DeviceRiskEventInline",
]
