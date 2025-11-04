"""
Attendance models package.

Contains all models for the attendance app, modularized for maintainability.
"""

from apps.attendance.models.audit_log import (
    AttendanceAccessLog,
    AuditLogRetentionPolicy
)
from apps.attendance.models.consent import (
    ConsentPolicy,
    EmployeeConsentLog,
    ConsentRequirement
)

__all__ = [
    'AttendanceAccessLog',
    'AuditLogRetentionPolicy',
    'ConsentPolicy',
    'EmployeeConsentLog',
    'ConsentRequirement',
]
