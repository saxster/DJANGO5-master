"""
Audit Logging Service for People Operations

Tracks all CRUD operations with correlation IDs for security and compliance.
Integrates with security monitoring infrastructure.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from django.utils import timezone
from django.http import HttpRequest

from apps.core.services.base_service import BaseService, monitor_service_performance

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Audit action types."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"


@dataclass
class AuditLogEntry:
    """Audit log entry structure."""
    action: str
    entity_type: str
    entity_id: Optional[int]
    user_id: Optional[int]
    correlation_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class AuditLoggingService(BaseService):
    """Service for comprehensive audit logging of people operations."""

    @monitor_service_performance("log_audit_event")
    def log_audit_event(
        self,
        action: AuditAction,
        entity_type: str,
        entity_id: Optional[int],
        user: Any,
        request: Optional[HttpRequest] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event with full context.

        Args:
            action: Type of action performed
            entity_type: Type of entity (People, Capability, etc.)
            entity_id: ID of entity affected
            user: User performing action
            request: HTTP request object (for IP and user agent)
            metadata: Additional metadata to log
        """
        entry = AuditLogEntry(
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=getattr(user, 'id', None),
            correlation_id=getattr(request, 'correlation_id', None) if request else None,
            ip_address=self._get_client_ip(request) if request else None,
            user_agent=self._get_user_agent(request) if request else None,
            timestamp=timezone.now().isoformat(),
            metadata=metadata
        )

        self._write_audit_log(entry)

    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """Extract client IP from request (< 15 lines)."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _get_user_agent(self, request: HttpRequest) -> Optional[str]:
        """Extract user agent from request."""
        return request.META.get('HTTP_USER_AGENT', 'Unknown')

    def _write_audit_log(self, entry: AuditLogEntry) -> None:
        """Write audit log entry (< 20 lines)."""
        self.logger.info(
            f"AUDIT: {entry.action} {entry.entity_type}",
            extra={
                'audit_action': entry.action,
                'entity_type': entry.entity_type,
                'entity_id': entry.entity_id,
                'user_id': entry.user_id,
                'correlation_id': entry.correlation_id,
                'ip_address': entry.ip_address,
                'user_agent': entry.user_agent,
                'timestamp': entry.timestamp,
                'metadata': entry.metadata
            }
        )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "AuditLoggingService"