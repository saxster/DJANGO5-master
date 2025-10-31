"""
Scheduler Admin Package - Backward Compatibility Shim

NOTE: This file exists for compatibility only!

The file previously named admin.py (1,311 lines) was NOT Django admin - it contained
ONLY import-export Resource classes for bulk data upload/update of tasks and tours.

It has been renamed to: import_export_resources.py (for clarity)

If you're looking for:
- Task/Tour import/export: see import_export_resources.py
- Django admin interfaces: Jobs are managed via activity.admin (Job model is in activity app)

Migration Date: 2025-10-12
Author: Claude Code (Admin Simplification Initiative)
"""

# Import from new location for backward compatibility
from .import_export_resources import *  # noqa: F401, F403

# Note: This file contains NO Django admin classes
# All admin registrations for Job model are in apps/activity/admin/
