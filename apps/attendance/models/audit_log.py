"""
Attendance Access Audit Log Model

Comprehensive audit trail for all access to attendance records.
Tracks reads, writes, updates, and deletes for compliance and security.

Compliance:
- SOC 2 Type II: Complete audit trail requirement
- ISO 27001: Access logging and monitoring
- Data Protection: Access transparency

Retention: 6 years (configurable via settings)
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.indexes import BrinIndex
from apps.tenants.models import TenantAwareModel
from typing import Optional
import uuid


class AttendanceAccessLog(TenantAwareModel):
    """
    Audit log for attendance record access.

    Captures comprehensive information about who accessed attendance data,
    when, from where, and what action was performed.

    Fields:
        - Basic: id, uuid, tenant, created_at
        - Who: user, impersonated_by (for admin acting as user)
        - What: attendance_record, action, resource_type
        - When: timestamp (auto), duration_ms
        - Where: ip_address, user_agent, request_path
        - How: http_method, status_code
        - Why: correlation_id (for request tracing)
        - Changes: old_values, new_values (for updates)
    """

    class Action(models.TextChoices):
        """Possible actions on attendance records"""
        VIEW = 'VIEW', 'View Record'
        CREATE = 'CREATE', 'Create Record'
        UPDATE = 'UPDATE', 'Update Record'
        DELETE = 'DELETE', 'Delete Record'
        EXPORT = 'EXPORT', 'Export Records'
        APPROVE = 'APPROVE', 'Approve Record'
        REJECT = 'REJECT', 'Reject Record'
        LOCK = 'LOCK', 'Lock for Payroll'
        UNLOCK = 'UNLOCK', 'Unlock Record'
        FACE_VERIFY = 'FACE_VERIFY', 'Face Recognition Verification'
        GPS_VALIDATE = 'GPS_VALIDATE', 'GPS Location Validation'
        BULK_UPDATE = 'BULK_UPDATE', 'Bulk Update Records'
        BULK_DELETE = 'BULK_DELETE', 'Bulk Delete Records'

    class ResourceType(models.TextChoices):
        """Type of resource being accessed"""
        ATTENDANCE_RECORD = 'ATTENDANCE_RECORD', 'Attendance Record'
        GEOFENCE = 'GEOFENCE', 'Geofence'
        ATTENDANCE_PHOTO = 'ATTENDANCE_PHOTO', 'Attendance Photo'
        BIOMETRIC_TEMPLATE = 'BIOMETRIC_TEMPLATE', 'Biometric Template'
        AUDIT_LOG = 'AUDIT_LOG', 'Audit Log'

    # Primary identification
    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="Unique identifier for this audit log entry"
    )

    # Who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_access_logs',
        help_text="User who performed the action"
    )

    impersonated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='impersonated_attendance_access_logs',
        help_text="Admin user who impersonated another user (if applicable)"
    )

    # What was accessed
    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_logs',
        help_text="Attendance record that was accessed"
    )

    resource_type = models.CharField(
        max_length=50,
        choices=ResourceType.choices,
        default=ResourceType.ATTENDANCE_RECORD,
        help_text="Type of resource accessed"
    )

    resource_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of the resource accessed (for non-attendance resources)"
    )

    action = models.CharField(
        max_length=50,
        choices=Action.choices,
        help_text="Action performed on the resource"
    )

    # When it happened
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the action was performed"
    )

    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of the operation in milliseconds"
    )

    # Where it came from
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the client"
    )

    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User agent string from the request"
    )

    request_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Request path (e.g., /api/v1/attendance/123/)"
    )

    # How it was done
    http_method = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="HTTP method (GET, POST, PUT, PATCH, DELETE)"
    )

    status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code of the response"
    )

    # Request tracing
    correlation_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Correlation ID for distributed tracing"
    )

    # Change tracking (for UPDATE actions)
    old_values = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous values before update (for audit trail)"
    )

    new_values = models.JSONField(
        null=True,
        blank=True,
        help_text="New values after update"
    )

    # Additional context
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Additional notes or context for this audit entry"
    )

    # Security flags
    is_suspicious = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag for suspicious access patterns"
    )

    risk_score = models.IntegerField(
        default=0,
        help_text="Automated risk score (0-100) for this access"
    )

    class Meta:
        db_table = 'attendance_access_log'
        verbose_name = 'Attendance Access Log'
        verbose_name_plural = 'Attendance Access Logs'
        ordering = ['-timestamp']

        indexes = [
            # Primary query patterns
            models.Index(fields=['tenant', 'timestamp'], name='aal_tenant_time_idx'),
            models.Index(fields=['tenant', 'user', 'timestamp'], name='aal_tenant_user_time_idx'),
            models.Index(fields=['tenant', 'attendance_record'], name='aal_tenant_record_idx'),
            models.Index(fields=['tenant', 'action'], name='aal_tenant_action_idx'),
            models.Index(fields=['correlation_id'], name='aal_correlation_idx'),
            models.Index(fields=['is_suspicious'], name='aal_suspicious_idx'),

            # BRIN index for timestamp (efficient for time-series data)
            BrinIndex(fields=['timestamp'], name='aal_timestamp_brin_idx'),
        ]

        # Permissions for accessing audit logs
        permissions = [
            ('view_audit_log', 'Can view attendance audit logs'),
            ('export_audit_log', 'Can export attendance audit logs'),
            ('investigate_suspicious', 'Can investigate suspicious access'),
        ]

    def __str__(self):
        return f"{self.action} on {self.resource_type} by {self.user} at {self.timestamp}"

    def save(self, *args, **kwargs):
        """Override save to auto-populate tenant from user"""
        if self.user and not self.tenant_id:
            # Try to get tenant from user
            if hasattr(self.user, 'client_id'):
                self.tenant_id = self.user.client_id
        super().save(*args, **kwargs)

    @property
    def is_failed_access(self) -> bool:
        """Check if this was a failed access attempt"""
        return self.status_code and self.status_code >= 400

    @property
    def is_unauthorized(self) -> bool:
        """Check if this was an unauthorized access attempt"""
        return self.status_code in [401, 403]

    @property
    def is_slow_operation(self) -> bool:
        """Check if this operation was slow (>1000ms)"""
        return self.duration_ms and self.duration_ms > 1000

    @classmethod
    def log_access(cls, user, action: str, attendance_record=None,
                   request=None, duration_ms: Optional[int] = None,
                   old_values: Optional[dict] = None,
                   new_values: Optional[dict] = None,
                   **kwargs) -> 'AttendanceAccessLog':
        """
        Convenience method to create an audit log entry.

        Args:
            user: User performing the action
            action: Action being performed (from Action choices)
            attendance_record: Attendance record being accessed (optional)
            request: Django request object (optional)
            duration_ms: Duration of operation in milliseconds
            old_values: Previous values (for updates)
            new_values: New values (for updates)
            **kwargs: Additional fields

        Returns:
            Created AttendanceAccessLog instance
        """
        log_data = {
            'user': user,
            'action': action,
            'attendance_record': attendance_record,
            'duration_ms': duration_ms,
            'old_values': old_values,
            'new_values': new_values,
        }

        # Extract data from request if provided
        if request:
            log_data.update({
                'ip_address': cls._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                'request_path': request.path,
                'http_method': request.method,
                'correlation_id': getattr(request, 'correlation_id', None),
            })

        # Merge any additional kwargs
        log_data.update(kwargs)

        # Create and save
        return cls.objects.create(**log_data)

    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        """Extract client IP address from request"""
        # Check for IP in forwarded headers (if behind proxy)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get first IP in the chain
            return x_forwarded_for.split(',')[0].strip()

        # Check CloudFlare header
        cf_connecting_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_connecting_ip:
            return cf_connecting_ip

        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR')


class AuditLogRetentionPolicy(models.Model):
    """
    Configuration for audit log retention policies.

    Allows different retention periods for different types of access logs.
    """

    resource_type = models.CharField(
        max_length=50,
        choices=AttendanceAccessLog.ResourceType.choices,
        unique=True,
        help_text="Type of resource this policy applies to"
    )

    retention_days = models.IntegerField(
        default=2190,  # 6 years
        help_text="Number of days to retain audit logs"
    )

    archive_after_days = models.IntegerField(
        default=730,  # 2 years
        help_text="Number of days before archiving logs"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is currently active"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'audit_log_retention_policy'
        verbose_name = 'Audit Log Retention Policy'
        verbose_name_plural = 'Audit Log Retention Policies'

    def __str__(self):
        return f"{self.resource_type}: {self.retention_days} days"
