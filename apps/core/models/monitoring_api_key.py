"""
Monitoring API Key Model

Dedicated model for managing API keys used by external monitoring systems
(Prometheus, Grafana, Datadog, New Relic, etc.).

Features:
- Granular permission control for monitoring endpoints
- IP whitelisting for enhanced security
- Automatic key rotation support
- Usage tracking and audit logging
- Integration with require_monitoring_api_key decorator

Compliance: Rule #3 Alternative Protection - API key authentication for monitoring
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Optional, List

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django.conf import settings



class MonitoringPermission(models.TextChoices):
    """Granular permissions for monitoring API keys."""
    HEALTH_CHECK = 'health', 'Health Check Access'
    METRICS = 'metrics', 'Metrics Access'
    PERFORMANCE = 'performance', 'Performance Data Access'
    ALERTS = 'alerts', 'Alerts Access'
    DASHBOARD = 'dashboard', 'Dashboard Data Access'
    ADMIN = 'admin', 'Full Monitoring Admin Access'


class MonitoringAPIKey(models.Model):
    """
    API keys for external monitoring systems.

    This model provides dedicated authentication for monitoring endpoints
    as an alternative to CSRF protection (Rule #3 compliant).

    Security Features:
    - SHA-256 hashed keys (never store plaintext)
    - Automatic expiration support
    - IP whitelisting
    - Granular permission control
    - Usage tracking and audit trail
    - Rotation support with grace periods
    """

    name = models.CharField(
        max_length=100,
        help_text="Descriptive name (e.g., 'Prometheus Production', 'Grafana Dashboard')"
    )

    description = models.TextField(
        blank=True,
        help_text="Purpose and usage notes for this API key"
    )

    key_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash of the API key"
    )

    monitoring_system = models.CharField(
        max_length=50,
        choices=[
            ('prometheus', 'Prometheus'),
            ('grafana', 'Grafana'),
            ('datadog', 'Datadog'),
            ('new_relic', 'New Relic'),
            ('cloudwatch', 'AWS CloudWatch'),
            ('stackdriver', 'Google Cloud Monitoring'),
            ('custom', 'Custom Monitoring System'),
        ],
        default='custom',
        help_text="Type of monitoring system using this key"
    )

    permissions = ArrayField(
        models.CharField(max_length=50, choices=MonitoringPermission.choices),
        default=list,
        help_text="List of monitoring permissions granted to this key"
    )

    allowed_ips = ArrayField(
        models.GenericIPAddressField(),
        blank=True,
        null=True,
        help_text="Whitelisted IP addresses (null = all IPs allowed)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this API key is currently active"
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_monitoring_keys',
        help_text="User who created this API key"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this API key was created"
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this API key expires (null = never expires)"
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this API key was used"
    )

    usage_count = models.IntegerField(
        default=0,
        help_text="Total number of times this key has been used"
    )

    rotation_schedule = models.CharField(
        max_length=20,
        choices=[
            ('never', 'Never Rotate'),
            ('monthly', 'Monthly Rotation'),
            ('quarterly', 'Quarterly Rotation'),
            ('yearly', 'Yearly Rotation'),
        ],
        default='quarterly',
        help_text="Automatic rotation schedule"
    )

    next_rotation_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key should be rotated next"
    )

    rotation_grace_period_hours = models.IntegerField(
        default=168,
        help_text="Hours to keep old key valid after rotation (default: 1 week)"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (contact info, escalation procedures, etc.)"
    )

    class Meta:
        db_table = 'monitoring_api_keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_hash']),
            models.Index(fields=['is_active', 'expires_at']),
            models.Index(fields=['next_rotation_at']),
            models.Index(fields=['monitoring_system']),
        ]
        verbose_name = 'Monitoring API Key'
        verbose_name_plural = 'Monitoring API Keys'

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f"{self.name} ({self.monitoring_system}) - {status}"

    @classmethod
    def generate_key(cls) -> tuple:
        """
        Generate a new monitoring API key.

        Returns:
            tuple: (api_key, key_hash)
        """
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key, key_hash

    @classmethod
    def create_key(cls, name: str, monitoring_system: str, permissions: List[str],
                   allowed_ips: Optional[List[str]] = None,
                   expires_days: Optional[int] = None,
                   created_by: Optional[User] = None,
                   **kwargs) -> tuple:
        """
        Create a new monitoring API key.

        Args:
            name: Descriptive name for the key
            monitoring_system: Type of monitoring system
            permissions: List of permission strings
            allowed_ips: List of allowed IP addresses (None = all)
            expires_days: Days until expiration (None = never)
            created_by: User creating the key
            **kwargs: Additional fields

        Returns:
            tuple: (MonitoringAPIKey instance, raw_api_key)
        """
        api_key, key_hash = cls.generate_key()

        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timedelta(days=expires_days)

        next_rotation_at = None
        rotation_schedule = kwargs.get('rotation_schedule', 'quarterly')
        if rotation_schedule != 'never':
            rotation_days = {
                'monthly': 30,
                'quarterly': 90,
                'yearly': 365,
            }.get(rotation_schedule, 90)
            next_rotation_at = timezone.now() + timedelta(days=rotation_days)

        instance = cls.objects.create(
            name=name,
            key_hash=key_hash,
            monitoring_system=monitoring_system,
            permissions=permissions,
            allowed_ips=allowed_ips,
            expires_at=expires_at,
            next_rotation_at=next_rotation_at,
            created_by=created_by,
            **kwargs
        )

        return instance, api_key

    def rotate_key(self, created_by: Optional[User] = None) -> tuple:
        """
        Rotate this API key while maintaining grace period overlap.

        The old key remains valid for rotation_grace_period_hours to allow
        zero-downtime updates to monitoring systems.

        Args:
            created_by: User initiating the rotation

        Returns:
            tuple: (new_MonitoringAPIKey instance, raw_api_key)
        """
        new_key, new_hash = self.generate_key()

        new_instance = MonitoringAPIKey.objects.create(
            name=f"{self.name} (Rotated)",
            description=f"Rotated from {self.name} on {timezone.now().isoformat()}",
            key_hash=new_hash,
            monitoring_system=self.monitoring_system,
            permissions=self.permissions,
            allowed_ips=self.allowed_ips,
            rotation_schedule=self.rotation_schedule,
            rotation_grace_period_hours=self.rotation_grace_period_hours,
            metadata=self.metadata,
            created_by=created_by,
            expires_at=self.expires_at
        )

        grace_period_end = timezone.now() + timedelta(hours=self.rotation_grace_period_hours)
        self.expires_at = grace_period_end
        self.metadata['rotated_to'] = new_instance.id
        self.metadata['rotation_date'] = timezone.now().isoformat()
        self.save(update_fields=['expires_at', 'metadata'])

        return new_instance, new_key

    def has_permission(self, permission: str) -> bool:
        """
        Check if this API key has a specific permission.

        Args:
            permission: Permission to check

        Returns:
            True if key has the permission or admin access
        """
        if MonitoringPermission.ADMIN.value in self.permissions:
            return True
        return permission in self.permissions

    def record_usage(self):
        """Record usage of this API key."""
        self.last_used_at = timezone.now()
        self.usage_count += 1
        self.save(update_fields=['last_used_at', 'usage_count'])

    def is_expired(self) -> bool:
        """Check if this API key has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    def needs_rotation(self) -> bool:
        """Check if this API key needs rotation."""
        if not self.next_rotation_at:
            return False
        return timezone.now() >= self.next_rotation_at

    @classmethod
    def cleanup_expired_keys(cls, grace_period_hours: int = 24) -> int:
        """
        Clean up expired monitoring API keys.

        Keys are only deleted if they've been expired for longer than
        the grace period to allow for audit trail retention.

        Args:
            grace_period_hours: Hours after expiration before deletion

        Returns:
            Number of deleted keys
        """
        cutoff = timezone.now() - timedelta(hours=grace_period_hours)
        deleted, _ = cls.objects.filter(
            expires_at__lt=cutoff,
            is_active=False
        ).delete()
        return deleted

    @classmethod
    def get_keys_needing_rotation(cls) -> models.QuerySet:
        """
        Get monitoring API keys that need rotation.

        Returns:
            QuerySet of keys needing rotation
        """
        return cls.objects.filter(
            is_active=True,
            next_rotation_at__lte=timezone.now()
        )


class MonitoringAPIAccessLog(models.Model):
    """
    Audit log for monitoring API key usage.

    Tracks all accesses to monitoring endpoints for security analysis
    and usage monitoring.
    """

    api_key = models.ForeignKey(
        MonitoringAPIKey,
        on_delete=models.CASCADE,
        related_name='access_logs',
        help_text="The monitoring API key used"
    )

    endpoint = models.CharField(
        max_length=200,
        help_text="Endpoint accessed"
    )

    method = models.CharField(
        max_length=10,
        help_text="HTTP method used"
    )

    ip_address = models.GenericIPAddressField(
        help_text="IP address of the request"
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )

    response_status = models.IntegerField(
        help_text="HTTP response status code"
    )

    response_time_ms = models.IntegerField(
        help_text="Response time in milliseconds"
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the access occurred"
    )

    correlation_id = models.CharField(
        max_length=36,
        blank=True,
        help_text="Request correlation ID for tracing"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional request metadata"
    )

    class Meta:
        db_table = 'monitoring_api_access_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['api_key', 'timestamp']),
            models.Index(fields=['endpoint', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['response_status']),
        ]
        verbose_name = 'Monitoring API Access Log'
        verbose_name_plural = 'Monitoring API Access Logs'

    def __str__(self):
        return f"{self.api_key.name} - {self.endpoint} - {self.timestamp}"

    @classmethod
    def cleanup_old_logs(cls, keep_days: int = 90) -> int:
        """
        Clean up old access logs.

        Args:
            keep_days: Number of days to retain logs

        Returns:
            Number of deleted log entries
        """
        cutoff = timezone.now() - timedelta(days=keep_days)
        deleted, _ = cls.objects.filter(timestamp__lt=cutoff).delete()
        return deleted

    @classmethod
    def get_usage_summary(cls, api_key: MonitoringAPIKey, days: int = 7) -> dict:
        """
        Get usage summary for an API key.

        Args:
            api_key: MonitoringAPIKey instance
            days: Number of days to analyze

        Returns:
            Dictionary with usage statistics
        """
        from django.db.models import Count, Avg

        since = timezone.now() - timedelta(days=days)
        logs = cls.objects.filter(api_key=api_key, timestamp__gte=since)

        return {
            'total_requests': logs.count(),
            'unique_ips': logs.values('ip_address').distinct().count(),
            'by_endpoint': logs.values('endpoint').annotate(count=Count('id')),
            'by_status': logs.values('response_status').annotate(count=Count('id')),
            'avg_response_time': logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
            'error_count': logs.filter(response_status__gte=400).count(),
            'period_days': days,
        }