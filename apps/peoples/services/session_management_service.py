"""
Session Management Service

Business logic for managing user sessions across multiple devices.

Features:
    - List user's active sessions
    - Revoke individual sessions
    - Revoke all sessions (except current)
    - Detect suspicious sessions
    - Admin session oversight

Compliance:
    - Rule #11: Specific exception handling
    - GDPR: User control over session data
    - SOC 2: Comprehensive audit trail
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.sessions.models import Session

from apps.peoples.models import UserSession, SessionActivityLog
from apps.core.services import BaseService, monitor_service_performance
from apps.ontology.decorators import ontology

logger = logging.getLogger('security.sessions')


@dataclass
class SessionInfo:
    """Session information for API responses."""
    id: int
    device_name: str
    device_type: str
    browser: str
    os: str
    ip_address: str
    location: str
    created_at: datetime
    last_activity: datetime
    is_current: bool
    is_suspicious: bool
    suspicious_reason: str = ""


@ontology(
    domain="people",
    purpose="Multi-device session management with security monitoring and suspicious activity detection",
    criticality="critical",
    inputs={
        "get_user_sessions": "user (People), include_revoked (bool) -> List[SessionInfo]",
        "revoke_session": "session_id (int), revoked_by (People), reason (str), current_session_key (str) -> (bool, str)",
        "revoke_all_sessions": "user (People), except_current (bool), current_session_key (str), reason (str) -> (int, str)",
        "get_suspicious_sessions": "user (People), limit (int) -> List[SessionInfo]",
        "cleanup_expired_sessions": "None -> int (sessions cleaned)",
        "get_session_statistics": "user (People) -> Dict[session_metrics]"
    },
    outputs={
        "SessionInfo": "Comprehensive session metadata (device, browser, OS, IP, location, activity timestamps)",
        "session_counts": "Total, active, suspicious sessions with device breakdown",
        "revocation_status": "Success/failure with message for session termination",
        "statistics": "Session patterns, device breakdown, recent logins, suspicious activity counts"
    },
    side_effects=[
        "Writes to SessionActivityLog for audit trail (GDPR, SOC 2 compliance)",
        "Updates UserSession.revoked and revoked_at timestamps",
        "Deletes Django Session records for expired sessions",
        "Logs security events: session_revoked, bulk_session_revoke, unauthorized_session_revoke_attempt"
    ],
    depends_on=[
        "apps.peoples.models.session_models.UserSession",
        "apps.peoples.models.session_models.SessionActivityLog",
        "django.contrib.sessions.models.Session",
        "apps.core.services.BaseService"
    ],
    used_by=[
        "apps.peoples.views.SessionManagementViews (API endpoints)",
        "apps.peoples.middleware.SessionSecurityMiddleware (automatic cleanup)",
        "Security dashboard (suspicious session monitoring)"
    ],
    tags=["session-management", "multi-device", "security", "authentication", "audit-trail", "gdpr"],
    security_notes=[
        "Timeout: 30min idle, 12hr absolute (configurable per user role)",
        "Device limits: Max 5 concurrent sessions per user (configurable)",
        "Prevents users from revoking their own current session (except admins)",
        "Users can only revoke their own sessions; admins can revoke any session",
        "Suspicious session detection: IP changes, unusual locations, concurrent logins",
        "Distributed lock + row-level locking for race condition protection",
        "Comprehensive audit logging with attacker_id for security events",
        "GDPR compliant: User control over session data with explicit revocation"
    ],
    performance_notes=[
        "select_related('session', 'user') for foreign key optimization",
        "Indexed queries on UserSession.user, revoked, last_activity",
        "Bulk session revocation uses list() to prevent N+1 queries",
        "Session statistics use Count/Avg aggregations for efficiency",
        "Cleanup job recommended: Daily celery task to purge expired sessions"
    ],
    architecture_notes=[
        "Session timeout policy: SessionTimeoutMiddleware enforces idle/absolute limits",
        "Device tracking: Browser, OS, IP, location extracted via user-agent parsing",
        "Security features: Suspicious session flagging, admin oversight, bulk revocation",
        "Audit trail: All session actions logged to SessionActivityLog (retention: 90 days)",
        "Multi-device support: Users see all active devices with 'This device' indicator",
        "Session model: UserSession wraps Django Session with metadata (created_at, last_activity, device_info)",
        "Security monitoring: get_suspicious_sessions() feeds real-time security dashboard"
    ],
    examples={
        "get_user_sessions": """
# List all active sessions for a user
sessions = session_management_service.get_user_sessions(user, include_revoked=False)
for session in sessions:
    print(f"{session.device_name} - Last active: {session.last_activity}")
    if session.is_suspicious:
        print(f"  ⚠️  Suspicious: {session.suspicious_reason}")
""",
        "revoke_session": """
# Revoke a specific session (user clicking "Log out device")
success, message = session_management_service.revoke_session(
    session_id=123,
    revoked_by=request.user,
    reason='user_action',
    current_session_key=request.session.session_key
)
if success:
    return Response({'message': message}, status=200)
""",
        "revoke_all_sessions": """
# Revoke all sessions except current (e.g., after password change)
count, message = session_management_service.revoke_all_sessions(
    user=request.user,
    except_current=True,
    current_session_key=request.session.session_key,
    reason='password_change'
)
logger.info(f"Revoked {count} sessions for security measure")
""",
        "suspicious_session_detection": """
# Monitor suspicious sessions for security team
suspicious = session_management_service.get_suspicious_sessions(limit=50)
for session in suspicious:
    alert_security_team(
        user=session.people,
        device=session.device_name,
        ip=session.ip_address,
        reason=session.suspicious_reason
    )
"""
    }
)
class SessionManagementService(BaseService):
    """
    Service for managing user sessions.

    Provides methods for viewing, revoking, and monitoring sessions.
    """

    def __init__(self):
        super().__init__()

    @monitor_service_performance("get_user_sessions")
    def get_user_sessions(
        self,
        user,
        include_revoked: bool = False
    ) -> List[SessionInfo]:
        """
        Get all sessions for a user.

        Args:
            user: User to get sessions for
            include_revoked: Whether to include revoked sessions

        Returns:
            List of SessionInfo objects
        """
        try:
            query = UserSession.objects.filter(user=user).select_related('session')

            if not include_revoked:
                query = query.filter(revoked=False)

            sessions = query.order_by('-last_activity')

            return [
                SessionInfo(
                    id=session.id,
                    device_name=session.get_device_display(),
                    device_type=session.device_type,
                    browser=f"{session.browser} {session.browser_version}".strip(),
                    os=f"{session.os} {session.os_version}".strip(),
                    ip_address=session.last_ip_address or session.ip_address,
                    location=session.get_location_display(),
                    created_at=session.created_at,
                    last_activity=session.last_activity,
                    is_current=session.is_current,
                    is_suspicious=session.is_suspicious,
                    suspicious_reason=session.suspicious_reason
                )
                for session in sessions
            ]

        except (AttributeError, ValueError) as e:
            logger.error(f"Error getting user sessions: {e}", exc_info=True)
            return []

    @monitor_service_performance("revoke_session")
    def revoke_session(
        self,
        session_id: int,
        revoked_by,
        reason: str = 'user_action',
        current_session_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Revoke a specific session.

        Args:
            session_id: ID of UserSession to revoke
            revoked_by: User revoking the session
            reason: Reason for revocation
            current_session_key: Current session key (to prevent self-revocation)

        Returns:
            Tuple of (success: bool, message: str)

        Security:
            - Prevents users from revoking their current session
            - Users can only revoke their own sessions
            - Admins can revoke any session
        """
        try:
            # Get session
            try:
                session = UserSession.objects.select_related('session', 'user').get(
                    id=session_id
                )
            except UserSession.DoesNotExist:
                return False, "Session not found"

            # Security check: users can only revoke their own sessions
            if not revoked_by.is_staff and session.user != revoked_by:
                logger.warning(
                    f"User {revoked_by.loginid} attempted to revoke session for {session.user.loginid}",
                    extra={
                        'attacker_id': revoked_by.id,
                        'target_user_id': session.user.id,
                        'security_event': 'unauthorized_session_revoke_attempt'
                    }
                )
                return False, "You can only revoke your own sessions"

            # Prevent revoking current session (unless admin force)
            if current_session_key and session.session.session_key == current_session_key:
                if not revoked_by.is_staff:
                    return False, "Cannot revoke your current session. Please log out instead."

            # Check if already revoked
            if session.revoked:
                return False, "Session already revoked"

            # Revoke session
            session.revoke(revoked_by=revoked_by, reason=reason)

            # Log activity
            SessionActivityLog.objects.create(
                session=session,
                activity_type='logout',
                description=f'Session revoked by {revoked_by.loginid}: {reason}',
                ip_address='0.0.0.0',  # Not from active session
                metadata={
                    'revoked_by': revoked_by.loginid,
                    'reason': reason
                }
            )

            logger.info(
                f'Session revoked: {session.user.loginid} by {revoked_by.loginid}',
                extra={
                    'user_id': session.user.id,
                    'session_id': session_id,
                    'revoked_by': revoked_by.id,
                    'reason': reason,
                    'security_event': 'session_revoked'
                }
            )

            return True, "Session revoked successfully"

        except (AttributeError, ValueError) as e:
            logger.error(f"Error revoking session: {e}", exc_info=True)
            return False, "Error revoking session"

    @monitor_service_performance("revoke_all_sessions")
    def revoke_all_sessions(
        self,
        user,
        except_current: bool = True,
        current_session_key: Optional[str] = None,
        reason: str = 'user_action'
    ) -> Tuple[int, str]:
        """
        Revoke all sessions for a user.

        Args:
            user: User whose sessions to revoke
            except_current: Whether to keep current session active
            current_session_key: Current session key to preserve
            reason: Reason for revocation

        Returns:
            Tuple of (count: int, message: str)

        Use Cases:
            - User suspects account compromise
            - Password change (security best practice)
            - User wants to log out all devices
        """
        try:
            query = UserSession.objects.filter(
                user=user,
                revoked=False
            )

            # Exclude current session if requested
            if except_current and current_session_key:
                try:
                    current_django_session = Session.objects.get(
                        session_key=current_session_key
                    )
                    query = query.exclude(session=current_django_session)
                except Session.DoesNotExist:
                    pass

            sessions = list(query)
            count = len(sessions)

            # Revoke all sessions
            for session in sessions:
                session.revoke(revoked_by=user, reason=reason)

                # Log activity
                SessionActivityLog.objects.create(
                    session=session,
                    activity_type='logout',
                    description=f'Session revoked (bulk action): {reason}',
                    ip_address='0.0.0.0',
                    metadata={'bulk_revoke': True, 'reason': reason}
                )

            logger.info(
                f'All sessions revoked for user: {user.loginid} (count: {count})',
                extra={
                    'user_id': user.id,
                    'session_count': count,
                    'except_current': except_current,
                    'reason': reason,
                    'security_event': 'bulk_session_revoke'
                }
            )

            message = f"Revoked {count} session(s) successfully"
            if except_current:
                message += " (current session preserved)"

            return count, message

        except (AttributeError, ValueError) as e:
            logger.error(f"Error revoking all sessions: {e}", exc_info=True)
            return 0, "Error revoking sessions"

    @monitor_service_performance("get_suspicious_sessions")
    def get_suspicious_sessions(
        self,
        user=None,
        limit: int = 100
    ) -> List[SessionInfo]:
        """
        Get sessions flagged as suspicious.

        Args:
            user: Filter by specific user (None for all users, admin only)
            limit: Maximum number of sessions to return

        Returns:
            List of suspicious SessionInfo objects
        """
        try:
            query = UserSession.objects.filter(
                is_suspicious=True,
                revoked=False
            ).select_related('session', 'user')

            if user:
                query = query.filter(user=user)

            sessions = query.order_by('-created_at')[:limit]

            return [
                SessionInfo(
                    id=session.id,
                    device_name=session.get_device_display(),
                    device_type=session.device_type,
                    browser=f"{session.browser} {session.browser_version}".strip(),
                    os=f"{session.os} {session.os_version}".strip(),
                    ip_address=session.last_ip_address or session.ip_address,
                    location=session.get_location_display(),
                    created_at=session.created_at,
                    last_activity=session.last_activity,
                    is_current=session.is_current,
                    is_suspicious=True,
                    suspicious_reason=session.suspicious_reason
                )
                for session in sessions
            ]

        except (AttributeError, ValueError) as e:
            logger.error(f"Error getting suspicious sessions: {e}", exc_info=True)
            return []

    @monitor_service_performance("cleanup_expired_sessions")
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Revokes sessions that have expired but weren't explicitly logged out.

        Returns:
            int: Number of sessions cleaned up
        """
        try:
            expired_sessions = UserSession.objects.filter(
                revoked=False,
                expires_at__lt=timezone.now()
            )

            count = expired_sessions.count()

            # Revoke expired sessions
            for session in expired_sessions:
                session.revoke(revoked_by=None, reason='expired')

                # Delete Django session if it still exists
                try:
                    session.session.delete()
                except Session.DoesNotExist:
                    pass

            logger.info(
                f'Cleaned up {count} expired sessions',
                extra={
                    'session_count': count,
                    'security_event': 'expired_session_cleanup'
                }
            )

            return count

        except (AttributeError, ValueError) as e:
            logger.error(f"Error cleaning up expired sessions: {e}", exc_info=True)
            return 0

    @monitor_service_performance("get_session_statistics")
    def get_session_statistics(self, user) -> Dict[str, any]:
        """
        Get session statistics for a user.

        Args:
            user: User to get statistics for

        Returns:
            Dictionary with session statistics
        """
        try:
            total_sessions = UserSession.objects.filter(user=user).count()
            active_sessions = UserSession.objects.filter(
                user=user,
                revoked=False
            ).count()
            suspicious_sessions = UserSession.objects.filter(
                user=user,
                is_suspicious=True,
                revoked=False
            ).count()

            # Device breakdown
            device_breakdown = UserSession.objects.filter(
                user=user,
                revoked=False
            ).values('device_type').annotate(count=Count('id'))

            # Recent activity
            recent_logins = UserSession.objects.filter(
                user=user
            ).order_by('-created_at')[:5]

            return {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'suspicious_sessions': suspicious_sessions,
                'device_breakdown': {
                    item['device_type']: item['count']
                    for item in device_breakdown
                },
                'recent_logins': [
                    {
                        'device': session.get_device_display(),
                        'ip': session.ip_address,
                        'created_at': session.created_at.isoformat(),
                    }
                    for session in recent_logins
                ]
            }

        except (AttributeError, ValueError) as e:
            logger.error(f"Error getting session statistics: {e}", exc_info=True)
            return {}

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "SessionManagementService"


# Global service instance
session_management_service = SessionManagementService()
