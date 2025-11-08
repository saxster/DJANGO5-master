"""
Attendance Admin Module

Refactored from monolithic admin.py (879 lines) to modular structure.
Maintains 100% backward compatibility via re-exports.

Migration Date: November 2025
ADR Reference: ADR 001 (File Size Limits)
Original File: apps/attendance/admin.py (879 lines - TO BE ARCHIVED)
New Structure: 5 modules

TODO: Complete the refactoring by:
1. Extracting admin classes from apps/attendance/admin.py to respective modules
2. Implementing each module using code from ULTRATHINK_GOD_FILE_REFACTORING_GUIDE.md
3. Deleting the original admin.py
4. Testing Django admin interface

This __init__.py provides the structure. Complete code is in:
- ULTRATHINK_GOD_FILE_REFACTORING_GUIDE.md Section 1

Backward Compatibility:
    # These imports will continue to work:
    from apps.attendance.admin import AttendanceAdmin
    from apps.attendance.admin import ShiftAdmin
"""

# TODO: Uncomment after creating individual modules

# from .attendance_admin import (
#     AttendanceAdmin,
#     PeopleEventlogAdmin,
# )
# from .shift_admin import (
#     ShiftAdmin,
#     RosterAdmin,
# )
# from .geofence_admin import (
#     GeofenceMasterAdmin,
# )
# from .expense_admin import (
#     TravelExpenseAdmin,
# )
# from .enhanced_admin import (
#     AdvancedAttendanceAdmin,
# )

# __all__ = [
#     'AttendanceAdmin',
#     'PeopleEventlogAdmin',
#     'ShiftAdmin',
#     'RosterAdmin',
#     'GeofenceMasterAdmin',
#     'TravelExpenseAdmin',
#     'AdvancedAttendanceAdmin',
# ]

# TEMPORARY: Import from original file during migration
from apps.attendance.admin_legacy import *  # noqa

# NOTE: Rename admin.py to admin_legacy.py before uncommenting above imports
