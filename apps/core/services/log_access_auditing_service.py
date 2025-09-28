"""
Log Access Auditing Service.

Tracks and audits access to log files for security and compliance:
- Who accessed which log files
- When they were accessed
- What operations were performed
- Role-based access control validation
- Compliance audit trail

CRITICAL: Required for HIPAA, SOC2, and GDPR compliance.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from apps.core.services.base_service import BaseService
from apps.core.exceptions import SecurityException, PermissionDeniedError
from apps.core.middleware.logging_sanitization import sanitized_warning, sanitized_info

logger = logging.getLogger(__name__)


class LogAccessOperation(Enum):
    """Types of log access operations."""
    READ = "read"
    DOWNLOAD = "download"
    DELETE = "delete"
    EXPORT = "export"
    SEARCH = "search"


@dataclass
class LogAccessAuditEntry:
    """Audit entry for log file access."""
    user_id: int
    user_role: str
    log_file: str
    operation: str
    timestamp: datetime
    ip_address: Optional[str] = None
    correlation_id: Optional[str] = None
    access_granted: bool = True
    denial_reason: Optional[str] = None


class LogAccessAuditingService(BaseService):
    """
    Service for auditing access to log files.

    Features:
    1. Track all log file access attempts
    2. Validate role-based access permissions
    3. Generate compliance audit trails
    4. Alert on unauthorized access attempts
    5. Maintain access history
    """

    def __init__(self):
        super().__init__()
        self.access_roles = getattr(
            settings,
            'LOG_ACCESS_ROLES',
            {
                'security_logs': ['superuser', 'security_admin'],
                'application_logs': ['superuser', 'admin', 'developer'],
                'error_logs': ['superuser', 'admin', 'developer'],
                'audit_logs': ['superuser', 'compliance_officer']
            }
        )
        self.audit_cache_key_prefix = 'log_access_audit'
        self.audit_retention_days = 365

    @BaseService.monitor_performance("validate_log_access")
    def validate_log_access(
        self,
        user,
        log_file_type: str,
        operation: LogAccessOperation,
        request = None
    ) -> bool:
        """
        Validate if user has permission to access a log file.

        Args:
            user: User attempting access
            log_file_type: Type of log (security_logs, application_logs, etc.)
            operation: Operation being performed
            request: HTTP request object (optional)

        Returns:
            bool: True if access granted, raises PermissionDeniedError otherwise
        """
        try:
            user_role = self._get_user_role(user)
            allowed_roles = self.access_roles.get(log_file_type, [])

            access_granted = user_role in allowed_roles

            audit_entry = LogAccessAuditEntry(
                user_id=user.id,
                user_role=user_role,
                log_file=log_file_type,
                operation=operation.value,
                timestamp=timezone.now(),
                ip_address=self._get_client_ip(request) if request else None,
                correlation_id=getattr(request, 'correlation_id', None) if request else None,
                access_granted=access_granted,
                denial_reason=None if access_granted else f"Role '{user_role}' not in allowed roles: {allowed_roles}"
            )

            self._record_audit_entry(audit_entry)

            if not access_granted:
                sanitized_warning(
                    logger,
                    "Unauthorized log access attempt",
                    extra={
                        'user_id': user.id,
                        'user_role': user_role,
                        'log_file_type': log_file_type,
                        'operation': operation.value,
                        'correlation_id': audit_entry.correlation_id
                    }
                )

                raise PermissionDeniedError(
                    f"User does not have permission to access {log_file_type}",
                    details={
                        'user_role': user_role,
                        'required_roles': allowed_roles,
                        'correlation_id': audit_entry.correlation_id
                    }
                )

            sanitized_info(
                logger,
                "Log access granted",
                extra={
                    'user_id': user.id,
                    'log_file_type': log_file_type,
                    'operation': operation.value,
                    'correlation_id': audit_entry.correlation_id
                }
            )

            return True

        except PermissionDeniedError:
            raise
        except (TypeError, ValidationError, ValueError) as e:
            self.logger.error(
                f"Log access validation error: {type(e).__name__}",
                extra={'error': str(e)}
            )
            raise SecurityException(
                "Log access validation failed",
                details={'error_type': type(e).__name__}
            )

    def _get_user_role(self, user) -> str:
        """Determine user's highest role for log access."""
        if user.is_superuser:
            return 'superuser'
        elif hasattr(user, 'is_staff') and user.is_staff:
            if hasattr(user, 'groups'):
                groups = user.groups.values_list('name', flat=True)
                if 'security_admin' in groups:
                    return 'security_admin'
                elif 'compliance_officer' in groups:
                    return 'compliance_officer'
                elif 'admin' in groups:
                    return 'admin'
            return 'staff'
        return 'user'

    def _get_client_ip(self, request) -> Optional[str]:
        """Extract client IP from request."""
        if not request:
            return None

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _record_audit_entry(self, entry: LogAccessAuditEntry):
        """Record audit entry for compliance tracking."""
        cache_key = f"{self.audit_cache_key_prefix}:{entry.timestamp.date()}:{entry.user_id}"

        existing_entries = cache.get(cache_key, [])
        existing_entries.append(self._entry_to_dict(entry))

        cache.set(cache_key, existing_entries, timeout=self.audit_retention_days * 86400)

        if not entry.access_granted:
            self._alert_unauthorized_access(entry)

    def _alert_unauthorized_access(self, entry: LogAccessAuditEntry):
        """Send alert for unauthorized log access attempts."""
        sanitized_warning(
            logger,
            "SECURITY ALERT: Unauthorized log access attempt",
            extra={
                'user_id': entry.user_id,
                'user_role': entry.user_role,
                'log_file': entry.log_file,
                'operation': entry.operation,
                'timestamp': entry.timestamp.isoformat(),
                'correlation_id': entry.correlation_id
            }
        )

    @BaseService.monitor_performance("get_access_audit_trail")
    def get_access_audit_trail(
        self,
        user_id: Optional[int] = None,
        log_file_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get audit trail for log access.

        Args:
            user_id: Filter by user (optional)
            log_file_type: Filter by log file type (optional)
            start_date: Start date for audit trail
            end_date: End date for audit trail

        Returns:
            List of audit entries
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()

        audit_entries = []
        current_date = start_date.date()

        while current_date <= end_date.date():
            if user_id:
                cache_key = f"{self.audit_cache_key_prefix}:{current_date}:{user_id}"
                entries = cache.get(cache_key, [])
                audit_entries.extend(entries)
            else:
                pattern = f"{self.audit_cache_key_prefix}:{current_date}:*"
                keys = cache.keys(pattern) if hasattr(cache, 'keys') else []
                for key in keys:
                    entries = cache.get(key, [])
                    audit_entries.extend(entries)

            current_date += timedelta(days=1)

        if log_file_type:
            audit_entries = [e for e in audit_entries if e.get('log_file') == log_file_type]

        return sorted(audit_entries, key=lambda x: x.get('timestamp', ''), reverse=True)

    def _entry_to_dict(self, entry: LogAccessAuditEntry) -> Dict:
        """Convert audit entry to dictionary."""
        return {
            'user_id': entry.user_id,
            'user_role': entry.user_role,
            'log_file': entry.log_file,
            'operation': entry.operation,
            'timestamp': entry.timestamp.isoformat(),
            'ip_address': entry.ip_address,
            'correlation_id': entry.correlation_id,
            'access_granted': entry.access_granted,
            'denial_reason': entry.denial_reason
        }