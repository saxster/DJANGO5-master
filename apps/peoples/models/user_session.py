"""
import logging
logger = logging.getLogger(__name__)
User Session Management Model

Tracks user sessions across multiple devices with comprehensive
security monitoring and device fingerprinting.

Compliance:
    - Rule #7: Model < 150 lines
    - GDPR: User can view/revoke own sessions
    - SOC 2: Complete session audit trail
"""

from django.db import models
from django.utils import timezone
from django.contrib.sessions.models import Session
from datetime import timedelta
import hashlib

from apps.ontology.decorators import ontology


@ontology(
    domain="people",
    concept="User Session Management",
    purpose=(
        "Multi-device session management with device fingerprinting and security monitoring. "
        "Enables users to view and remotely revoke sessions across all devices."
    ),
    criticality="critical",
    security_boundary=True,
    models=[{
        "name": "UserSession",
        "purpose": "Tracks all active sessions per user across multiple devices with device fingerprinting",
        "pii_fields": ["user", "ip_address", "last_ip_address", "user_agent", "country", "city", "device_name"],
        "retention": "Revoked sessions: 90 days | Active sessions: Until expiration or revocation",
    }],
    tags=["security", "session-management", "device-fingerprinting", "gdpr", "soc2"],
)
class UserSession(models.Model):
    """
    Enhanced session tracking with device fingerprinting.

    Tracks all active sessions for a user across multiple devices,
    enabling users to view and revoke sessions remotely.
    """

    # User relationship
    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='user_sessions',
        help_text="User who owns this session"
    )

    # Django session reference
    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name='user_session',
        help_text="Django session object"
    )

    # Device information
    device_fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Unique device fingerprint hash"
    )

    device_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="User-friendly device name (e.g., 'iPhone 14', 'Chrome on Windows')"
    )

    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown'),
        ],
        default='unknown',
        help_text="Device type"
    )

    # Browser/OS information
    user_agent = models.TextField(
        help_text="Full user agent string"
    )

    browser = models.CharField(max_length=50, blank=True)
    browser_version = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    os_version = models.CharField(max_length=50, blank=True)

    # Location information
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="IP address at session creation"
    )

    last_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Last known IP address"
    )

    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    # Session lifecycle
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_activity = models.DateTimeField(auto_now=True, db_index=True)
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="When session expires"
    )

    # Security flags
    is_current = models.BooleanField(
        default=False,
        help_text="Whether this is the current session"
    )

    is_suspicious = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged for suspicious activity"
    )

    suspicious_reason = models.TextField(
        blank=True,
        help_text="Reason for suspicious flag"
    )

    # Revocation tracking
    revoked = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether session was manually revoked"
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When session was revoked"
    )

    revoked_by = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revoked_sessions',
        help_text="User or admin who revoked session"
    )

    revoke_reason = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('user_action', 'User Revoked'),
            ('admin_action', 'Admin Revoked'),
            ('suspicious_activity', 'Suspicious Activity'),
            ('device_lost', 'Device Lost/Stolen'),
            ('security_breach', 'Security Breach'),
            ('expired', 'Session Expired'),
        ],
        help_text="Reason for revocation"
    )

    class Meta:
        db_table = 'user_session'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'revoked']),
            models.Index(fields=['device_fingerprint', 'user']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['expires_at']),
        ]
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'

    def __str__(self):
        return f"{self.user.loginid} - {self.device_name} ({self.ip_address})"

    def is_expired(self):
        """Check if session has expired."""
        return timezone.now() > self.expires_at

    def is_active(self):
        """Check if session is still active (not revoked or expired)."""
        return not self.revoked and not self.is_expired()

    def revoke(self, revoked_by=None, reason='user_action'):
        """
        Revoke this session.

        Args:
            revoked_by: User who revoked the session
            reason: Reason for revocation
        """
        self.revoked = True
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.revoke_reason = reason
        self.save()

        # Delete the Django session
        try:
            self.session.delete()
        except Session.DoesNotExist:
            pass

    def get_location_display(self):
        """Get human-readable location string."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.country:
            parts.append(self.country)
        return ', '.join(parts) if parts else 'Unknown'

    def get_device_display(self):
        """Get human-readable device string."""
        if self.device_name:
            return self.device_name

        parts = []
        if self.browser:
            parts.append(f"{self.browser} {self.browser_version}".strip())
        if self.os:
            parts.append(f"on {self.os} {self.os_version}".strip())

        return ' '.join(parts) if parts else 'Unknown Device'

    @staticmethod
    def generate_device_fingerprint(user_agent, ip_address):
        """
        Generate unique device fingerprint from user agent and IP.

        Args:
            user_agent: Browser user agent string
            ip_address: Client IP address

        Returns:
            str: SHA256 hash of device characteristics
        """
        # Combine identifying characteristics
        fingerprint_data = f"{user_agent}:{ip_address}"

        # Generate hash
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
