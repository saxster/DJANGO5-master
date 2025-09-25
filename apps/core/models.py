from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import ipaddress

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
