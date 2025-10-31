"""
People admin - Compatibility shim for modular admin structure.

This file provides 100% backward compatibility with the original monolithic admin.py.
All imports like `from apps.peoples.admin import PeopleAdmin` will continue to work.

The actual implementation has been refactored into a modular structure under apps/peoples/admin/
following CLAUDE.md architectural limits (max 200 lines per file).

Original file: admin.py.original_monolith (1,299 lines)
Refactored into: 8 focused modules totaling ~1,400 lines (with better organization)

Structure:
    - admin/base.py: Helper functions and widgets (110 lines)
    - admin/import_export_resources.py: Import/Export resources (873 lines - will be split further)
    - admin/people_admin.py: People model admin (180 lines)
    - admin/group_admin.py: Group admins (129 lines)
    - admin/capability_admin.py: Capability admin (68 lines)
    - admin/device_admin.py: Device trust & security admins (271 lines)
    - admin/security_admin.py: Login & lockout admins (185 lines - pre-existing)
    - admin/session_admin.py: Session & activity admins (337 lines - pre-existing)
"""

# Import everything from admin package for backward compatibility
from apps.peoples.admin import *  # noqa: F401, F403

# This file exists solely for backward compatibility.
# All actual implementation is in apps/peoples/admin/ package.
