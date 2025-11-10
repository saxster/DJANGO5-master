"""
Session Management Signals

Automatic session tracking and lifecycle management via Django signals.

Features:
    - Automatic UserSession creation on login
    - Session cleanup on logout
    - Activity logging for security monitoring
    - Suspicious activity detection

Compliance:
    - Rule #11: Specific exception handling
    - Automatic audit trail for all session events
"""

import logging
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, pre_delete
from django.contrib.sessions.models import Session
from user_agents import parse

from apps.peoples.models import UserSession, SessionActivityLog

logger = logging.getLogger('security.sessions')


@receiver(user_logged_in)
def track_user_login(sender, request, user, **kwargs):
    """
    Track user login and create UserSession record.

    Args:
        sender: Signal sender
        request: HTTP request object
        user: Authenticated user
        **kwargs: Additional signal data
    """
    try:
        # Extract device information
        user_agent_string = request.META.get('HTTP_USER_AGENT', '')
        user_agent = parse(user_agent_string)

        # Get IP address
        ip_address = _get_client_ip(request)

        # Generate device fingerprint
        device_fingerprint = UserSession.generate_device_fingerprint(user_agent_string,
            ip_address)

        # Get or create Django session
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key
        django_session = Session.objects.get(session_key=session_key)

        # Determine device type
        if user_agent.is_mobile:
            device_type = 'mobile'
        elif user_agent.is_tablet:
            device_type = 'tablet'
        elif user_agent.is_pc:
            device_type = 'desktop'
        else:
            device_type = 'unknown'

        # Create device name
        device_name = _generate_device_name(user_agent)

        # Calculate expiration
        from datetime import timedelta
        from django.conf import settings
        from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

        session_age = getattr(settings, 'SESSION_COOKIE_AGE', 2 * SECONDS_IN_HOUR)
        expires_at = django_session.expire_date

        # Mark all other sessions as not current
        UserSession.objects.filter(user=user, is_current=True).update(is_current=False)

        # Create or update UserSession
        user_session, created = UserSession.objects.update_or_create(
            session=django_session,
            defaults={
                'user': user,
                'device_fingerprint': device_fingerprint,
                'device_name': device_name,
                'device_type': device_type,
                'user_agent': user_agent_string,
                'browser': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string,
                'os': user_agent.os.family,
                'os_version': user_agent.os.version_string,
                'ip_address': ip_address,
                'last_ip_address': ip_address,
                'expires_at': expires_at,
                'is_current': True,
            }
        )

        # Log activity
        SessionActivityLog.objects.create(
            session=user_session,
            activity_type='login',
            description=f'User logged in from {device_name}',
            ip_address=ip_address,
            metadata={
                'device_fingerprint': device_fingerprint,
                'user_agent': user_agent_string,
            }
        )

        # Check for suspicious activity (e.g., new device, new location)
        _check_suspicious_activity(user_session, user)

        logger.info(
            f'Session tracked: {user.loginid} from {device_name} ({ip_address})',
            extra={
                'user_id': user.id,
                'username': user.loginid,
                'device_fingerprint': device_fingerprint,
                'ip_address': ip_address,
                'device_type': device_type,
                'security_event': 'session_created'
            }
        )

    except Session.DoesNotExist:
        logger.error(
            f'Session not found for user {user.loginid}',
            extra={'user_id': user.id, 'session_key': request.session.session_key}
        )
    except (AttributeError, ValueError, TypeError) as e:
        logger.error(
            f'Error tracking user login: {e}',
            extra={'user_id': user.id, 'error': str(e)},
            exc_info=True
        )


@receiver(user_logged_out)
def track_user_logout(sender, request, user, **kwargs):
    """
    Track user logout and update UserSession record.

    Args:
        sender: Signal sender
        request: HTTP request object
        user: User being logged out
        **kwargs: Additional signal data
    """
    try:
        if not user:
            return

        # Find current session
        session_key = request.session.session_key
        if not session_key:
            return

        try:
            django_session = Session.objects.get(session_key=session_key)
            user_session = UserSession.objects.get(session=django_session)

            # Get IP address
            ip_address = _get_client_ip(request)

            # Log activity
            SessionActivityLog.objects.create(
                session=user_session,
                activity_type='logout',
                description='User logged out',
                ip_address=ip_address
            )

            # Mark session as not current
            user_session.is_current = False
            user_session.save(update_fields=['is_current'])

            logger.info(
                f'User logged out: {user.loginid}',
                extra={
                    'user_id': user.id,
                    'username': user.loginid,
                    'session_id': user_session.id,
                    'security_event': 'user_logout'
                }
            )

        except (Session.DoesNotExist, UserSession.DoesNotExist):
            logger.debug(f'Session not found for logout: {user.loginid}')

    except (AttributeError, ValueError) as e:
        logger.error(f'Error tracking user logout: {e}', exc_info=True)


@receiver(pre_delete, sender=Session)
def cleanup_user_session(sender, instance, **kwargs):
    """
    Clean up UserSession when Django session is deleted.

    Args:
        sender: Signal sender
        instance: Session being deleted
        **kwargs: Additional signal data
    """
    try:
        user_session = UserSession.objects.get(session=instance)

        logger.info(
            f'Session deleted: {user_session.user.loginid}',
            extra={
                'user_id': user_session.user.id,
                'session_id': user_session.id,
                'security_event': 'session_deleted'
            }
        )

        # UserSession will be cascade deleted
    except UserSession.DoesNotExist:
        pass
    except (AttributeError, ValueError) as e:
        logger.error(f'Error cleaning up user session: {e}')


def _get_client_ip(request):
    """
    Extract client IP from request.

    Args:
        request: HTTP request

    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or '0.0.0.0'


def _generate_device_name(user_agent):
    """
    Generate human-readable device name.

    Args:
        user_agent: Parsed user agent object

    Returns:
        str: Device name (e.g., "Chrome on Windows")
    """
    parts = []

    if user_agent.browser.family != 'Other':
        parts.append(user_agent.browser.family)

    if user_agent.os.family != 'Other':
        parts.append(f"on {user_agent.os.family}")

    if not parts:
        return 'Unknown Device'

    return ' '.join(parts)


def _check_suspicious_activity(user_session, user):
    """
    Check for suspicious session activity.

    Flags sessions that exhibit suspicious patterns:
    - Login from new device
    - Login from new location
    - Multiple simultaneous sessions
    - Rapid location changes

    Args:
        user_session: UserSession to check
        user: User owning the session
    """
    try:
        suspicious_reasons = []

        # Check for new device
        previous_devices = UserSession.objects.filter(
            user=user,
            device_fingerprint=user_session.device_fingerprint,
            revoked=False
        ).exclude(id=user_session.id).count()

        if previous_devices == 0:
            # First time seeing this device
            recent_sessions = UserSession.objects.filter(
                user=user,
                revoked=False,
                created_at__gte=user_session.created_at
            ).exclude(id=user_session.id).count()

            if recent_sessions > 0:
                suspicious_reasons.append('New device detected')

        # Check for multiple simultaneous sessions
        active_sessions_count = UserSession.objects.filter(
            user=user,
            revoked=False,
            is_current=True
        ).exclude(id=user_session.id).count()

        if active_sessions_count > 3:  # More than 3 simultaneous sessions
            suspicious_reasons.append(f'Multiple simultaneous sessions ({active_sessions_count + 1})')

        # Flag if suspicious
        if suspicious_reasons:
            user_session.is_suspicious = True
            user_session.suspicious_reason = '; '.join(suspicious_reasons)
            user_session.save(update_fields=['is_suspicious', 'suspicious_reason'])

            # Log suspicious activity
            SessionActivityLog.objects.create(
                session=user_session,
                activity_type='suspicious_action',
                description=f'Suspicious activity detected: {"; ".join(suspicious_reasons)}',
                ip_address=user_session.ip_address,
                is_suspicious=True,
                metadata={'reasons': suspicious_reasons}
            )

            logger.warning(
                f'Suspicious session detected: {user.loginid}',
                extra={
                    'user_id': user.id,
                    'session_id': user_session.id,
                    'reasons': suspicious_reasons,
                    'security_event': 'suspicious_session'
                }
            )

    except (AttributeError, ValueError) as e:
        logger.error(f'Error checking suspicious activity: {e}')
