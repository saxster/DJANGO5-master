"""
Security Audit Models

Models for tracking authentication events, lockouts, and security incidents.

Compliance:
    - Rule #7: Model < 150 lines
    - Comprehensive audit trail for security events
"""

from django.db import models
from django.utils import timezone

from apps.ontology.decorators import ontology


@ontology(
    domain="people",
    concept="Security Audit & Authentication Tracking",
    purpose=(
        "Security audit models for tracking authentication events, login attempts, "
        "account lockouts, and security incidents. Provides comprehensive audit trail "
        "for security analysis, incident response, and compliance reporting (SOC2, GDPR)."
    ),
    criticality="critical",
    security_boundary=True,
    models=[
        {
            "name": "LoginAttemptLog",
            "purpose": "Tracks all login attempts (success + failure) with full context for security auditing",
            "pii_fields": ["username", "ip_address", "user_agent"],
            "retention": "90 days (configurable for compliance)",
        },
        {
            "name": "AccountLockout",
            "purpose": "Active account lockouts due to failed login attempts or manual admin action",
            "pii_fields": ["username", "ip_address"],
            "business_logic": ["is_expired() - Check if lockout has expired", "unlock() - Manually unlock account"],
        },
    ],
    inputs=[
        {
            "name": "LoginAttemptLog.username",
            "type": "str",
            "description": "Username attempted (not encrypted, needed for security analysis)",
            "required": True,
            "sensitive": True,
            "max_length": 255,
        },
        {
            "name": "LoginAttemptLog.ip_address",
            "type": "IPv4/IPv6",
            "description": "Client IP address for geolocation and rate limiting",
            "required": True,
            "sensitive": True,
        },
        {
            "name": "LoginAttemptLog.success",
            "type": "bool",
            "description": "Whether login was successful",
            "required": True,
        },
        {
            "name": "LoginAttemptLog.failure_reason",
            "type": "str (choices)",
            "description": "Reason for failure (invalid_credentials, user_not_found, account_locked, ip_throttled, username_throttled, etc.)",
            "required": False,
        },
        {
            "name": "LoginAttemptLog.correlation_id",
            "type": "str",
            "description": "Correlation ID for distributed tracing across services",
            "required": False,
            "max_length": 64,
        },
        {
            "name": "AccountLockout.username",
            "type": "str",
            "description": "Locked username (unique constraint)",
            "required": True,
            "sensitive": True,
            "max_length": 255,
        },
        {
            "name": "AccountLockout.lockout_type",
            "type": "str (choices)",
            "description": "Type of lockout: ip, username, manual",
            "required": True,
        },
        {
            "name": "AccountLockout.locked_until",
            "type": "datetime",
            "description": "When lockout expires (UTC)",
            "required": True,
        },
    ],
    outputs=[
        {
            "name": "LoginAttemptLog queryset",
            "type": "QuerySet",
            "description": "Security audit trail with username, IP, success, failure_reason, created_at",
        },
        {
            "name": "AccountLockout.is_expired()",
            "type": "bool",
            "description": "Returns True if lockout has expired (timezone.now() > locked_until)",
        },
    ],
    side_effects=[
        "Creates LoginAttemptLog record on every authentication attempt (success or failure)",
        "Creates AccountLockout record when threshold exceeded (e.g., 5 failed attempts)",
        "Updates AccountLockout.is_active = False when manually unlocked",
        "Database writes indexed by: username+created_at, ip_address+created_at, success+created_at",
        "Logs are retained for 90 days (configurable) for compliance",
    ],
    depends_on=[
        "apps.peoples.models.user_model.People (ForeignKey for unlocked_by)",
        "apps.peoples.services.login_throttling_service (creates lockouts)",
        "apps.peoples.services.authentication_service (creates login attempt logs)",
    ],
    used_by=[
        "apps.peoples.services.login_throttling_service.LoginThrottlingService (queries for rate limiting)",
        "apps.peoples.services.authentication_service.AuthenticationService (creates audit logs)",
        "Security incident response (manual queries for forensics)",
        "Compliance reporting (SOC2, GDPR audit trails)",
        "Django Admin (security team review of suspicious activity)",
    ],
    tags=[
        "security",
        "authentication",
        "audit-trail",
        "compliance",
        "soc2",
        "gdpr",
        "rate-limiting",
        "account-lockout",
        "forensics",
        "pii",
    ],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. PII Data Storage:\n"
        "   - username: Stored plaintext (needed for security analysis)\n"
        "   - ip_address: Stored plaintext (needed for geolocation/rate limiting)\n"
        "   - user_agent: Stored plaintext (needed for device fingerprinting)\n"
        "   - GDPR: Data subject access requests must include these logs\n\n"
        "2. Retention Policy:\n"
        "   - Default: 90 days retention for security analysis\n"
        "   - Compliance: Configurable per jurisdiction (GDPR: max 90 days, SOC2: min 90 days)\n"
        "   - Cleanup: Automated task deletes old records beyond retention period\n\n"
        "3. Rate Limiting Integration:\n"
        "   - LoginThrottlingService queries this table for failed attempt counts\n"
        "   - Indexed queries by username+created_at and ip_address+created_at\n"
        "   - Performance: Uses database indexes to prevent full table scans\n\n"
        "4. Account Lockout Security:\n"
        "   - Lockout threshold: Configurable (default: 5 failed attempts in 5 minutes)\n"
        "   - Lockout duration: Exponential backoff (5min, 15min, 1hour, 24hours)\n"
        "   - Manual unlock: Requires admin privileges (logged via unlocked_by ForeignKey)\n\n"
        "5. Access Controls:\n"
        "   - Read: Security admins only (Django Admin permission: view_loginattemptlog)\n"
        "   - Write: System only (no manual creation via admin)\n"
        "   - Delete: Automated cleanup task only (admins cannot delete)\n\n"
        "6. Correlation ID:\n"
        "   - Distributed tracing across authentication services\n"
        "   - Links: API requests → authentication attempt → session creation → audit log\n\n"
        "7. NEVER:\n"
        "   - Store passwords or password hashes in these logs\n"
        "   - Expose these logs via public API (admin-only)\n"
        "   - Allow bulk deletion (preserves audit trail integrity)"
    ),
    performance_notes=(
        "Database Indexes:\n"
        "- Composite: username+created_at (rate limiting queries)\n"
        "- Composite: ip_address+created_at (IP-based rate limiting)\n"
        "- Composite: success+created_at (failed attempt analysis)\n"
        "- Single: locked_until (AccountLockout expiry checks)\n\n"
        "Query Patterns:\n"
        "- High write volume: ~100-500 writes/minute during peak hours\n"
        "- Read volume: Low (admin forensics only)\n"
        "- Retention cleanup: Daily batch job (deletes >90 day old records)\n\n"
        "Performance Considerations:\n"
        "- Use select_related('unlocked_by') for AccountLockout queries to prevent N+1\n"
        "- LoginAttemptLog table grows quickly (partition by month if >10M records)\n"
        "- Rate limiting queries: Add WHERE created_at > NOW() - INTERVAL '5 minutes' for performance"
    ),
    examples=[
        "# Query failed login attempts for username\n"
        "LoginAttemptLog.objects.filter(\n"
        "    username='john.doe',\n"
        "    success=False,\n"
        "    created_at__gte=timezone.now() - timedelta(minutes=5)\n"
        ").count()  # Returns count for rate limiting\n",
        "# Check if account is locked\n"
        "lockout = AccountLockout.objects.filter(\n"
        "    username='john.doe',\n"
        "    is_active=True\n"
        ").first()\n"
        "if lockout and not lockout.is_expired():\n"
        "    raise AccountLockedError(f'Account locked until {lockout.locked_until}')\n",
        "# Manually unlock account\n"
        "lockout = AccountLockout.objects.get(username='john.doe', is_active=True)\n"
        "lockout.unlock(unlocked_by=admin_user)\n"
        "# Logs unlocked_by and unlocked_at for audit trail\n",
    ],
)


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
