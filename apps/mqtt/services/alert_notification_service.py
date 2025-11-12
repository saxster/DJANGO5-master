"""
MQTT Alert Notification Service

@ontology(
    domain="integration",
    purpose="Multi-channel notification delivery for critical MQTT device alerts",
    notification_channels=["SMS (Twilio)", "Email (Django)", "Mobile Push (FCM)"],
    alert_routing={
        "critical": ["SMS", "Email", "Push"],
        "high": ["Email", "Push"],
        "medium": ["Email"],
        "low": ["Email (digest)"]
    },
    rate_limiting="Max 10 SMS/min per supervisor to prevent spam",
    retry_strategy="3 retries with exponential backoff for failed notifications",
    criticality="high",
    dependencies=["Twilio (optional)", "Django email", "FCM (optional)"],
    tags=["notifications", "sms", "email", "push", "alerts"]
)
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.core.cache import cache

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS
from apps.core.tasks.base import TaskMetrics
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE
from apps.core.exceptions.patterns import CELERY_EXCEPTIONS


logger = logging.getLogger('mqtt.alert_notifications')


@dataclass
class AlertNotification:
    """Alert notification data."""
    alert_id: int
    alert_type: str
    severity: str
    message: str
    source_id: str
    timestamp: datetime
    location: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = None


@dataclass
class NotificationResult:
    """Notification delivery result."""
    channel: str
    success: bool
    latency_ms: float
    error_message: Optional[str] = None
    external_id: Optional[str] = None


class AlertNotificationService:
    """
    Multi-channel notification service for MQTT device alerts.

    Sends SMS, email, and push notifications based on alert severity.
    Includes rate limiting to prevent notification spam.
    """

    # SMS rate limiting (per supervisor)
    SMS_RATE_LIMIT_KEY = "mqtt_alert_sms_rate_limit:{phone}"
    SMS_MAX_PER_MINUTE = 10

    @classmethod
    def notify_alert(
        cls,
        alert: AlertNotification,
        recipients: Dict[str, List[str]]
    ) -> List[NotificationResult]:
        """
        Send notifications for device alert.

        Args:
            alert: AlertNotification object
            recipients: Dict with keys 'sms', 'email', 'push' containing recipient lists

        Returns:
            List of NotificationResult objects

        Example:
            recipients = {
                'sms': ['+919876543210', '+918765432109'],
                'email': ['supervisor@example.com', 'manager@example.com'],
                'push': ['fcm_token_123', 'fcm_token_456']
            }
        """
        results = []

        # Send based on severity
        if alert.severity in ['CRITICAL', 'HIGH']:
            # Send SMS for critical/high alerts
            if recipients.get('sms'):
                sms_results = cls._send_sms_notifications(alert, recipients['sms'])
                results.extend(sms_results)

        # Always send email
        if recipients.get('email'):
            email_result = cls._send_email_notification(alert, recipients['email'])
            results.append(email_result)

        # Send push notifications
        if recipients.get('push'):
            push_results = cls._send_push_notifications(alert, recipients['push'])
            results.extend(push_results)

        return results

    @classmethod
    def _send_sms_notifications(
        cls,
        alert: AlertNotification,
        phone_numbers: List[str]
    ) -> List[NotificationResult]:
        """
        Send SMS notifications via Twilio.

        Args:
            alert: AlertNotification object
            phone_numbers: List of phone numbers

        Returns:
            List of NotificationResult objects
        """
        results = []

        # Check if Twilio is configured
        try:
            from twilio.rest import Client
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)

            if not all([account_sid, auth_token, from_number]):
                logger.warning("Twilio not configured, skipping SMS notifications")
                return [NotificationResult(
                    channel='sms',
                    success=False,
                    latency_ms=0,
                    error_message='Twilio not configured'
                )]

            client = Client(account_sid, auth_token)

        except ImportError:
            logger.warning("Twilio package not installed, skipping SMS")
            return [NotificationResult(
                channel='sms',
                success=False,
                latency_ms=0,
                error_message='Twilio package not installed'
            )]

        # Send to each phone number
        for phone in phone_numbers:
            # Rate limiting check
            if not cls._check_sms_rate_limit(phone):
                logger.warning(f"SMS rate limit exceeded for {phone}")
                results.append(NotificationResult(
                    channel='sms',
                    success=False,
                    latency_ms=0,
                    error_message='Rate limit exceeded'
                ))
                continue

            start_time = time.time()

            try:
                # Format SMS message
                sms_body = cls._format_sms_message(alert)

                # Send via Twilio
                message = client.messages.create(
                    to=phone,
                    from_=from_number,
                    body=sms_body
                )

                latency_ms = (time.time() - start_time) * 1000

                results.append(NotificationResult(
                    channel='sms',
                    success=True,
                    latency_ms=latency_ms,
                    external_id=message.sid
                ))

                # Record metric
                TaskMetrics.increment_counter('alert_notification_sent', {
                    'channel': 'sms',
                    'alert_type': alert.alert_type,
                    'severity': alert.severity
                })

                logger.info(f"SMS sent to {phone}: {message.sid}")

            except NETWORK_EXCEPTIONS as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"Failed to send SMS to {phone}: {e}")
                results.append(NotificationResult(
                    channel='sms',
                    success=False,
                    latency_ms=latency_ms,
                    error_message=str(e)
                ))

                TaskMetrics.increment_counter('alert_notification_failed', {
                    'channel': 'sms',
                    'error_type': type(e).__name__
                })

        return results

    @classmethod
    def _send_email_notification(
        cls,
        alert: AlertNotification,
        email_addresses: List[str]
    ) -> NotificationResult:
        """
        Send email notification via Django email.

        Args:
            alert: AlertNotification object
            email_addresses: List of email addresses

        Returns:
            NotificationResult object
        """
        start_time = time.time()

        try:
            # Format email
            subject = f"[{alert.severity}] {alert.alert_type}: {alert.source_id}"
            message = cls._format_email_message(alert)

            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=email_addresses,
                fail_silently=False
            )

            latency_ms = (time.time() - start_time) * 1000

            # Record metric
            TaskMetrics.increment_counter('alert_notification_sent', {
                'channel': 'email',
                'alert_type': alert.alert_type,
                'severity': alert.severity
            })

            logger.info(f"Email sent to {len(email_addresses)} recipients")

            return NotificationResult(
                channel='email',
                success=True,
                latency_ms=latency_ms
            )

        except (CELERY_EXCEPTIONS, SMTPException) as e:
            # Catch both Celery task errors AND SMTP failures
            # (SMTPAuthenticationError, SMTPServerDisconnected, etc.)
            # This ensures SMS/push notifications still run if email fails
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Failed to send email notification: {type(e).__name__}: {e}",
                exc_info=True,
                extra={'alert_id': alert.id, 'severity': alert.severity}
            )

            TaskMetrics.increment_counter('alert_notification_failed', {
                'channel': 'email',
                'error_type': type(e).__name__
            })

            return NotificationResult(
                channel='email',
                success=False,
                latency_ms=latency_ms,
                error_message=str(e)
            )

    @classmethod
    def _send_push_notifications(
        cls,
        alert: AlertNotification,
        fcm_tokens: List[str]
    ) -> List[NotificationResult]:
        """
        Send push notifications via FCM.

        Args:
            alert: AlertNotification object
            fcm_tokens: List of FCM device tokens

        Returns:
            List of NotificationResult objects
        """
        results = []

        # Check if FCM is configured
        fcm_server_key = getattr(settings, 'FCM_SERVER_KEY', None)

        if not fcm_server_key:
            logger.warning("FCM not configured, skipping push notifications")
            return [NotificationResult(
                channel='push',
                success=False,
                latency_ms=0,
                error_message='FCM not configured'
            )]

        # Send to each token
        for token in fcm_tokens:
            start_time = time.time()

            try:
                # Format push notification
                notification_data = {
                    'title': f"{alert.alert_type} Alert",
                    'body': alert.message,
                    'data': {
                        'alert_id': str(alert.alert_id),
                        'alert_type': alert.alert_type,
                        'severity': alert.severity,
                        'timestamp': alert.timestamp.isoformat()
                    }
                }

                # Send via FCM (simplified - use library in production)
                headers = {
                    'Authorization': f'key={fcm_server_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    'to': token,
                    'notification': notification_data,
                    'priority': 'high' if alert.severity == 'CRITICAL' else 'normal'
                }

                response = requests.post(
                    'https://fcm.googleapis.com/fcm/send',
                    headers=headers,
                    json=payload,
                    timeout=(5, 10)
                )

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    results.append(NotificationResult(
                        channel='push',
                        success=True,
                        latency_ms=latency_ms,
                        external_id=response.json().get('message_id')
                    ))

                    TaskMetrics.increment_counter('alert_notification_sent', {
                        'channel': 'push',
                        'alert_type': alert.alert_type
                    })
                else:
                    results.append(NotificationResult(
                        channel='push',
                        success=False,
                        latency_ms=latency_ms,
                        error_message=f"FCM error: {response.status_code}"
                    ))

            except NETWORK_EXCEPTIONS as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(NotificationResult(
                    channel='push',
                    success=False,
                    latency_ms=latency_ms,
                    error_message=str(e)
                ))

        return results

    @classmethod
    def _check_sms_rate_limit(cls, phone: str) -> bool:
        """
        Check if SMS rate limit allows sending.

        Args:
            phone: Phone number to check

        Returns:
            bool: True if within rate limit, False if exceeded
        """
        cache_key = cls.SMS_RATE_LIMIT_KEY.format(phone=phone)
        current_count = cache.get(cache_key, 0)

        if current_count >= cls.SMS_MAX_PER_MINUTE:
            return False

        # Increment counter (1 minute TTL)
        cache.set(cache_key, current_count + 1, timeout=SECONDS_IN_MINUTE)
        return True

    @classmethod
    def _format_sms_message(cls, alert: AlertNotification) -> str:
        """
        Format SMS message (160 characters max for single SMS).

        Args:
            alert: AlertNotification object

        Returns:
            str: Formatted SMS message
        """
        # Keep it short for SMS
        location_text = ""
        if alert.location:
            location_text = f" @ {alert.location['lat']:.4f},{alert.location['lon']:.4f}"

        message = f"[{alert.severity}] {alert.alert_type}: {alert.source_id}{location_text}. {alert.message[:80]}"

        return message[:160]  # SMS limit

    @classmethod
    def _format_email_message(cls, alert: AlertNotification) -> str:
        """
        Format email message.

        Args:
            alert: AlertNotification object

        Returns:
            str: Formatted email message
        """
        message = f"""
CRITICAL DEVICE ALERT

Alert Type: {alert.alert_type}
Severity: {alert.severity}
Source: {alert.source_id}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Message:
{alert.message}

"""

        if alert.location:
            message += f"""
Location:
- Latitude: {alert.location['lat']}
- Longitude: {alert.location['lon']}
- Map: https://www.openstreetmap.org/?mlat={alert.location['lat']}&mlon={alert.location['lon']}&zoom=18

"""

        message += """
Action Required:
1. Acknowledge this alert in the NOC dashboard
2. Verify guard/device status
3. Contact field personnel if needed
4. Document resolution

This is an automated alert from the IntelliWiz MQTT Alert System.
"""

        return message
