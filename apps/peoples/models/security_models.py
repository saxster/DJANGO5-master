"""
Security Audit Models

Models for tracking authentication events, lockouts, and security incidents.

Compliance:
    - Rule #7: Model < 150 lines
    - Comprehensive audit trail for security events
"""

from django.db import models
from django.utils import timezone


class LoginAttemptLog(models.Model):
    """
    Log of all login attempts for security auditing.

    Tracks both successful and failed login attempts with full context
    for security analysis and incident response.
    """

    # Authentication details
    username = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Username attempted"
    )

    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="Client IP address"
    )

    # Attempt details
    success = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether login was successful"
    )

    failure_reason = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('invalid_credentials', 'Invalid Credentials'),
            ('user_not_found', 'User Not Found'),
            ('account_locked', 'Account Locked'),
            ('ip_throttled', 'IP Address Throttled'),
            ('username_throttled', 'Username Throttled'),
            ('authentication_exception', 'Authentication Exception'),
            ('access_denied', 'Access Denied'),
        ],
        help_text="Reason for failure"
    )

    # Context
    user_agent = models.TextField(
        blank=True,
        help_text="Browser user agent string"
    )

    access_type = models.CharField(
        max_length=20,
        default='Web',
        choices=[
            ('Web', 'Web'),
            ('Mobile', 'Mobile'),
            ('API', 'API'),
        ],
        help_text="Access method"
    )

    # Metadata
    correlation_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Correlation ID for tracing"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'login_attempt_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['username', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['success', 'created_at']),
        ]
        verbose_name = 'Login Attempt Log'
        verbose_name_plural = 'Login Attempt Logs'

    def __str__(self):
        status = 'SUCCESS' if self.success else 'FAILED'
        return f"{self.username} from {self.ip_address} - {status}"


class AccountLockout(models.Model):
    """
    Active account lockouts for security.

    Tracks accounts that are currently locked due to failed login attempts.
    """

    username = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Locked username"
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address that triggered lockout (if applicable)"
    )

    lockout_type = models.CharField(
        max_length=20,
        choices=[
            ('ip', 'IP Address Lockout'),
            ('username', 'Username Lockout'),
            ('manual', 'Manual Lockout'),
        ],
        help_text="Type of lockout"
    )

    reason = models.TextField(
        help_text="Reason for lockout"
    )

    locked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    locked_until = models.DateTimeField(
        db_index=True,
        help_text="When lockout expires"
    )

    attempt_count = models.IntegerField(
        default=0,
        help_text="Number of failed attempts that triggered lockout"
    )

    # Resolution
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether lockout is still active"
    )

    unlocked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When lockout was manually removed"
    )

    unlocked_by = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='unlocked_accounts',
        help_text="Admin who manually unlocked"
    )

    class Meta:
        db_table = 'account_lockout'
        ordering = ['-locked_at']
        indexes = [
            models.Index(fields=['username', 'is_active']),
            models.Index(fields=['lockout_type', 'is_active']),
            models.Index(fields=['locked_until']),
        ]
        verbose_name = 'Account Lockout'
        verbose_name_plural = 'Account Lockouts'

    def __str__(self):
        return f"{self.username} locked until {self.locked_until}"

    def is_expired(self):
        """Check if lockout has expired."""
        return timezone.now() > self.locked_until

    def unlock(self, unlocked_by=None):
        """Manually unlock account."""
        self.is_active = False
        self.unlocked_at = timezone.now()
        self.unlocked_by = unlocked_by
        self.save()
