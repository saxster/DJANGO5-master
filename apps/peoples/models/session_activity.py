"""
Session Activity Logging Model

Logs significant session events for security monitoring and anomaly detection.

Compliance:
    - Rule #7: Model < 150 lines
    - SOC 2: Complete audit trail
"""

from django.db import models

from apps.ontology.decorators import ontology


@ontology(
    domain="people",
    concept="Session Activity Logging",
    purpose=(
        "Logs significant session events for security monitoring and anomaly detection. "
        "Tracks login, logout, IP changes, and suspicious activities."
    ),
    criticality="high",
    security_boundary=True,
    models=[{
        "name": "SessionActivityLog",
        "purpose": "Logs significant session events for security monitoring",
        "pii_fields": ["ip_address", "url"],
        "retention": "90 days (configurable)",
        "activity_types": [
            "login", "logout", "api_call", "page_view", "data_access",
            "permission_escalation", "suspicious_action", "ip_change"
        ],
    }],
    tags=["security", "audit-trail", "monitoring", "soc2"],
)
class SessionActivityLog(models.Model):
    """
    Log of session activities for security monitoring.

    Tracks significant session events for audit and anomaly detection.
    """

    session = models.ForeignKey(
        'peoples.UserSession',
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
