"""
Attendance Admin Package
========================

This module exposes the production-ready attendance admin registrations by
importing the new modular implementations under ``apps.attendance.admin``.

Prior to this change ``apps.attendance.admin`` simply re-imported
``admin_legacy`` which meant engineers would keep editing the legacy file.
The new structure keeps the modernized admin in-package while the old
``admin_legacy`` module now re-exports these classes for backward
compatibility (e.g., tests or scripts that still import it directly).
"""

from .main_admin import (
    PostAdmin,
    PostAssignmentAdmin,
    PostOrderAcknowledgementAdmin,
    PeopleEventlogAdmin,
    GeofenceAdmin,
)
from .enhanced_admin import (
    AttendanceAccessLogAdmin,
    ConsentPolicyAdmin,
    EmployeeConsentLogAdmin,
    AttendancePhotoAdmin,
    UserBehaviorProfileAdmin,
    FraudAlertAdmin,
    SyncConflictAdmin,
)

__all__ = [
    # Core attendance admin registrations
    'PostAdmin',
    'PostAssignmentAdmin',
    'PostOrderAcknowledgementAdmin',
    'PeopleEventlogAdmin',
    'GeofenceAdmin',
    # Enhanced modules (audit, consent, fraud, sync)
    'AttendanceAccessLogAdmin',
    'ConsentPolicyAdmin',
    'EmployeeConsentLogAdmin',
    'AttendancePhotoAdmin',
    'UserBehaviorProfileAdmin',
    'FraudAlertAdmin',
    'SyncConflictAdmin',
]
