"""
Attendance middleware package.

Contains middleware for:
- Audit logging
- Performance monitoring
- Security checks
"""

from apps.attendance.middleware.audit_middleware import AttendanceAuditMiddleware

__all__ = ['AttendanceAuditMiddleware']
