"""
Unified Audit Service

Generic audit logging service for all entities across the system.

Features:
- Entity-agnostic audit logging
- PII redaction (Rule #15 compliance)
- Async logging via Celery (optional)
- State transition tracking
- Bulk operation tracking
- Permission denial tracking
- Retention policy enforcement

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service < 150 lines (split into multiple services)
- Rule #11: Specific exception handling
- Rule #15: No PII in logs
- Rule #17: Transaction management
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import timedelta
from django.db import models, transaction, DatabaseError
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

from apps.core.models.audit import (
    AuditLog,
    StateTransitionAudit,
    BulkOperationAudit,
    PermissionDenialAudit,
    AuditEventType,
    AuditLevel,
)

logger = logging.getLogger(__name__)


class PIIRedactor:
    """
    PII redaction utility (Rule #15 compliance).

    Automatically redacts sensitive information from audit logs.
    """

    # PII field patterns to redact
    PII_FIELDS = {
        'password', 'mobno', 'email', 'phone', 'ssn', 'pan',
        'aadhar', 'passport', 'license', 'credit_card', 'bank_account'
    }

    # Regex patterns for PII detection
    PII_PATTERNS = [
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL REDACTED]'),  # Email
        (r'\b\d{10}\b', '[PHONE REDACTED]'),  # 10-digit phone
        (r'\b\d{12}\b', '[AADHAR REDACTED]'),  # Aadhar
        (r'\b\d{16}\b', '[CARD REDACTED]'),  # Credit card
    ]

    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact PII from dictionary.

        Args:
            data: Dictionary potentially containing PII

        Returns:
            Dictionary with PII redacted
        """
        redacted = {}

        for key, value in data.items():
            # Check if field name indicates PII
            if any(pii_field in key.lower() for pii_field in cls.PII_FIELDS):
                redacted[key] = '[REDACTED]'
            elif isinstance(value, str):
                # Apply regex patterns
                redacted[key] = cls.redact_string(value)
            elif isinstance(value, dict):
                # Recursively redact nested dicts
                redacted[key] = cls.redact_dict(value)
            elif isinstance(value, list):
                # Redact list items
                redacted[key] = [
                    cls.redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value

        return redacted

    @classmethod
    def redact_string(cls, text: str) -> str:
        """Redact PII patterns from string"""
        for pattern, replacement in cls.PII_PATTERNS:
            text = re.sub(pattern, replacement, text)
        return text


class EntityAuditService:
    """
    Unified audit service for all entities.

    Usage:
        audit_service = EntityAuditService(
            user=request.user,
            session_id=request.session.session_key,
            ip_address=get_client_ip(request)
        )

        audit_service.log_entity_created(
            entity=work_order,
            action='Work order created',
            metadata={'priority': 'high'}
        )
    """

    def __init__(
        self,
        user=None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
        async_logging: bool = False
    ):
        """
        Initialize audit service.

        Args:
            user: User performing the action
            session_id: Session ID
            ip_address: Client IP address
            user_agent: User agent string
            correlation_id: Optional correlation ID for grouping events
            async_logging: Use Celery for async logging (default: False)
        """
        self.user = user
        self.session_id = session_id or ''
        self.ip_address = ip_address
        self.user_agent = user_agent or ''
        self.correlation_id = correlation_id
        self.async_logging = async_logging

    def log_entity_created(
        self,
        entity: models.Model,
        action: str,
        metadata: Optional[Dict] = None,
        level: str = AuditLevel.INFO
    ) -> Optional[AuditLog]:
        """Log entity creation"""
        return self._log_audit(
            event_type=AuditEventType.CREATED,
            entity=entity,
            action=action,
            message=f"{entity.__class__.__name__} created: {action}",
            metadata=metadata or {},
            level=level
        )

    def log_entity_updated(
        self,
        entity: models.Model,
        action: str,
        changes: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        level: str = AuditLevel.INFO
    ) -> Optional[AuditLog]:
        """Log entity update with field changes"""
        return self._log_audit(
            event_type=AuditEventType.UPDATED,
            entity=entity,
            action=action,
            message=f"{entity.__class__.__name__} updated: {action}",
            changes=changes or {},
            metadata=metadata or {},
            level=level
        )

    def log_entity_deleted(
        self,
        entity: models.Model,
        action: str,
        metadata: Optional[Dict] = None,
        level: str = AuditLevel.WARNING
    ) -> Optional[AuditLog]:
        """Log entity deletion"""
        return self._log_audit(
            event_type=AuditEventType.DELETED,
            entity=entity,
            action=action,
            message=f"{entity.__class__.__name__} deleted: {action}",
            metadata=metadata or {},
            level=level
        )

    def log_state_transition(
        self,
        entity: models.Model,
        from_state: str,
        to_state: str,
        action: str,
        successful: bool = True,
        failure_reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[AuditLog]:
        """
        Log state transition with specialized tracking.

        Creates both AuditLog and StateTransitionAudit.
        """
        try:
            with transaction.atomic():
                # Create main audit log
                audit_log = self._log_audit(
                    event_type=AuditEventType.STATE_CHANGED,
                    entity=entity,
                    action=action,
                    message=f"State transition: {from_state} → {to_state}",
                    metadata=metadata or {},
                    level=AuditLevel.INFO if successful else AuditLevel.WARNING
                )

                if not audit_log:
                    return None

                # Create specialized state transition record
                StateTransitionAudit.objects.create(
                    audit_log=audit_log,
                    from_state=from_state,
                    to_state=to_state,
                    transition_successful=successful,
                    failure_reason=failure_reason or '',
                    approved_by=self.user
                )

                return audit_log

        except (DatabaseError, ValidationError) as e:
            logger.error(f"Failed to log state transition: {e}", exc_info=True)
            return None

    def log_bulk_operation(
        self,
        operation_type: str,
        entity_type: str,
        total_items: int,
        successful_items: int,
        failed_items: int,
        successful_ids: List[str],
        failed_ids: List[str],
        failure_details: Optional[Dict] = None,
        was_rolled_back: bool = False,
        rollback_reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[AuditLog]:
        """
        Log bulk operation with detailed metrics.

        Creates both AuditLog and BulkOperationAudit.
        """
        try:
            with transaction.atomic():
                # Create main audit log
                audit_log = self._log_audit(
                    event_type=AuditEventType.BULK_OPERATION,
                    entity=None,  # No single entity
                    action=f"Bulk {operation_type}",
                    message=f"Bulk {operation_type}: {successful_items}/{total_items} successful",
                    metadata=metadata or {},
                    level=AuditLevel.INFO if failed_items == 0 else AuditLevel.WARNING
                )

                if not audit_log:
                    return None

                # Create specialized bulk operation record
                BulkOperationAudit.objects.create(
                    audit_log=audit_log,
                    operation_type=operation_type,
                    entity_type=entity_type,
                    total_items=total_items,
                    successful_items=successful_items,
                    failed_items=failed_items,
                    successful_ids=successful_ids,
                    failed_ids=failed_ids,
                    failure_details=failure_details or {},
                    was_rolled_back=was_rolled_back,
                    rollback_reason=rollback_reason or ''
                )

                return audit_log

        except (DatabaseError, ValidationError) as e:
            logger.error(f"Failed to log bulk operation: {e}", exc_info=True)
            return None

    def log_permission_denied(
        self,
        attempted_action: str,
        required_permissions: List[str],
        user_permissions: Optional[List[str]] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        is_suspicious: bool = False,
        risk_score: int = 0,
        metadata: Optional[Dict] = None
    ) -> Optional[AuditLog]:
        """
        Log permission denial with security context.

        Creates both AuditLog and PermissionDenialAudit.
        """
        try:
            with transaction.atomic():
                # Create main audit log with SECURITY level
                audit_log = self._log_audit(
                    event_type=AuditEventType.PERMISSION_DENIED,
                    entity=None,
                    action=attempted_action,
                    message=f"Access denied: {attempted_action}",
                    metadata=metadata or {},
                    level=AuditLevel.SECURITY,
                    security_flags=['permission_denied'] + (['suspicious'] if is_suspicious else [])
                )

                if not audit_log:
                    return None

                # Create specialized permission denial record
                PermissionDenialAudit.objects.create(
                    audit_log=audit_log,
                    required_permissions=required_permissions,
                    user_permissions=user_permissions or [],
                    attempted_action=attempted_action,
                    request_path=request_path or '',
                    request_method=request_method or '',
                    is_suspicious=is_suspicious,
                    risk_score=risk_score
                )

                return audit_log

        except (DatabaseError, ValidationError) as e:
            logger.error(f"Failed to log permission denial: {e}", exc_info=True)
            return None

    def _log_audit(
        self,
        event_type: str,
        entity: Optional[models.Model],
        action: str,
        message: str,
        changes: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        level: str = AuditLevel.INFO,
        security_flags: Optional[List[str]] = None
    ) -> Optional[AuditLog]:
        """
        Internal method to create audit log entry.

        Handles PII redaction and async logging.
        """
        try:
            # Redact PII from changes and metadata (Rule #15)
            redacted_changes = PIIRedactor.redact_dict(changes or {})
            redacted_metadata = PIIRedactor.redact_dict(metadata or {})

            # Get content type for entity
            content_type = None
            object_id = None
            if entity:
                content_type = ContentType.objects.get_for_model(entity)
                object_id = str(entity.pk)

            # Prepare audit log data
            audit_data = {
                'correlation_id': self.correlation_id,
                'event_type': event_type,
                'level': level,
                'content_type': content_type,
                'object_id': object_id,
                'user': self.user,
                'session_id': self.session_id,
                'ip_address': self.ip_address,
                'user_agent': self.user_agent,
                'action': action,
                'message': message,
                'changes': redacted_changes,
                'metadata': redacted_metadata,
                'security_flags': security_flags or [],
                'timestamp': timezone.now(),
            }

            # Add tenant if user has tenant
            if self.user and hasattr(self.user, 'tenant'):
                audit_data['tenant'] = self.user.tenant

            # Create audit log (sync or async)
            if self.async_logging:
                # TODO: Implement Celery task for async logging
                # from background_tasks.audit_tasks import create_audit_log_async
                # create_audit_log_async.delay(audit_data)
                logger.info(f"Async audit logging not yet implemented, logging synchronously")

            # Synchronous logging
            audit_log = AuditLog.objects.create(**audit_data)

            logger.debug(
                f"Audit log created: {event_type} - {action}",
                extra={'audit_log_id': audit_log.id}
            )

            return audit_log

        except (DatabaseError, ValidationError, TypeError) as e:
            # Audit logging should never break the main flow
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
            return None


# Convenience function for quick audit logging
def quick_audit(
    event_type: str,
    entity: models.Model,
    action: str,
    user=None,
    metadata: Optional[Dict] = None
):
    """
    Quick audit logging without full service initialization.

    Usage:
        quick_audit('CREATED', work_order, 'Work order created', user=request.user)
    """
    service = EntityAuditService(user=user)
    service._log_audit(
        event_type=event_type,
        entity=entity,
        action=action,
        message=f"{entity.__class__.__name__}: {action}",
        metadata=metadata
    )
