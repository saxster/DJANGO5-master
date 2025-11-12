"""
Attendance views package.

This package contains all attendance-related views organized by functionality:
- attendance_views: Main attendance tracking
- conveyance_views: Travel expense management
- geofence_views: Geofence tracking
- attendance_sync_views: Sync operations
- bulk_operations: Bulk attendance operations

All views are exported at the package level for backward compatibility.
"""

# Import main attendance views
from .attendance_views import Attendance
from .conveyance_views import Conveyance
from .geofence_views import GeofenceTracking

# Import sync and bulk operation views (if they exist)
try:
    from .attendance_sync_views import AttendanceSyncView, AttendanceChangesView
except ImportError:
    pass

try:
    from .bulk_operations import (
        AttendanceBulkTransitionView,
        AttendanceBulkApproveView,
        AttendanceBulkRejectView,
        AttendanceBulkLockView,
        AttendanceBulkUpdateView,
    )
except ImportError:
    pass

# Explicit __all__ to control namespace (Rule #16: Wildcard Import Prevention)
__all__ = [
    # From attendance_views.py
    'Attendance',

    # From conveyance_views.py
    'Conveyance',

    # From geofence_views.py
    'GeofenceTracking',

    # From attendance_sync_views.py (if exists)
    'AttendanceSyncView',
    'AttendanceChangesView',

    # From bulk_operations.py (if exists)
    'AttendanceBulkTransitionView',
    'AttendanceBulkApproveView',
    'AttendanceBulkRejectView',
    'AttendanceBulkLockView',
    'AttendanceBulkUpdateView',
]
