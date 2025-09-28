from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()



# CSP Violation Model
class CSPViolation(models.Model):
    """
    Store Content Security Policy violation reports for analysis.
    
    This helps identify:
    - Legitimate resources that need to be whitelisted
    - Actual XSS attempts
    - Misconfigured CSP policies
    """
    
    # Violation details from CSP report
    document_uri = models.URLField(max_length=2000, help_text="URI of the document where violation occurred")
    referrer = models.URLField(max_length=2000, blank=True, help_text="Referrer of the document")
    violated_directive = models.CharField(max_length=500, help_text="The directive that was violated")
    effective_directive = models.CharField(max_length=500, help_text="The effective directive after fallback")
    original_policy = models.TextField(help_text="The original CSP policy")
    blocked_uri = models.CharField(max_length=2000, help_text="URI that was blocked")
    source_file = models.URLField(max_length=2000, blank=True, help_text="Source file where violation occurred")
    line_number = models.IntegerField(default=0, help_text="Line number in source file")
    column_number = models.IntegerField(default=0, help_text="Column number in source file")
    status_code = models.IntegerField(default=0, help_text="HTTP status code of the document")
    script_sample = models.TextField(blank=True, help_text="Sample of the violating script")
    
    # Additional metadata
    ip_address = models.GenericIPAddressField(help_text="IP address of the client")
    user_agent = models.TextField(blank=True, help_text="User agent of the client")
    reported_at = models.DateTimeField(default=timezone.now, help_text="When the violation was reported")
    
    # Analysis fields
    severity = models.CharField(
        max_length=20,
        choices=[
            ('CRITICAL', 'Critical - Potential Attack'),
            ('HIGH', 'High - Risky Behavior'),
            ('MEDIUM', 'Medium - Policy Violation'),
            ('LOW', 'Low - Minor Issue'),
        ],
        default='MEDIUM',
        help_text="Severity of the violation"
    )
    
    reviewed = models.BooleanField(default=False, help_text="Whether this violation has been reviewed")
    false_positive = models.BooleanField(default=False, help_text="Whether this is a false positive")
    notes = models.TextField(blank=True, help_text="Admin notes about this violation")
    
    class Meta:
        db_table = 'security_csp_violations'
        ordering = ['-reported_at']
        indexes = [
            models.Index(fields=['reported_at']),
            models.Index(fields=['severity', 'reviewed']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['blocked_uri']),
        ]
        
    def __str__(self):
        return f"{self.violated_directive} - {self.blocked_uri[:50]} - {self.reported_at}"
        
    @classmethod
    def get_violation_summary(cls, days=7):
        """
        Get summary of CSP violations for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            dict: Summary statistics
        """
        from datetime import timedelta
        from django.db.models import Count
        
        since = timezone.now() - timedelta(days=days)
        violations = cls.objects.filter(reported_at__gte=since)
        
        return {
            'total': violations.count(),
            'by_severity': violations.values('severity').annotate(count=Count('id')),
            'by_directive': violations.values('violated_directive').annotate(count=Count('id')),
            'unique_ips': violations.values('ip_address').distinct().count(),
            'unreviewed': violations.filter(reviewed=False).count(),
        }
        
    @classmethod
    def cleanup_old_violations(cls, keep_days=30):
        """
        Clean up old CSP violation records.
        
        Args:
            keep_days: Number of days to keep
            
        Returns:
            int: Number of deleted records
        """
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=keep_days)
        deleted, _ = cls.objects.filter(
            reported_at__lt=cutoff,
            reviewed=True,
            false_positive=True
        ).delete()
        
        return deleted


# API Authentication Models
import hashlib
import secrets
from django.contrib.postgres.fields import ArrayField


class APIKey(models.Model):
    """
    Model for storing API keys with secure hashing.
    """
    
    name = models.CharField(
        max_length=100,
        help_text="Descriptive name for this API key"
    )
    
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash of the API key"
    )
    
    secret = models.CharField(
        max_length=64,
        help_text="Secret for request signing (HMAC)"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_keys',
        null=True,
        blank=True,
        help_text="User associated with this API key"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this API key is active"
    )
    
    require_signing = models.BooleanField(
        default=False,
        help_text="Whether requests must be signed with HMAC"
    )
    
    allowed_ips = ArrayField(
        models.GenericIPAddressField(),
        blank=True,
        null=True,
        help_text="List of allowed IP addresses (null = all allowed)"
    )
    
    permissions = models.JSONField(
        default=dict,
        help_text="Permissions granted to this API key"
    )
    
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this API key expires (null = never)"
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this API key was used"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this API key was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this API key was last updated"
    )
    
    class Meta:
        db_table = 'api_keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_hash']),
            models.Index(fields=['is_active', 'expires_at']),
        ]
        
    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"
        
    @classmethod
    def generate_key(cls):
        """
        Generate a new API key.
        
        Returns:
            tuple: (api_key, key_hash)
        """
        # Generate a secure random API key
        api_key = secrets.token_urlsafe(32)
        
        # Hash the key for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        return api_key, key_hash
        
    @classmethod
    def generate_secret(cls):
        """
        Generate a secret for request signing.
        
        Returns:
            str: Secret string
        """
        return secrets.token_urlsafe(32)
        
    @classmethod
    def create_api_key(cls, name, user=None, **kwargs):
        """
        Create a new API key.
        
        Args:
            name: Name for the API key
            user: Optional user to associate with
            **kwargs: Additional fields
            
        Returns:
            tuple: (api_key_instance, raw_api_key)
        """
        api_key, key_hash = cls.generate_key()
        secret = cls.generate_secret()
        
        instance = cls.objects.create(
            name=name,
            key_hash=key_hash,
            secret=secret,
            user=user,
            **kwargs
        )
        
        # Return both instance and raw key (raw key is only available now)
        return instance, api_key
        
    def update_last_used(self):
        """Update the last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])
        
    def is_expired(self):
        """Check if the API key has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
        
    def has_permission(self, permission):
        """
        Check if this API key has a specific permission.
        
        Args:
            permission: Permission string to check
            
        Returns:
            bool: True if permission is granted
        """
        if not self.permissions:
            return False
            
        # Check for wildcard permission
        if self.permissions.get('*'):
            return True
            
        # Check specific permission
        return self.permissions.get(permission, False)


class APIAccessLog(models.Model):
    """
    Log of API access attempts for audit and analytics.
    """
    
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True,
        related_name='access_logs',
        help_text="API key used for this request"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the request"
    )
    
    method = models.CharField(
        max_length=10,
        help_text="HTTP method used"
    )
    
    path = models.CharField(
        max_length=500,
        help_text="Request path"
    )
    
    query_params = models.TextField(
        blank=True,
        help_text="Query parameters"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    
    response_status = models.IntegerField(
        null=True,
        help_text="HTTP response status code"
    )
    
    response_time = models.IntegerField(
        help_text="Response time in milliseconds"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if request failed"
    )
    
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When the request was made"
    )
    
    class Meta:
        db_table = 'api_access_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['api_key', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['response_status']),
        ]
        
    def __str__(self):
        return f"{self.method} {self.path} - {self.timestamp}"
        
    @classmethod
    def cleanup_old_logs(cls, days=90):
        """
        Clean up old access logs.

        Args:
            days: Number of days to keep

        Returns:
            int: Number of deleted records
        """
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(timestamp__lt=cutoff).delete()

        return deleted


class EncryptionKeyMetadata(models.Model):
    """
    Track encryption key lifecycle for key rotation management.

    This model addresses the CVSS 7.5 vulnerability where no key rotation
    mechanism existed. It enables:
    - Multi-key support for safe rotation
    - Key age tracking and expiration
    - Audit trail of all key operations
    - Rollback capability during rotation failures
    """

    # Key identification
    key_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the encryption key"
    )

    # Key lifecycle status
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this key is currently active for encryption/decryption"
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the key was created"
    )

    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key was activated for use"
    )

    expires_at = models.DateTimeField(
        help_text="When the key should expire and be rotated"
    )

    rotated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key was rotated out"
    )

    # Rotation tracking
    rotation_status = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Created - Not Yet Active'),
            ('active', 'Active - Current Key'),
            ('rotating', 'Rotating - Migration In Progress'),
            ('retired', 'Retired - No Longer Used'),
            ('expired', 'Expired - Past Expiration Date'),
        ],
        default='created',
        db_index=True,
        help_text="Current status of the key in rotation lifecycle"
    )

    replaced_by_key_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Key ID that replaced this key during rotation"
    )

    # Audit trail
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_encryption_keys',
        help_text="User who created this key"
    )

    rotation_notes = models.TextField(
        blank=True,
        help_text="Notes about key rotation process"
    )

    # Metadata
    data_encrypted_count = models.BigIntegerField(
        default=0,
        help_text="Approximate count of records encrypted with this key"
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this key was used for encryption/decryption"
    )

    class Meta:
        db_table = 'encryption_key_metadata'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_id']),
            models.Index(fields=['is_active', 'expires_at']),
            models.Index(fields=['rotation_status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Encryption Key Metadata'
        verbose_name_plural = 'Encryption Key Metadata'

    def __str__(self):
        status_indicator = "✅" if self.is_active else "⏸️"
        return f"{status_indicator} {self.key_id} ({self.rotation_status})"

    def save(self, *args, **kwargs):
        """Override save to update timestamps and audit trail."""
        # Update activated_at when becoming active
        if self.is_active and not self.activated_at:
            self.activated_at = timezone.now()

        # Update rotated_at when status changes to retired
        if self.rotation_status == 'retired' and not self.rotated_at:
            self.rotated_at = timezone.now()

        # Check for expiration
        if timezone.now() > self.expires_at and self.rotation_status not in ['retired', 'expired']:
            self.rotation_status = 'expired'
            self.is_active = False

        super().save(*args, **kwargs)

    @property
    def age_days(self):
        """Calculate key age in days."""
        return (timezone.now() - self.created_at).days

    @property
    def expires_in_days(self):
        """Calculate days until expiration."""
        return (self.expires_at - timezone.now()).days

    @property
    def is_expired(self):
        """Check if key has expired."""
        return timezone.now() > self.expires_at

    @property
    def needs_rotation(self):
        """Check if key needs rotation (within 14 days of expiration)."""
        return self.expires_in_days < 14

    def mark_for_rotation(self, new_key_id: str, notes: str = "") -> None:
        """
        Mark this key for rotation.

        Args:
            new_key_id: ID of the new key that will replace this one
            notes: Notes about the rotation process
        """
        self.rotation_status = 'rotating'
        self.replaced_by_key_id = new_key_id
        if notes:
            self.rotation_notes = f"{self.rotation_notes}\n{timezone.now()}: {notes}"
        self.save()

    def retire(self, notes: str = "") -> None:
        """
        Retire this key after successful rotation.

        Args:
            notes: Notes about retirement
        """
        self.is_active = False
        self.rotation_status = 'retired'
        self.rotated_at = timezone.now()
        if notes:
            self.rotation_notes = f"{self.rotation_notes}\n{timezone.now()}: {notes}"
        self.save()

    @classmethod
    def get_current_key(cls):
        """Get the current active encryption key."""
        return cls.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

    @classmethod
    def get_keys_needing_rotation(cls):
        """Get keys that need rotation (expiring within 14 days)."""
        from datetime import timedelta
        rotation_threshold = timezone.now() + timedelta(days=14)

        return cls.objects.filter(
            is_active=True,
            expires_at__lt=rotation_threshold
        )

    @classmethod
    def cleanup_old_keys(cls, days=365):
        """
        Clean up retired keys older than specified days.

        Args:
            days: Number of days to keep retired keys

        Returns:
            int: Number of deleted records
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(
            rotation_status='retired',
            rotated_at__lt=cutoff
        ).delete()

        return deleted


class SessionForensics(models.Model):
    """
    Session forensics and audit trail model.

    Implements Rule #10: Session Security Standards.
    Provides comprehensive audit trail for session lifecycle and security events.

    Features:
    - Tracks session creation, rotation, and termination
    - Records IP address and geolocation data
    - Monitors privilege changes and security events
    - Enables post-incident analysis
    """

    SESSION_EVENT_TYPES = [
        ('created', 'Session Created'),
        ('authenticated', 'User Authenticated'),
        ('rotated', 'Session Rotated'),
        ('activity_timeout', 'Activity Timeout'),
        ('privilege_change', 'Privilege Change Detected'),
        ('ip_change', 'IP Address Changed'),
        ('user_agent_change', 'User Agent Changed'),
        ('concurrent_limit', 'Concurrent Session Limit'),
        ('manual_logout', 'Manual Logout'),
        ('forced_logout', 'Forced Logout'),
        ('expired', 'Session Expired'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='session_forensics',
        help_text="User associated with this session"
    )

    session_key = models.CharField(
        max_length=40,
        db_index=True,
        help_text="Django session key (hashed for security)"
    )

    event_type = models.CharField(
        max_length=30,
        choices=SESSION_EVENT_TYPES,
        db_index=True,
        help_text="Type of session event"
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the event occurred"
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address at time of event"
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string at time of event"
    )

    geolocation = models.JSONField(
        null=True,
        blank=True,
        help_text="Approximate geolocation data (country, city, etc.)"
    )

    event_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event-specific metadata"
    )

    correlation_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Correlation ID for request tracking"
    )

    severity = models.CharField(
        max_length=20,
        choices=[
            ('info', 'Informational'),
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical Security Event'),
        ],
        default='info',
        help_text="Security severity of the event"
    )

    is_suspicious = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged as suspicious by automated analysis"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes or analysis"
    )

    class Meta:
        db_table = 'session_forensics'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['session_key', 'event_type']),
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['is_suspicious', 'severity']),
            models.Index(fields=['correlation_id']),
        ]
        verbose_name = 'Session Forensic Record'
        verbose_name_plural = 'Session Forensic Records'

    def __str__(self):
        return f"{self.event_type} - {self.user.peoplecode} @ {self.timestamp}"

    @classmethod
    def log_session_event(
        cls,
        user,
        session_key: str,
        event_type: str,
        ip_address: str = None,
        user_agent: str = None,
        correlation_id: str = None,
        metadata: dict = None,
        severity: str = 'info'
    ):
        """
        Create a forensic log entry for a session event.

        Args:
            user: User instance
            session_key: Session key (will be hashed)
            event_type: Type of event
            ip_address: Client IP address
            user_agent: Client user agent
            correlation_id: Request correlation ID
            metadata: Additional event metadata
            severity: Event severity level

        Returns:
            SessionForensics instance
        """
        import hashlib

        hashed_session_key = hashlib.sha256(session_key.encode()).hexdigest()[:40]

        is_suspicious = cls._detect_suspicious_event(
            event_type, metadata or {}
        )

        return cls.objects.create(
            user=user,
            session_key=hashed_session_key,
            event_type=event_type,
            timestamp=timezone.now(),
            ip_address=ip_address,
            user_agent=user_agent[:1000] if user_agent else '',
            event_metadata=metadata or {},
            correlation_id=correlation_id or '',
            severity=severity,
            is_suspicious=is_suspicious
        )

    @staticmethod
    def _detect_suspicious_event(event_type: str, metadata: dict) -> bool:
        """
        Detect if event appears suspicious based on type and metadata.

        Args:
            event_type: Type of event
            metadata: Event metadata

        Returns:
            True if event is suspicious
        """
        suspicious_events = [
            'ip_change',
            'user_agent_change',
            'concurrent_limit',
            'forced_logout'
        ]

        if event_type in suspicious_events:
            return True

        if event_type == 'rotated' and 'privilege_escalation' in metadata.get('reason', ''):
            return True

        return False

    @classmethod
    def get_user_session_history(cls, user_id: int, days: int = 30):
        """
        Get session history for user within specified timeframe.

        Args:
            user_id: User ID
            days: Number of days to look back

        Returns:
            QuerySet of SessionForensics records
        """
        cutoff = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            user_id=user_id,
            timestamp__gte=cutoff
        ).select_related('user')

    @classmethod
    def get_suspicious_activity(cls, hours: int = 24):
        """
        Get suspicious session activity within specified timeframe.

        Args:
            hours: Number of hours to look back

        Returns:
            QuerySet of suspicious SessionForensics records
        """
        cutoff = timezone.now() - timedelta(hours=hours)
        return cls.objects.filter(
            timestamp__gte=cutoff,
            is_suspicious=True
        ).select_related('user').order_by('-severity', '-timestamp')


from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
)

from apps.core.models.cache_analytics import (
    CacheMetrics,
    CacheAnomalyLog,
)

from apps.core.models.health_monitoring import (
    HealthCheckLog,
    ServiceAvailability,
    AlertThreshold,
)

from apps.core.models.api_deprecation import (
    APIDeprecation,
    APIDeprecationUsage,
)
