"""
Ticket Audit Service - Centralized audit logging and compliance tracking

Provides comprehensive audit capabilities across all ticket operations:
- State transitions (via TicketStateMachine)
- Assignment changes (via TicketAssignmentService)
- Workflow operations (via TicketWorkflow)
- Data modifications and access patterns

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines
- Rule #11: Specific exception handling
- Rule #12: Database query optimization
"""

import logging
from typing import Dict, List, Optional, Any, Union, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict

# TYPE_CHECKING import to break circular dependency
# (y_helpdesk.models → .managers → optimized_managers → services → ticket_state_machine → ticket_audit_service → y_helpdesk.models)
if TYPE_CHECKING:
    from apps.y_helpdesk.models import Ticket

# Note: extract_sensitive_fields removed - function not used in this service
# Sensitive field handling is done via SENSITIVE_FIELDS class attribute

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of auditable events."""
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_DELETED = "ticket_deleted"
    STATUS_CHANGED = "status_changed"
    ASSIGNMENT_CHANGED = "assignment_changed"
    ESCALATION_OCCURRED = "escalation_occurred"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"
    WORKFLOW_COMPLETED = "workflow_completed"
    PERMISSION_DENIED = "permission_denied"
    DATA_ACCESSED = "data_accessed"
    BULK_OPERATION = "bulk_operation"


class AuditLevel(Enum):
    """Audit logging levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


@dataclass
class AuditContext:
    """Context information for audit events."""
    user: Optional[AbstractUser]
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    tenant: Optional[str] = None
    business_unit: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class AuditEvent:
    """Structured audit event data."""
    event_type: AuditEventType
    level: AuditLevel
    ticket_id: Optional[int]
    context: AuditContext
    details: Dict[str, Any]
    changes: Optional[Dict[str, Any]] = None
    security_flags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary for logging."""
        return {
            'event_type': self.event_type.value,
            'level': self.level.value,
            'ticket_id': self.ticket_id,
            'timestamp': self.context.timestamp.isoformat(),
            'user_id': self.context.user.id if self.context.user else None,
            'user_name': getattr(self.context.user, 'peoplename', None) if self.context.user else None,
            'session_id': self.context.session_id,
            'ip_address': self.context.ip_address,
            'tenant': self.context.tenant,
            'business_unit': self.context.business_unit,
            'details': self.details,
            'changes': self.changes,
            'security_flags': self.security_flags or []
        }


class TicketAuditService:
    """
    Centralized audit service for ticket operations.

    Provides comprehensive audit logging, compliance tracking,
    and security monitoring for all ticket-related activities.
    """

    # Security-sensitive fields that require special handling
    SENSITIVE_FIELDS = {
        'email', 'mobno', 'password', 'api_key', 'token',
        'credit_card', 'ssn', 'personal_id'
    }

    # Fields that indicate potential security issues
    SECURITY_INDICATORS = {
        'failed_login', 'permission_denied', 'unauthorized_access',
        'data_export', 'bulk_delete', 'admin_override'
    }

    @classmethod
    def log_ticket_creation(
        cls,
        ticket,  # Type hint removed due to circular import (use TYPE_CHECKING for IDE support)
        context: AuditContext,
        additional_details: Optional[Dict] = None
    ) -> None:
        """
        Log ticket creation event.

        Args:
            ticket: Created ticket instance
            context: Audit context
            additional_details: Optional additional details
        """
        details = {
            'ticket_number': ticket.ticketno,
            'priority': ticket.priority,
            'status': ticket.status,
            'category': ticket.ticketcategory.taname if ticket.ticketcategory else None,
            'created_by': ticket.cuser.peoplename if ticket.cuser else None,
            **(additional_details or {})
        }

        event = AuditEvent(
            event_type=AuditEventType.TICKET_CREATED,
            level=AuditLevel.INFO,
            ticket_id=ticket.id,
            context=context,
            details=details
        )

        cls._write_audit_log(event)

    @classmethod
    def log_ticket_update(
        cls,
        ticket,  # Type hint removed due to circular import (use TYPE_CHECKING for IDE support)
        changes: Dict[str, Any],
        context: AuditContext
    ) -> None:
        """
        Log ticket update with field-level change tracking.

        Args:
            ticket: Updated ticket instance
            changes: Dictionary of changed fields (old_value -> new_value)
            context: Audit context
        """
        # Sanitize sensitive data in changes
        sanitized_changes = cls._sanitize_changes(changes)

        # Detect security-sensitive changes
        security_flags = cls._detect_security_flags(changes)

        details = {
            'ticket_number': ticket.ticketno,
            'fields_changed': list(sanitized_changes.keys()),
            'change_count': len(sanitized_changes)
        }

        event = AuditEvent(
            event_type=AuditEventType.TICKET_UPDATED,
            level=AuditLevel.WARNING if security_flags else AuditLevel.INFO,
            ticket_id=ticket.id,
            context=context,
            details=details,
            changes=sanitized_changes,
            security_flags=security_flags
        )

        cls._write_audit_log(event)

    @classmethod
    def log_status_transition(
        cls,
        ticket_id: int,
        old_status: str,
        new_status: str,
        context: AuditContext,
        transition_result: Optional[Dict] = None
    ) -> None:
        """
        Log ticket status transition.

        Args:
            ticket_id: ID of ticket
            old_status: Previous status
            new_status: New status
            context: Audit context
            transition_result: Optional transition validation result
        """
        details = {
            'old_status': old_status,
            'new_status': new_status,
            'transition_valid': transition_result.get('valid', True) if transition_result else True,
            'validation_message': transition_result.get('message') if transition_result else None
        }

        # Flag suspicious transitions
        security_flags = []
        if cls._is_suspicious_transition(old_status, new_status, context):
            security_flags.append('suspicious_status_transition')

        event = AuditEvent(
            event_type=AuditEventType.STATUS_CHANGED,
            level=AuditLevel.WARNING if security_flags else AuditLevel.INFO,
            ticket_id=ticket_id,
            context=context,
            details=details,
            security_flags=security_flags
        )

        cls._write_audit_log(event)

    @classmethod
    def log_assignment_change(
        cls,
        ticket_id: int,
        assignment_result: Dict[str, Any],
        context: AuditContext
    ) -> None:
        """
        Log ticket assignment changes.

        Args:
            ticket_id: ID of ticket
            assignment_result: Result from TicketAssignmentService
            context: Audit context
        """
        details = {
            'assignment_type': assignment_result.get('assignment_type'),
            'previous_assignee': assignment_result.get('previous_assignee'),
            'new_assignee': assignment_result.get('new_assignee'),
            'assignment_success': assignment_result.get('success', False)
        }

        event = AuditEvent(
            event_type=AuditEventType.ASSIGNMENT_CHANGED,
            level=AuditLevel.INFO,
            ticket_id=ticket_id,
            context=context,
            details=details
        )

        cls._write_audit_log(event)

    @classmethod
    def log_escalation(
        cls,
        ticket_id: int,
        escalation_level: int,
        escalation_reason: Optional[str],
        context: AuditContext
    ) -> None:
        """
        Log ticket escalation events.

        Args:
            ticket_id: ID of escalated ticket
            escalation_level: New escalation level
            escalation_reason: Reason for escalation
            context: Audit context
        """
        details = {
            'escalation_level': escalation_level,
            'escalation_reason': escalation_reason,
            'automatic_escalation': context.user is None
        }

        # Flag unusual escalation patterns
        security_flags = []
        if escalation_level > 3:
            security_flags.append('high_escalation_level')

        event = AuditEvent(
            event_type=AuditEventType.ESCALATION_OCCURRED,
            level=AuditLevel.WARNING,
            ticket_id=ticket_id,
            context=context,
            details=details,
            security_flags=security_flags
        )

        cls._write_audit_log(event)

    @classmethod
    def log_permission_denial(
        cls,
        ticket_id: Optional[int],
        attempted_action: str,
        context: AuditContext,
        denial_reason: str
    ) -> None:
        """
        Log permission denial for security monitoring.

        Args:
            ticket_id: ID of ticket (if applicable)
            attempted_action: Action that was denied
            context: Audit context
            denial_reason: Reason for denial
        """
        details = {
            'attempted_action': attempted_action,
            'denial_reason': denial_reason
        }

        event = AuditEvent(
            event_type=AuditEventType.PERMISSION_DENIED,
            level=AuditLevel.SECURITY,
            ticket_id=ticket_id,
            context=context,
            details=details,
            security_flags=['permission_denied']
        )

        cls._write_audit_log(event)

    @classmethod
    def log_bulk_operation(
        cls,
        operation_type: str,
        ticket_ids: List[int],
        context: AuditContext,
        operation_result: Dict[str, Any]
    ) -> None:
        """
        Log bulk operations for compliance tracking.

        Args:
            operation_type: Type of bulk operation
            ticket_ids: List of affected ticket IDs
            context: Audit context
            operation_result: Result of bulk operation
        """
        details = {
            'operation_type': operation_type,
            'ticket_count': len(ticket_ids),
            'affected_tickets': ticket_ids[:10],  # Limit for log size
            'success_count': operation_result.get('success_count', 0),
            'failure_count': operation_result.get('failure_count', 0)
        }

        # Flag large bulk operations
        security_flags = []
        if len(ticket_ids) > 100:
            security_flags.append('large_bulk_operation')

        event = AuditEvent(
            event_type=AuditEventType.BULK_OPERATION,
            level=AuditLevel.WARNING if security_flags else AuditLevel.INFO,
            ticket_id=None,
            context=context,
            details=details,
            security_flags=security_flags
        )

        cls._write_audit_log(event)

    @classmethod
    def get_audit_trail(
        cls,
        ticket_id: int,
        limit: int = 100,
        event_types: Optional[List[AuditEventType]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail for a specific ticket.

        Args:
            ticket_id: ID of ticket
            limit: Maximum number of events to return
            event_types: Optional filter for event types

        Returns:
            List of audit events
        """
        # This would query actual audit storage (database/log files)
        # For now, return placeholder implementation
        return []

    @classmethod
    def _sanitize_changes(cls, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or mask sensitive data from change log."""
        sanitized = {}

        for field, change_data in changes.items():
            if field.lower() in cls.SENSITIVE_FIELDS:
                # Mask sensitive fields
                sanitized[field] = {
                    'old_value': '***MASKED***',
                    'new_value': '***MASKED***',
                    'changed': True
                }
            else:
                sanitized[field] = change_data

        return sanitized

    @classmethod
    def _detect_security_flags(cls, changes: Dict[str, Any]) -> List[str]:
        """Detect security-relevant changes."""
        flags = []

        for field in changes.keys():
            if field.lower() in cls.SECURITY_INDICATORS:
                flags.append(f'security_field_changed_{field}')

        return flags

    @classmethod
    def _is_suspicious_transition(
        cls,
        old_status: str,
        new_status: str,
        context: AuditContext
    ) -> bool:
        """Detect suspicious status transitions."""
        # Example: Direct transition to CLOSED without RESOLVED
        if old_status in ['NEW', 'OPEN'] and new_status == 'CLOSED':
            return True

        # Multiple rapid transitions by same user could be suspicious
        # This would require querying recent transition history

        return False

    @classmethod
    def _write_audit_log(cls, event: AuditEvent) -> None:
        """
        Write audit event to configured storage.

        Compliance enhancement: Now writes to both logger AND persistent database
        for immutable audit trail (SOC 2, HIPAA, GDPR compliance).
        """
        # Convert to structured log format
        log_data = event.to_dict()

        # Use appropriate log level
        if event.level == AuditLevel.CRITICAL:
            logger.critical("AUDIT", extra=log_data)
        elif event.level == AuditLevel.ERROR:
            logger.error("AUDIT", extra=log_data)
        elif event.level == AuditLevel.WARNING:
            logger.warning("AUDIT", extra=log_data)
        elif event.level == AuditLevel.SECURITY:
            logger.critical("SECURITY_AUDIT", extra=log_data)
        else:
            logger.info("AUDIT", extra=log_data)

        # Write to persistent audit database for compliance
        try:
            from apps.y_helpdesk.models.audit_log import TicketAuditLog
            from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

            # Map event type to category
            category_map = {
                'ticket_created': 'modification',
                'ticket_updated': 'modification',
                'ticket_deleted': 'modification',
                'ticket_accessed': 'access',
                'permission_denied': 'security',
                'status_transition': 'workflow',
                'escalation': 'escalation',
            }

            # Get request context if available
            ip_address = None
            user_agent = None
            request_method = None
            request_path = None

            if hasattr(event.context, 'request') and event.context.request:
                request = event.context.request
                ip_address = cls._get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
                request_method = request.method
                request_path = request.path[:500]

            # Create immutable audit log entry
            TicketAuditLog.objects.create(
                event_id=log_data.get('event_id'),
                correlation_id=log_data.get('correlation_id'),
                event_type=event.event_type.value,
                event_category=category_map.get(event.event_type.value, 'modification'),
                severity_level=event.level.value.lower(),
                user=event.context.user if hasattr(event.context, 'user') else None,
                tenant=event.context.user.tenant if (hasattr(event.context, 'user') and event.context.user and hasattr(event.context.user, 'tenant')) else None,
                ticket_id=log_data.get('ticket_id'),
                event_data=log_data,
                old_values=log_data.get('old_values'),
                new_values=log_data.get('new_values'),
                ip_address=ip_address,
                user_agent=user_agent,
                request_method=request_method,
                request_path=request_path,
                timestamp=event.context.timestamp,
            )

            logger.debug(f"Audit log persisted to database: {event.event_type.value}")

        except DATABASE_EXCEPTIONS as e:
            # Don't fail the operation if audit logging fails
            # Just log the error - audit logging is best-effort
            logger.error(
                f"Failed to persist audit log to database: {e}",
                exc_info=True,
                extra={'event_type': event.event_type.value}
            )

    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip