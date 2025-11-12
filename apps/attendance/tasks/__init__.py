"""
Attendance Celery tasks package.

Contains async tasks for:
- Audit logging
- Data archival
- Fraud detection
- Analytics processing
"""

from apps.attendance.tasks.audit_tasks import (
    create_audit_log_async,
    batch_create_audit_logs,
    cleanup_old_audit_logs,
    analyze_suspicious_access,
)

__all__ = [
    'create_audit_log_async',
    'batch_create_audit_logs',
    'cleanup_old_audit_logs',
    'analyze_suspicious_access',
]
