"""
Password Reset and Setup Service.

SECURITY FIX (2025-10-11): Replaces predictable default passwords with secure reset flow.
Implements Django's built-in password reset tokens for one-time password setup links.

Features:
- Secure token generation (Django's default_token_generator)
- Email-based password setup for new users
- One-time use tokens with 24-hour expiration
- PCI-DSS compliant (passwords never logged or transmitted)
- Integration with existing email infrastructure

Related Issues:
- CVSS 7.5: Predictable default passwords (fixed 2025-10-11)

Usage:
    from apps.peoples.services.password_reset_service import send_password_setup_email

    # After creating user with set_unusable_password()
    user = People.objects.create(loginid='newuser', email='user@example.com')
    user.set_unusable_password()
    user.save()

    # Send setup email
    email_sent = send_password_setup_email(user)
"""

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
import logging

logger = logging.getLogger(__name__)


def send_password_setup_email(user, request=None):
    """
    Send one-time password setup link to new user.

    SECURITY:
    - Uses Django's default_token_generator (HMAC-based, cryptographically secure)
    - Token valid for 24 hours (PASSWORD_RESET_TIMEOUT setting)
    - Token invalidated after use
    - No password transmitted via email

    Args:
        user: People instance with unusable password
        request: Optional HTTP request for building absolute URL

    Returns:
        bool: True if email sent successfully, False otherwise

    Example:
        >>> user = People.objects.create(loginid='jdoe', email='jdoe@example.com')
        >>> user.set_unusable_password()
        >>> user.save()
        >>> email_sent = send_password_setup_email(user)
        >>> if not email_sent:
        ...     logger.error(f"Failed to send setup email to {user.loginid}")
    """
    # Validate user has email
    if not user.email:
        logger.error(
            f"Cannot send password setup email: User {user.loginid} has no email address",
            extra={'user_id': user.id, 'loginid': user.loginid}
        )
        return False

    # Generate secure token
    token = default_token_generator.make_token(user)

    # Encode user ID (prevents URL manipulation)
    uid = urlsafe_base64_encode(force_bytes(user.id))

    # Build password reset URL
    # If request is available, use it to build absolute URL
    if request:
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        reset_url = f"{protocol}://{domain}/people/password-reset/{uid}/{token}/"
    else:
        # Fallback to settings
        site_url = getattr(settings, 'SITE_URL', 'https://django5.youtility.in')
        reset_url = f"{site_url}/people/password-reset/{uid}/{token}/"

    # Prepare email context
    context = {
        'user': user,
        'reset_url': reset_url,
        'expiry_hours': 24,
        'site_name': getattr(settings, 'SITE_NAME', 'Youtility Platform'),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@youtility.in'),
    }

    # Render email templates
    try:
        html_message = render_to_string('emails/password_setup.html', context)
        plain_message = render_to_string('emails/password_setup.txt', context)
    except Exception as e:
        logger.error(
            f"Failed to render password setup email templates: {e}",
            exc_info=True,
            extra={'user_id': user.id, 'template_error': str(e)}
        )
        return False

    # Send email
    try:
        send_mail(
            subject=f'Set Your Password - {context["site_name"]}',
            message=plain_message,
            html_message=html_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@youtility.in'),
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(
            f"Password setup email sent to user {user.loginid}",
            extra={
                'user_id': user.id,
                'email': user.email,
                'security_event': 'password_setup_email_sent'
            }
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to send password setup email to {user.loginid}: {e}",
            exc_info=True,
            extra={
                'user_id': user.id,
                'email': user.email,
                'error': str(e),
                'security_event': 'password_setup_email_failed'
            }
        )
        return False


def send_password_reset_email(user, request=None):
    """
    Send password reset link to existing user.

    This is an alias to send_password_setup_email() for password resets.
    The same secure token mechanism is used for both setup and reset.

    Args:
        user: People instance requesting password reset
        request: Optional HTTP request for building absolute URL

    Returns:
        bool: True if email sent successfully, False otherwise

    Example:
        >>> user = People.objects.get(loginid='jdoe')
        >>> reset_sent = send_password_reset_email(user, request)
    """
    return send_password_setup_email(user, request)


def verify_password_reset_token(user, token):
    """
    Verify if password reset token is valid for user.

    SECURITY:
    - Token expires after PASSWORD_RESET_TIMEOUT (default: 24 hours)
    - Token invalidated after password change
    - Timing-attack resistant (constant-time comparison)

    Args:
        user: People instance
        token: Password reset token from URL

    Returns:
        bool: True if token is valid and not expired, False otherwise

    Example:
        >>> user = People.objects.get(id=decode_uid(uid))
        >>> if verify_password_reset_token(user, token):
        ...     # Allow password reset
        ...     user.set_password(new_password)
        ...     user.save()
    """
    return default_token_generator.check_token(user, token)


# Export public API
__all__ = [
    'send_password_setup_email',
    'send_password_reset_email',
    'verify_password_reset_token',
]
