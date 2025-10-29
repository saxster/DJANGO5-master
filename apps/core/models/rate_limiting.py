"""
Rate Limiting Models

Persistent storage for rate limiting data including:
- Blocked IPs with automatic expiry
- Trusted IP whitelist
- Violation history for analytics

Complies with Rule #7 - Model Complexity Limits (< 150 lines per model)
"""

from django.db import models
from django.utils import timezone
from django.core.validators import validate_ipv46_address
from datetime import timedelta


class RateLimitBlockedIP(models.Model):
    """
    Automatically blocked IPs due to excessive rate limit violations.

    Used by PathBasedRateLimitMiddleware for persistent IP blocking
    beyond cache-based temporary blocks.
    """
    ip_address = models.GenericIPAddressField(
        unique=True,
        validators=[validate_ipv46_address],
        help_text="Blocked IP address (IPv4 or IPv6)"
    )

    blocked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the IP was blocked"
    )

    blocked_until = models.DateTimeField(
        help_text="When the block expires"
    )

    violation_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of violations that triggered the block"
    )

    endpoint_type = models.CharField(
        max_length=50,
        default='unknown',
        help_text="Type of endpoint that triggered the block (admin, api, etc.)"
    )

    last_violation_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last URL path that triggered a violation"
    )

    reason = models.TextField(
        blank=True,
        help_text="Reason for blocking (auto-generated)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether the block is currently active"
    )

    notes = models.TextField(
        blank=True,
        help_text="Admin notes about this block"
    )

    class Meta:
        db_table = 'core_rate_limit_blocked_ip'
        verbose_name = 'Blocked IP Address'
        verbose_name_plural = 'Blocked IP Addresses'
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['blocked_until']),
            models.Index(fields=['endpoint_type']),
        ]
        ordering = ['-blocked_at']

    def __str__(self):
        return f"{self.ip_address} (until {self.blocked_until.strftime('%Y-%m-%d %H:%M')})"

    def is_expired(self) -> bool:
        """Check if the block has expired."""
        return timezone.now() >= self.blocked_until

    def extend_block(self, hours: int = 24):
        """Extend the block duration."""
        self.blocked_until = timezone.now() + timedelta(hours=hours)
        self.save(update_fields=['blocked_until'])


class RateLimitTrustedIP(models.Model):
    """
    Trusted IPs that bypass rate limiting.

    Used for internal services, monitoring systems, and trusted API consumers.
    """
    ip_address = models.GenericIPAddressField(
        unique=True,
        validators=[validate_ipv46_address],
        help_text="Trusted IP address (IPv4 or IPv6)"
    )

    description = models.CharField(
        max_length=255,
        help_text="Description of the trusted source (e.g., 'Internal monitoring service')"
    )

    added_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the IP was added to the trusted list"
    )

    added_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trusted_ips_added',
        help_text="Admin who added this trusted IP"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether the trust is currently active"
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration date for temporary trust"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this trusted IP"
    )

    class Meta:
        db_table = 'core_rate_limit_trusted_ip'
        verbose_name = 'Trusted IP Address'
        verbose_name_plural = 'Trusted IP Addresses'
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.ip_address} - {self.description}"

    def is_expired(self) -> bool:
        """Check if the trust has expired."""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at


class RateLimitViolationLog(models.Model):
    """
    Historical log of rate limit violations for analytics and monitoring.

    Enables:
    - Trend analysis
    - Attack pattern detection
    - Security incident investigation
    """
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the violation occurred"
    )

    client_ip = models.GenericIPAddressField(
        validators=[validate_ipv46_address],
        help_text="IP address that triggered the violation"
    )

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rate_limit_violations',
        help_text="User if authenticated"
    )

    endpoint_path = models.CharField(
        max_length=255,
        db_index=True,
        help_text="The endpoint path that was accessed"
    )

    endpoint_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of endpoint (admin, api, rest, etc.) - GraphQL removed Oct 2025"
    )

    violation_reason = models.CharField(
        max_length=100,
        help_text="Reason for violation (ip_rate_limit, user_rate_limit, etc.)"
    )

    request_count = models.PositiveIntegerField(
        help_text="Number of requests at the time of violation"
    )

    rate_limit = models.PositiveIntegerField(
        help_text="The rate limit threshold that was exceeded"
    )

    correlation_id = models.CharField(
        max_length=36,
        db_index=True,
        help_text="Correlation ID for request tracking"
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string of the violating request"
    )

    class Meta:
        db_table = 'core_rate_limit_violation_log'
        verbose_name = 'Rate Limit Violation'
        verbose_name_plural = 'Rate Limit Violations'
        indexes = [
            models.Index(fields=['timestamp', 'endpoint_type']),
            models.Index(fields=['client_ip', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.client_ip} - {self.endpoint_path} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"