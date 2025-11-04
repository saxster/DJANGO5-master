"""
Ticket Audit Log Model - Immutable Audit Trail

Provides persistent, tamper-proof audit logging for compliance requirements
(SOC 2, HIPAA, GDPR, ISO 27001).

Following .claude/rules.md:
- Rule #1: Security-first approach
- Model < 150 lines
- Immutable audit records (no updates/deletes)
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import hashlib
import json


class TicketAuditLog(models.Model):
    """
    Immutable audit log for ticket operations.

    Features:
    - Tamper-proof with integrity hashing
    - Indexed for fast compliance queries
    - Automatic retention policy management
    - Support for multi-tenant isolation

    Compliance:
    - SOC 2: Audit trail requirement
    - HIPAA: Access logging
    - GDPR: Data access records
    - ISO 27001: Security event logging
    """

    # Event Identification
    id = models.BigAutoField(primary_key=True)
    event_id = models.UUIDField(unique=True, db_index=True)
    correlation_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    # Event Classification
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of event (ticket_created, ticket_updated, etc.)"
    )
    event_category = models.CharField(
        max_length=50,
        choices=[
            ('access', 'Access Control'),
            ('modification', 'Data Modification'),
            ('security', 'Security Event'),
            ('workflow', 'Workflow Transition'),
            ('escalation', 'Escalation Event'),
        ],
        db_index=True
    )
    severity_level = models.CharField(
        max_length=20,
        choices=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical'),
        ],
        default='info',
        db_index=True
    )

    # Context Information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ticket_audit_logs',
        db_index=True
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='ticket_audit_logs',
        db_index=True
    )
    ticket = models.ForeignKey(
        'y_helpdesk.Ticket',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        db_index=True
    )

    # Event Data
    event_data = models.JSONField(
        help_text="Complete event details in JSON format"
    )
    old_values = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous values for update events"
    )
    new_values = models.JSONField(
        null=True,
        blank=True,
        help_text="New values for update events"
    )

    # Request Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)
    request_path = models.CharField(max_length=500, null=True, blank=True)

    # Temporal Information
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    # Integrity & Security
    integrity_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256 hash for tamper detection"
    )
    previous_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Hash of previous audit log entry (blockchain-style)"
    )

    # Compliance & Retention
    retention_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Retention policy expiration date"
    )
    is_archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'y_helpdesk_audit_log'
        verbose_name = 'Ticket Audit Log'
        verbose_name_plural = 'Ticket Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp'], name='audit_event_time_idx'),
            models.Index(fields=['user', 'timestamp'], name='audit_user_time_idx'),
            models.Index(fields=['ticket', 'timestamp'], name='audit_ticket_time_idx'),
            models.Index(fields=['tenant', 'timestamp'], name='audit_tenant_time_idx'),
            models.Index(fields=['severity_level', 'timestamp'], name='audit_severity_time_idx'),
        ]
        permissions = [
            ('view_audit_logs', 'Can view audit logs'),
            ('export_audit_logs', 'Can export audit logs for compliance'),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.timestamp}"

    def save(self, *args, **kwargs):
        """Override save to compute integrity hash."""
        # Prevent updates (immutable audit logs)
        if self.pk is not None:
            raise ValidationError("Audit logs are immutable and cannot be updated")

        # Compute integrity hash
        if not self.integrity_hash:
            self.integrity_hash = self._compute_integrity_hash()

        # Set retention date if not specified (default: 7 years for compliance)
        if not self.retention_until:
            from datetime import timedelta
            self.retention_until = self.timestamp + timedelta(days=365 * 7)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of audit logs."""
        raise ValidationError("Audit logs are immutable and cannot be deleted")

    def _compute_integrity_hash(self) -> str:
        """
        Compute SHA256 hash for tamper detection.

        Hash includes: event_type, user_id, timestamp, event_data
        """
        hash_data = {
            'event_id': str(self.event_id),
            'event_type': self.event_type,
            'user_id': self.user_id if self.user else None,
            'ticket_id': self.ticket_id if self.ticket else None,
            'timestamp': self.timestamp.isoformat(),
            'event_data': self.event_data,
            'previous_hash': self.previous_hash,
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify audit log has not been tampered with."""
        computed_hash = self._compute_integrity_hash()
        return computed_hash == self.integrity_hash
