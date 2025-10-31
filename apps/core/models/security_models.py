"""
Security-related models for the core app.

This module contains models for security monitoring, audit trails, and violation tracking:
- CSPViolation: Content Security Policy violation reports
- SessionForensics: Session lifecycle and security event audit trail

Migration Date: 2025-10-10
Migrated from: apps/core/models.py (lines 42-862)
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# Late import pattern to prevent circular dependencies during app loading
# get_user_model() will be called inside model methods when needed
def get_user_model_safe():
    """Safely get user model with late import."""
    from django.contrib.auth import get_user_model
    return get_user_model()


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
        settings.AUTH_USER_MODEL,
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
