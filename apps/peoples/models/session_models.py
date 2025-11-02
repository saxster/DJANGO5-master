"""
User Session Management Models

Models for tracking user sessions across multiple devices with comprehensive
security monitoring and device fingerprinting.

Features:
    - Multi-device session tracking
    - Device fingerprinting for security
    - Automatic session expiration
    - Suspicious activity detection
    - Admin oversight capability

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
import json

from apps.ontology.decorators import ontology


@ontology(
    domain="people",
    concept="Session Management & Device Tracking",
    purpose=(
        "Enhanced multi-device session management with device fingerprinting, security monitoring, "
        "and anomaly detection. Enables users to view and remotely revoke sessions across all devices. "
        "Provides comprehensive audit trail for security analysis and compliance (SOC2, GDPR Article 15)."
    ),
    criticality="critical",
    security_boundary=True,
    models=[
        {
            "name": "UserSession",
            "purpose": "Tracks all active sessions per user across multiple devices with device fingerprinting",
            "pii_fields": ["user", "ip_address", "last_ip_address", "user_agent", "country", "city", "device_name"],
            "retention": "Revoked sessions: 90 days | Active sessions: Until expiration or revocation",
            "business_logic": [
                "is_expired() - Check if session has expired (timezone.now() > expires_at)",
                "is_active() - Check if session is active (not revoked and not expired)",
                "revoke() - Revoke session and delete Django session object",
                "generate_device_fingerprint() - SHA256 hash of user_agent + ip_address",
                "get_location_display() - Human-readable location string",
                "get_device_display() - Human-readable device string",
            ],
        },
        {
            "name": "SessionActivityLog",
            "purpose": "Logs significant session events for security monitoring and anomaly detection",
            "pii_fields": ["ip_address", "url"],
            "retention": "90 days (configurable)",
            "activity_types": [
                "login", "logout", "api_call", "page_view", "data_access",
                "permission_escalation", "suspicious_action", "ip_change"
            ],
        },
    ],
    inputs=[
        {
            "name": "UserSession.user",
            "type": "ForeignKey(People)",
            "description": "User who owns the session",
            "required": True,
            "sensitive": True,
        },
        {
            "name": "UserSession.session",
            "type": "OneToOneField(Session)",
            "description": "Django session object reference",
            "required": True,
        },
        {
            "name": "UserSession.device_fingerprint",
            "type": "str (64 chars, SHA256 hash)",
            "description": "Unique device fingerprint: SHA256(user_agent + ip_address)",
            "required": True,
            "sensitive": False,
        },
        {
            "name": "UserSession.ip_address",
            "type": "IPv4/IPv6",
            "description": "IP address at session creation (for geolocation and security)",
            "required": True,
            "sensitive": True,
        },
        {
            "name": "UserSession.last_ip_address",
            "type": "IPv4/IPv6",
            "description": "Last known IP address (detects IP changes for anomaly detection)",
            "required": False,
            "sensitive": True,
        },
        {
            "name": "UserSession.user_agent",
            "type": "text",
            "description": "Full browser user agent string (for device fingerprinting)",
            "required": True,
            "sensitive": True,
        },
        {
            "name": "UserSession.expires_at",
            "type": "datetime",
            "description": "When session expires (default: created_at + 30 days)",
            "required": True,
        },
        {
            "name": "UserSession.is_suspicious",
            "type": "bool",
            "description": "Flagged for suspicious activity (IP change, unusual access patterns, etc.)",
            "required": False,
            "default": False,
        },
        {
            "name": "SessionActivityLog.activity_type",
            "type": "str (choices)",
            "description": "Type of activity: login, logout, api_call, page_view, data_access, permission_escalation, suspicious_action, ip_change",
            "required": True,
        },
        {
            "name": "SessionActivityLog.metadata",
            "type": "JSONField",
            "description": "Additional activity metadata (request method, response status, data accessed, etc.)",
            "required": False,
        },
    ],
    outputs=[
        {
            "name": "UserSession.is_expired()",
            "type": "bool",
            "description": "Returns True if timezone.now() > expires_at",
        },
        {
            "name": "UserSession.is_active()",
            "type": "bool",
            "description": "Returns True if session is not revoked and not expired",
        },
        {
            "name": "UserSession.generate_device_fingerprint(user_agent, ip_address)",
            "type": "str",
            "description": "Returns SHA256 hash of user_agent:ip_address for device identification",
        },
        {
            "name": "UserSession queryset",
            "type": "QuerySet",
            "description": "Active sessions per user with device information, location, security flags",
        },
    ],
    side_effects=[
        "Creates UserSession record on user login (linked to Django Session)",
        "Creates SessionActivityLog records for significant events (login, logout, suspicious activity)",
        "Updates UserSession.last_activity on every request (via middleware)",
        "Updates UserSession.last_ip_address when IP changes (triggers ip_change activity log)",
        "Deletes Django Session when UserSession.revoke() is called",
        "Sets is_suspicious flag when anomalies detected (IP change, unusual patterns)",
        "Database writes indexed by: user+revoked, device_fingerprint+user, is_suspicious, expires_at",
    ],
    depends_on=[
        "apps.peoples.models.user_model.People (ForeignKey for user and revoked_by)",
        "django.contrib.sessions.models.Session (OneToOneField)",
        "apps.peoples.services.session_management_service (creates/manages sessions)",
        "apps.core.middleware.session_activity (logs session activities)",
        "hashlib (SHA256 for device fingerprinting)",
    ],
    used_by=[
        "apps.peoples.services.session_management_service.SessionManagementService (CRUD operations)",
        "apps.core.middleware.session_activity.SessionActivityMiddleware (activity logging)",
        "User session management UI (view/revoke sessions)",
        "Security monitoring dashboard (suspicious activity alerts)",
        "Admin panel (session oversight, revocation)",
        "GDPR compliance (Article 15: right to access session data)",
    ],
    tags=[
        "security",
        "session-management",
        "device-fingerprinting",
        "multi-device",
        "anomaly-detection",
        "gdpr",
        "soc2",
        "audit-trail",
        "pii",
        "geolocation",
        "suspicious-activity",
    ],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. Device Fingerprinting:\n"
        "   - SHA256 hash of user_agent + ip_address (not reversible)\n"
        "   - Used for device identification across sessions\n"
        "   - WARNING: IP changes trigger new fingerprint (use last_ip_address for continuity)\n"
        "   - Not suitable for authentication (only for tracking/anomaly detection)\n\n"
        "2. PII Data Storage:\n"
        "   - user_agent: Full browser string (contains device/OS info)\n"
        "   - ip_address, last_ip_address: Geolocation data (GDPR PII)\n"
        "   - country, city: Derived from IP via geolocation service\n"
        "   - device_name: User-provided friendly name (optional)\n"
        "   - GDPR Article 15: Users can request all session data\n"
        "   - GDPR Article 17: Users can revoke all sessions (right to be forgotten)\n\n"
        "3. Session Lifecycle:\n"
        "   - Default expiration: 30 days from creation\n"
        "   - Sliding window: last_activity updated on every request (middleware)\n"
        "   - Absolute expiration: expires_at is fixed (no extension)\n"
        "   - Manual revocation: User or admin can revoke via revoke() method\n"
        "   - Automatic cleanup: Daily task deletes expired/revoked sessions >90 days old\n\n"
        "4. Suspicious Activity Detection:\n"
        "   - IP address change: Triggers is_suspicious flag and ip_change activity log\n"
        "   - Unusual access patterns: Rapid API calls, permission escalation attempts\n"
        "   - Geolocation anomalies: Session active in multiple countries within short time\n"
        "   - Device fingerprint mismatch: Same session_key with different fingerprint\n"
        "   - Automated response: Email alert to user, admin dashboard notification\n\n"
        "5. Multi-Device Management:\n"
        "   - Users can have multiple active sessions (different devices)\n"
        "   - is_current flag marks the current session (for UI highlighting)\n"
        "   - Users can view all active sessions and revoke individually\n"
        "   - Use case: 'Log out all other devices' feature\n\n"
        "6. Session Revocation:\n"
        "   - revoke() method sets revoked=True, revoked_at=now(), deletes Django Session\n"
        "   - revoke_reason tracks: user_action, admin_action, suspicious_activity, device_lost, security_breach\n"
        "   - revoked_by tracks who initiated revocation (user or admin)\n"
        "   - Irreversible: Once revoked, session cannot be restored (must create new session)\n\n"
        "7. Activity Logging:\n"
        "   - SessionActivityLog records significant events (login, logout, suspicious actions)\n"
        "   - High-frequency events (page views) are sampled or aggregated to prevent DB bloat\n"
        "   - metadata JSONField stores additional context (URL, request method, response status)\n"
        "   - is_suspicious flag enables fast queries for security analysis\n\n"
        "8. Access Controls:\n"
        "   - Users can only view/revoke their own sessions (enforced in service layer)\n"
        "   - Admins can view/revoke any user's sessions (requires admin permission)\n"
        "   - Session data exposed via API (requires authentication)\n"
        "   - Activity logs are admin-only (users see summary, not detailed logs)\n\n"
        "9. NEVER:\n"
        "   - Store session_key in plaintext in activity logs (use session ForeignKey)\n"
        "   - Expose user_agent or IP address in public API responses\n"
        "   - Allow session extension beyond expires_at (security risk)\n"
        "   - Trust client-provided device_name (sanitize input)"
    ),
    performance_notes=(
        "Database Indexes:\n"
        "- Composite: user+revoked (query active sessions per user)\n"
        "- Composite: device_fingerprint+user (detect duplicate devices)\n"
        "- Single: is_suspicious (security monitoring dashboard)\n"
        "- Single: expires_at (cleanup task queries)\n"
        "- Composite: session+timestamp (SessionActivityLog queries)\n"
        "- Composite: activity_type+timestamp (activity type analysis)\n\n"
        "Query Patterns:\n"
        "- High read volume: Middleware queries last_activity on every request\n"
        "- Medium write volume: Activity logging on significant events\n"
        "- Low write volume: Session creation (login), revocation\n"
        "- Cleanup: Daily batch job deletes expired/revoked sessions >90 days\n\n"
        "Performance Optimizations:\n"
        "- Use select_related('user', 'revoked_by') for UserSession queries (prevent N+1)\n"
        "- Cache active sessions per user (Redis: 5-minute TTL)\n"
        "- Batch activity logging (queue writes, flush every 10 seconds)\n"
        "- Partition SessionActivityLog by month (high volume table)\n"
        "- Use bulk_update() for last_activity updates (reduce DB round-trips)\n\n"
        "Scaling Considerations:\n"
        "- UserSession table: ~10K sessions for 1K active users (manageable)\n"
        "- SessionActivityLog table: ~1M rows/month at 100K requests/day (partition required)\n"
        "- Device fingerprint collisions: <0.01% with SHA256 (acceptable)\n"
        "- Cleanup job performance: Delete in batches of 1000 to prevent locks"
    ),
    examples=[
        "# Get all active sessions for user\n"
        "active_sessions = UserSession.objects.filter(\n"
        "    user=current_user,\n"
        "    revoked=False\n"
        ").select_related('user')\n"
        "# Returns QuerySet of active sessions with device info, location, last_activity\n",
        "# Check if session is still active\n"
        "session = UserSession.objects.get(session__session_key=request.session.session_key)\n"
        "if not session.is_active():\n"
        "    # Session expired or revoked\n"
        "    logout(request)\n"
        "    return redirect('login')\n",
        "# Revoke session (user logs out from another device)\n"
        "session = UserSession.objects.get(id=session_id, user=current_user)\n"
        "session.revoke(revoked_by=current_user, reason='user_action')\n"
        "# Deletes Django Session, sets revoked=True, logs revoked_at\n",
        "# Detect suspicious activity (IP change)\n"
        "session = UserSession.objects.get(session__session_key=request.session.session_key)\n"
        "if session.last_ip_address and session.last_ip_address != current_ip:\n"
        "    session.is_suspicious = True\n"
        "    session.suspicious_reason = f'IP changed from {session.last_ip_address} to {current_ip}'\n"
        "    session.last_ip_address = current_ip\n"
        "    session.save()\n"
        "    # Log activity\n"
        "    SessionActivityLog.objects.create(\n"
        "        session=session,\n"
        "        activity_type='ip_change',\n"
        "        description=session.suspicious_reason,\n"
        "        ip_address=current_ip,\n"
        "        is_suspicious=True\n"
        "    )\n"
        "    # Send alert email to user\n",
        "# Generate device fingerprint\n"
        "fingerprint = UserSession.generate_device_fingerprint(\n"
        "    user_agent=request.META['HTTP_USER_AGENT'],\n"
        "    ip_address=request.META['REMOTE_ADDR']\n"
        ")\n"
        "# Returns SHA256 hash for device tracking\n",
    ],
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


class SessionActivityLog(models.Model):
    """
    Log of session activities for security monitoring.

    Tracks significant session events for audit and anomaly detection.
    """

    session = models.ForeignKey(
        UserSession,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        help_text="Session that performed the activity"
    )

    activity_type = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('login', 'Login'),
            ('logout', 'Logout'),
            ('api_call', 'API Call'),
            ('page_view', 'Page View'),
            ('data_access', 'Data Access'),
            ('permission_escalation', 'Permission Escalation'),
            ('suspicious_action', 'Suspicious Action'),
            ('ip_change', 'IP Address Changed'),
        ],
        help_text="Type of activity"
    )

    description = models.TextField(
        blank=True,
        help_text="Activity description"
    )

    ip_address = models.GenericIPAddressField(
        help_text="IP address at time of activity"
    )

    url = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL accessed"
    )

    # Additional context
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional activity metadata"
    )

    # Security flags
    is_suspicious = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged as suspicious"
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'session_activity_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['activity_type', 'timestamp']),
            models.Index(fields=['is_suspicious', 'timestamp']),
        ]
        verbose_name = 'Session Activity Log'
        verbose_name_plural = 'Session Activity Logs'

    def __str__(self):
        return f"{self.activity_type} - {self.session.user.loginid} at {self.timestamp}"
