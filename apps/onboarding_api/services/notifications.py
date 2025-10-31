"""
Webhook notification service for onboarding approvals and escalations.

Provides external notifications to Slack, Discord, email, and custom webhooks
for important approval events and escalations.
"""
import hashlib
import hmac
import json
import logging
import requests
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class NotificationEvent:
    """Represents a notification event"""
    event_type: str  # approval_pending, approval_granted, approval_rejected, escalation_created
    event_id: str
    title: str
    message: str
    priority: str  # low, medium, high, critical
    metadata: Dict[str, Any]
    timestamp: datetime
    correlation_id: Optional[str] = None


@dataclass
class NotificationResult:
    """Result from sending a notification"""
    success: bool
    provider: str
    latency_ms: int
    error_message: Optional[str] = None
    external_id: Optional[str] = None  # ID from external service


class NotificationProvider(ABC):
    """Abstract base class for notification providers"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    def send_notification(self, event: NotificationEvent) -> NotificationResult:
        """Send notification for an event"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate provider configuration"""
        pass


class SlackNotificationProvider(NotificationProvider):
    """Slack webhook notification provider"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.webhook_url = config.get('webhook_url', '')
        self.channel = config.get('channel', '#onboarding-alerts')
        self.username = config.get('username', 'IntelliWiz AI')
        self.timeout = config.get('timeout_seconds', 10)

    def send_notification(self, event: NotificationEvent) -> NotificationResult:
        """Send notification to Slack"""
        start_time = time.time()

        try:
            # Format Slack message
            color = self._get_color_for_priority(event.priority)
            slack_payload = {
                "channel": self.channel,
                "username": self.username,
                "icon_emoji": ":robot_face:",
                "attachments": [
                    {
                        "color": color,
                        "title": event.title,
                        "text": event.message,
                        "fields": self._format_metadata_fields(event.metadata),
                        "footer": "IntelliWiz Conversational Onboarding",
                        "ts": int(event.timestamp.timestamp())
                    }
                ]
            }

            # Add action buttons for approval events
            if event.event_type in ['approval_pending', 'escalation_created']:
                slack_payload["attachments"][0]["actions"] = self._create_action_buttons(event)

            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=slack_payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            latency_ms = int((time.time() - start_time) * 1000)

            return NotificationResult(
                success=True,
                provider=self.name,
                latency_ms=latency_ms,
                external_id=response.headers.get('x-slack-req-id')
            )

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Slack notification failed: {str(e)}")
            return NotificationResult(
                success=False,
                provider=self.name,
                latency_ms=latency_ms,
                error_message=str(e)
            )

    def validate_config(self) -> bool:
        """Test Slack webhook configuration"""
        try:
            test_payload = {
                "channel": self.channel,
                "username": self.username,
                "text": "Configuration test from IntelliWiz",
                "icon_emoji": ":white_check_mark:"
            }

            response = requests.post(
                self.webhook_url,
                json=test_payload,
                timeout=5
            )
            return response.status_code == 200

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            logger.warning(f"Slack config validation failed: {str(e)}")
            return False

    def _get_color_for_priority(self, priority: str) -> str:
        """Get Slack color for event priority"""
        color_map = {
            'low': '#36a64f',      # green
            'medium': '#ffaa00',   # yellow
            'high': '#ff6600',     # orange
            'critical': '#ff0000'  # red
        }
        return color_map.get(priority, '#808080')  # gray default

    def _format_metadata_fields(self, metadata: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format metadata for Slack fields"""
        fields = []

        # Common fields
        important_fields = ['session_id', 'changeset_id', 'user_email', 'client_name', 'approval_level', 'risk_score']

        for field in important_fields:
            if field in metadata and metadata[field] is not None:
                # Format field name nicely
                field_name = field.replace('_', ' ').title()
                field_value = str(metadata[field])

                # Special formatting for specific fields
                if field == 'risk_score':
                    field_value = f"{float(field_value):.1%}"
                elif field.endswith('_id'):
                    field_value = f"`{field_value}`"  # Monospace for IDs

                fields.append({
                    "title": field_name,
                    "value": field_value,
                    "short": True
                })

        return fields

    def _create_action_buttons(self, event: NotificationEvent) -> List[Dict[str, Any]]:
        """Create action buttons for interactive Slack messages"""
        actions = []

        if event.event_type == 'approval_pending':
            # Get the URLs from metadata
            approval_url = event.metadata.get('approval_url', '')
            if approval_url:
                actions.extend([
                    {
                        "type": "button",
                        "text": "✅ Approve",
                        "style": "primary",
                        "url": f"{approval_url}?action=approve"
                    },
                    {
                        "type": "button",
                        "text": "❌ Reject",
                        "style": "danger",
                        "url": f"{approval_url}?action=reject"
                    },
                    {
                        "type": "button",
                        "text": "⬆️ Escalate",
                        "url": f"{approval_url}?action=escalate"
                    }
                ])

        elif event.event_type == 'escalation_created':
            escalation_url = event.metadata.get('escalation_url', '')
            if escalation_url:
                actions.append({
                    "type": "button",
                    "text": "🔍 Review Escalation",
                    "style": "primary",
                    "url": escalation_url
                })

        return actions


class DiscordNotificationProvider(NotificationProvider):
    """Discord webhook notification provider"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.webhook_url = config.get('webhook_url', '')
        self.username = config.get('username', 'IntelliWiz AI')
        self.timeout = config.get('timeout_seconds', 10)

    def send_notification(self, event: NotificationEvent) -> NotificationResult:
        """Send notification to Discord"""
        start_time = time.time()

        try:
            # Format Discord embed
            color = self._get_color_for_priority(event.priority)
            discord_payload = {
                "username": self.username,
                "embeds": [
                    {
                        "title": event.title,
                        "description": event.message,
                        "color": color,
                        "fields": self._format_metadata_fields(event.metadata),
                        "footer": {
                            "text": "IntelliWiz Conversational Onboarding"
                        },
                        "timestamp": event.timestamp.isoformat()
                    }
                ]
            }

            # Send to Discord
            response = requests.post(
                self.webhook_url,
                json=discord_payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            latency_ms = int((time.time() - start_time) * 1000)

            return NotificationResult(
                success=True,
                provider=self.name,
                latency_ms=latency_ms
            )

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Discord notification failed: {str(e)}")
            return NotificationResult(
                success=False,
                provider=self.name,
                latency_ms=latency_ms,
                error_message=str(e)
            )

    def validate_config(self) -> bool:
        """Test Discord webhook configuration"""
        try:
            test_payload = {
                "username": self.username,
                "content": "Configuration test from IntelliWiz ✅"
            }

            response = requests.post(
                self.webhook_url,
                json=test_payload,
                timeout=5
            )
            return response.status_code in [200, 204]

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            logger.warning(f"Discord config validation failed: {str(e)}")
            return False

    def _get_color_for_priority(self, priority: str) -> int:
        """Get Discord color for event priority"""
        color_map = {
            'low': 0x36a64f,      # green
            'medium': 0xffaa00,   # yellow
            'high': 0xff6600,     # orange
            'critical': 0xff0000  # red
        }
        return color_map.get(priority, 0x808080)  # gray default

    def _format_metadata_fields(self, metadata: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format metadata for Discord embed fields"""
        fields = []

        important_fields = ['session_id', 'changeset_id', 'user_email', 'client_name', 'approval_level', 'risk_score']

        for field in important_fields:
            if field in metadata and metadata[field] is not None:
                field_name = field.replace('_', ' ').title()
                field_value = str(metadata[field])

                if field == 'risk_score':
                    field_value = f"{float(field_value):.1%}"
                elif field.endswith('_id'):
                    field_value = f"`{field_value}`"

                fields.append({
                    "name": field_name,
                    "value": field_value,
                    "inline": True
                })

        return fields


class EmailNotificationProvider(NotificationProvider):
    """Email notification provider"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.recipients = config.get('recipients', [])
        self.from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
        self.template_dir = config.get('template_dir', 'onboarding/notifications/')

    def send_notification(self, event: NotificationEvent) -> NotificationResult:
        """Send email notification"""
        start_time = time.time()

        try:
            # Format email subject and body
            subject = self._format_subject(event)

            # Try to render HTML template first
            try:
                html_content = render_to_string(
                    f"{self.template_dir}{event.event_type}.html",
                    {'event': event, 'metadata': event.metadata}
                )
            except (ValueError, TypeError, AttributeError) as e:
                html_content = None

            # Render plain text template
            try:
                text_content = render_to_string(
                    f"{self.template_dir}{event.event_type}.txt",
                    {'event': event, 'metadata': event.metadata}
                )
            except (ValueError, TypeError, AttributeError) as e:
                # Fallback to simple text formatting
                text_content = self._format_plain_text(event)

            # Send email
            from django.core.mail import EmailMultiAlternatives

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=self.recipients
            )

            if html_content:
                email.attach_alternative(html_content, "text/html")

            sent_count = email.send()

            latency_ms = int((time.time() - start_time) * 1000)

            return NotificationResult(
                success=sent_count > 0,
                provider=self.name,
                latency_ms=latency_ms,
                external_id=f"sent_to_{len(self.recipients)}_recipients"
            )

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Email notification failed: {str(e)}")
            return NotificationResult(
                success=False,
                provider=self.name,
                latency_ms=latency_ms,
                error_message=str(e)
            )

    def validate_config(self) -> bool:
        """Test email configuration"""
        try:
            # Check if we have recipients
            if not self.recipients:
                return False

            # Try to send a test email (but don't actually send it)
            from django.core.mail import get_connection
            connection = get_connection()
            return connection is not None

        except (TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout):
            return False

    def _format_subject(self, event: NotificationEvent) -> str:
        """Format email subject"""
        priority_prefix = ""
        if event.priority in ['high', 'critical']:
            priority_prefix = f"[{event.priority.upper()}] "

        return f"{priority_prefix}IntelliWiz: {event.title}"

    def _format_plain_text(self, event: NotificationEvent) -> str:
        """Format plain text email content"""
        lines = [
            f"IntelliWiz Conversational Onboarding Alert",
            f"{'=' * 50}",
            f"",
            f"Event: {event.title}",
            f"Type: {event.event_type}",
            f"Priority: {event.priority.upper()}",
            f"Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"",
            f"Message:",
            event.message,
            f"",
            f"Additional Details:",
        ]

        # Add metadata
        for key, value in event.metadata.items():
            if value is not None:
                field_name = key.replace('_', ' ').title()
                lines.append(f"- {field_name}: {value}")

        lines.extend([
            f"",
            f"Event ID: {event.event_id}",
            f"Correlation ID: {event.correlation_id or 'N/A'}",
            f"",
            f"--",
            f"This is an automated notification from IntelliWiz AI."
        ])

        return "\n".join(lines)


class CustomWebhookProvider(NotificationProvider):
    """Custom webhook provider for integrations"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.webhook_url = config.get('webhook_url', '')
        self.secret = config.get('secret', '')
        self.timeout = config.get('timeout_seconds', 10)
        self.headers = config.get('headers', {})
        self.auth_header = config.get('auth_header', '')

    def send_notification(self, event: NotificationEvent) -> NotificationResult:
        """Send notification to custom webhook"""
        start_time = time.time()

        try:
            # Create webhook payload
            payload = {
                "event_type": event.event_type,
                "event_id": event.event_id,
                "title": event.title,
                "message": event.message,
                "priority": event.priority,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id,
                "metadata": event.metadata,
                "source": "intelliwiz_onboarding"
            }

            # Prepare headers
            headers = {'Content-Type': 'application/json'}
            headers.update(self.headers)

            # Add authentication if configured
            if self.auth_header:
                headers['Authorization'] = self.auth_header

            # Add HMAC signature if secret is configured
            if self.secret:
                payload_json = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    self.secret.encode(),
                    payload_json.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers['X-IntelliWiz-Signature'] = f"sha256={signature}"

            # Send webhook
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            latency_ms = int((time.time() - start_time) * 1000)

            return NotificationResult(
                success=True,
                provider=self.name,
                latency_ms=latency_ms,
                external_id=response.headers.get('x-request-id', response.headers.get('request-id'))
            )

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Custom webhook notification failed: {str(e)}")
            return NotificationResult(
                success=False,
                provider=self.name,
                latency_ms=latency_ms,
                error_message=str(e)
            )

    def validate_config(self) -> bool:
        """Test custom webhook configuration"""
        try:
            # Send a test ping
            test_payload = {
                "event_type": "config_test",
                "message": "Configuration test from IntelliWiz",
                "timestamp": timezone.now().isoformat(),
                "source": "intelliwiz_onboarding"
            }

            headers = {'Content-Type': 'application/json'}
            headers.update(self.headers)

            if self.auth_header:
                headers['Authorization'] = self.auth_header

            response = requests.post(
                self.webhook_url,
                json=test_payload,
                headers=headers,
                timeout=5
            )
            return response.status_code in [200, 201, 202, 204]

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            logger.warning(f"Custom webhook config validation failed: {str(e)}")
            return False


class NotificationService:
    """
    Central notification service that manages multiple providers
    and handles notification routing and delivery.
    """

    def __init__(self):
        self.providers: Dict[str, NotificationProvider] = {}
        self.event_routing: Dict[str, List[str]] = {}
        self._initialize_providers()
        self._configure_routing()

    def _initialize_providers(self):
        """Initialize notification providers from Django settings"""
        provider_configs = getattr(settings, 'NOTIFICATION_PROVIDERS', {})

        for provider_name, config in provider_configs.items():
            try:
                provider_type = config.get('type', '')

                if provider_type == 'slack':
                    provider = SlackNotificationProvider(provider_name, config)
                elif provider_type == 'discord':
                    provider = DiscordNotificationProvider(provider_name, config)
                elif provider_type == 'email':
                    provider = EmailNotificationProvider(provider_name, config)
                elif provider_type == 'webhook':
                    provider = CustomWebhookProvider(provider_name, config)
                else:
                    logger.warning(f"Unknown notification provider type: {provider_type}")
                    continue

                # Validate configuration
                if provider.validate_config():
                    self.providers[provider_name] = provider
                    logger.info(f"Initialized notification provider: {provider_name}")
                else:
                    logger.warning(f"Failed to validate provider config: {provider_name}")

            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
                logger.error(f"Failed to initialize notification provider {provider_name}: {str(e)}")

    def _configure_routing(self):
        """Configure which providers should handle which events"""
        routing_config = getattr(settings, 'NOTIFICATION_ROUTING', {})

        # Default routing
        self.event_routing = {
            'approval_pending': ['slack', 'email'],
            'approval_granted': ['slack'],
            'approval_rejected': ['slack', 'email'],
            'escalation_created': ['slack', 'discord', 'email'],
            'changeset_applied': ['slack'],
            'changeset_rollback': ['slack', 'email'],
            'system_error': ['email', 'webhook_alerts']
        }

        # Override with configuration
        self.event_routing.update(routing_config)

    def send_notification(self, event: NotificationEvent) -> Dict[str, NotificationResult]:
        """
        Send notification to appropriate providers based on event type

        Args:
            event: Notification event to send

        Returns:
            Dict mapping provider names to their notification results
        """
        # Get providers for this event type
        provider_names = self.event_routing.get(event.event_type, [])
        results = {}

        if not provider_names:
            logger.warning(f"No providers configured for event type: {event.event_type}")
            return results

        # Send to each configured provider
        for provider_name in provider_names:
            if provider_name not in self.providers:
                logger.warning(f"Provider {provider_name} not available for event {event.event_type}")
                continue

            try:
                provider = self.providers[provider_name]
                result = provider.send_notification(event)
                results[provider_name] = result

                if result.success:
                    logger.info(f"Notification sent via {provider_name} for {event.event_type}")
                else:
                    logger.error(f"Notification failed via {provider_name}: {result.error_message}")

            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
                logger.error(f"Exception sending notification via {provider_name}: {str(e)}")
                results[provider_name] = NotificationResult(
                    success=False,
                    provider=provider_name,
                    latency_ms=0,
                    error_message=str(e)
                )

        return results

    def send_approval_pending_notification(
        self,
        session_id: str,
        changeset_id: str,
        approver_email: str,
        client_name: str,
        approval_level: str,
        risk_score: float,
        changes_count: int,
        approval_url: str
    ):
        """Send notification for pending approval"""
        event = NotificationEvent(
            event_type='approval_pending',
            event_id=f"approval_pending_{changeset_id}",
            title=f"🔍 AI Recommendation Approval Required",
            message=f"A {approval_level} approval is required for AI recommendations affecting {client_name}. "
                   f"Risk score: {risk_score:.1%}, Changes: {changes_count}",
            priority='high' if risk_score > 0.7 else 'medium',
            metadata={
                'session_id': session_id,
                'changeset_id': changeset_id,
                'user_email': approver_email,
                'client_name': client_name,
                'approval_level': approval_level,
                'risk_score': risk_score,
                'changes_count': changes_count,
                'approval_url': approval_url
            },
            timestamp=timezone.now(),
            correlation_id=session_id
        )

        return self.send_notification(event)

    def send_escalation_notification(
        self,
        session_id: str,
        changeset_id: str,
        escalated_by_email: str,
        escalation_reason: str,
        ticket_number: str,
        client_name: str,
        escalation_url: str
    ):
        """Send notification for escalated approval"""
        event = NotificationEvent(
            event_type='escalation_created',
            event_id=f"escalation_{changeset_id}",
            title=f"⬆️ AI Recommendation Escalated",
            message=f"AI recommendation approval has been escalated by {escalated_by_email}. "
                   f"Ticket: {ticket_number}. Reason: {escalation_reason}",
            priority='critical',
            metadata={
                'session_id': session_id,
                'changeset_id': changeset_id,
                'escalated_by': escalated_by_email,
                'escalation_reason': escalation_reason,
                'ticket_number': ticket_number,
                'client_name': client_name,
                'escalation_url': escalation_url
            },
            timestamp=timezone.now(),
            correlation_id=session_id
        )

        return self.send_notification(event)

    def send_changeset_applied_notification(
        self,
        session_id: str,
        changeset_id: str,
        applied_by_email: str,
        client_name: str,
        changes_applied: int,
        rollback_available: bool
    ):
        """Send notification when changeset is successfully applied"""
        event = NotificationEvent(
            event_type='changeset_applied',
            event_id=f"applied_{changeset_id}",
            title=f"✅ AI Recommendations Applied",
            message=f"AI recommendations have been successfully applied to {client_name} by {applied_by_email}. "
                   f"{changes_applied} changes applied. Rollback {'available' if rollback_available else 'not available'}.",
            priority='medium',
            metadata={
                'session_id': session_id,
                'changeset_id': changeset_id,
                'applied_by': applied_by_email,
                'client_name': client_name,
                'changes_applied': changes_applied,
                'rollback_available': rollback_available
            },
            timestamp=timezone.now(),
            correlation_id=session_id
        )

        return self.send_notification(event)

    def send_rollback_notification(
        self,
        changeset_id: str,
        rolled_back_by_email: str,
        rollback_reason: str,
        client_name: str,
        changes_rolled_back: int
    ):
        """Send notification when changeset is rolled back"""
        event = NotificationEvent(
            event_type='changeset_rollback',
            event_id=f"rollback_{changeset_id}",
            title=f"↩️ AI Changeset Rolled Back",
            message=f"AI changeset has been rolled back by {rolled_back_by_email}. "
                   f"Reason: {rollback_reason}. {changes_rolled_back} changes rolled back.",
            priority='high',
            metadata={
                'changeset_id': changeset_id,
                'rolled_back_by': rolled_back_by_email,
                'rollback_reason': rollback_reason,
                'client_name': client_name,
                'changes_rolled_back': changes_rolled_back
            },
            timestamp=timezone.now()
        )

        return self.send_notification(event)

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all notification providers"""
        status = {}

        for name, provider in self.providers.items():
            try:
                is_healthy = provider.validate_config()
                status[name] = {
                    'available': is_healthy,
                    'type': provider.config.get('type', 'unknown'),
                    'last_check': timezone.now().isoformat()
                }
            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
                status[name] = {
                    'available': False,
                    'error': str(e),
                    'last_check': timezone.now().isoformat()
                }

        return status

    def test_all_providers(self) -> Dict[str, bool]:
        """Test all providers and return results"""
        results = {}
        for name, provider in self.providers.items():
            try:
                results[name] = provider.validate_config()
            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, requests.ConnectionError, requests.RequestException, requests.Timeout):
                results[name] = False
        return results


# Singleton instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get singleton instance of notification service"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# Convenience functions for common notification patterns
def notify_approval_pending(session_id: str, changeset_id: str, approver_email: str,
                          client_name: str, approval_level: str, risk_score: float,
                          changes_count: int, approval_url: str) -> Dict[str, NotificationResult]:
    """Send approval pending notification"""
    service = get_notification_service()
    return service.send_approval_pending_notification(
        session_id, changeset_id, approver_email, client_name,
        approval_level, risk_score, changes_count, approval_url
    )


def notify_escalation_created(session_id: str, changeset_id: str, escalated_by_email: str,
                            escalation_reason: str, ticket_number: str, client_name: str,
                            escalation_url: str) -> Dict[str, NotificationResult]:
    """Send escalation notification"""
    service = get_notification_service()
    return service.send_escalation_notification(
        session_id, changeset_id, escalated_by_email, escalation_reason,
        ticket_number, client_name, escalation_url
    )


def notify_changeset_applied(session_id: str, changeset_id: str, applied_by_email: str,
                           client_name: str, changes_applied: int, rollback_available: bool) -> Dict[str, NotificationResult]:
    """Send changeset applied notification"""
    service = get_notification_service()
    return service.send_changeset_applied_notification(
        session_id, changeset_id, applied_by_email, client_name,
        changes_applied, rollback_available
    )


def notify_rollback_performed(changeset_id: str, rolled_back_by_email: str, rollback_reason: str,
                            client_name: str, changes_rolled_back: int) -> Dict[str, NotificationResult]:
    """Send rollback notification"""
    service = get_notification_service()
    return service.send_rollback_notification(
        changeset_id, rolled_back_by_email, rollback_reason,
        client_name, changes_rolled_back
    )