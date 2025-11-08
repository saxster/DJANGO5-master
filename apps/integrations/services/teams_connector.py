"""
Microsoft Teams Connector Service.

Sends notifications to Microsoft Teams channels via incoming webhooks.
Supports Adaptive Cards format for rich formatting.

Following CLAUDE.md:
- Rule #15: Network calls with timeouts
- Rule #11: Specific exception handling
"""

import logging
from typing import Dict, Optional
import requests
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

logger = logging.getLogger(__name__)

TEAMS_TIMEOUT = (5, 30)  # (connect, read) seconds


class TeamsConnector:
    """Service for sending notifications to Microsoft Teams."""

    @classmethod
    def send_alert_notification(
        cls,
        webhook_url: str,
        alert_data: Dict
    ) -> Dict:
        """
        Send alert notification to Teams channel.

        Args:
            webhook_url: Teams incoming webhook URL
            alert_data: Alert information

        Returns:
            Result dictionary with success status
        """
        card = cls._build_alert_card(alert_data)
        return cls._send_card(webhook_url, card)

    @classmethod
    def send_sos_notification(
        cls,
        webhook_url: str,
        sos_data: Dict
    ) -> Dict:
        """Send SOS alert notification (high priority)."""
        card = cls._build_sos_card(sos_data)
        return cls._send_card(webhook_url, card)

    @classmethod
    def send_sla_risk_notification(
        cls,
        webhook_url: str,
        ticket_data: Dict
    ) -> Dict:
        """Send SLA breach risk notification."""
        card = cls._build_sla_risk_card(ticket_data)
        return cls._send_card(webhook_url, card)

    @classmethod
    def _send_card(cls, webhook_url: str, card: Dict) -> Dict:
        """
        Send Adaptive Card to Teams webhook.

        Args:
            webhook_url: Teams webhook URL
            card: Adaptive Card JSON

        Returns:
            Result dictionary
        """
        try:
            response = requests.post(
                webhook_url,
                json=card,
                headers={'Content-Type': 'application/json'},
                timeout=TEAMS_TIMEOUT
            )

            response.raise_for_status()

            logger.info(
                "teams_notification_sent",
                extra={
                    'status_code': response.status_code,
                    'card_type': card.get('type')
                }
            )

            return {
                'success': True,
                'status_code': response.status_code
            }

        except NETWORK_EXCEPTIONS as e:
            logger.error(
                "teams_notification_failed",
                extra={'error': str(e)},
                exc_info=True
            )
            return {
                'success': False,
                'error': str(e)
            }

    @classmethod
    def _build_alert_card(cls, alert_data: Dict) -> Dict:
        """Build Adaptive Card for alert notification."""
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"Alert: {alert_data.get('alert_type')}",
            "themeColor": "D70000",  # Red
            "title": f"🚨 {alert_data.get('alert_type')} Alert",
            "sections": [{
                "activityTitle": alert_data.get('description', 'Alert triggered'),
                "facts": [
                    {"name": "Severity", "value": alert_data.get('severity', 'UNKNOWN')},
                    {"name": "Device", "value": alert_data.get('device_id', 'N/A')},
                    {"name": "Site", "value": alert_data.get('site_name', 'N/A')},
                    {"name": "Time", "value": alert_data.get('timestamp', '')}
                ],
                "markdown": True
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "View Alert",
                "targets": [{
                    "os": "default",
                    "uri": alert_data.get('url', '#')
                }]
            }]
        }

    @classmethod
    def _build_sos_card(cls, sos_data: Dict) -> Dict:
        """Build Adaptive Card for SOS alert."""
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": "🆘 SOS ALERT",
            "themeColor": "FF0000",  # Bright red
            "title": "🆘 SOS ALERT - IMMEDIATE ACTION REQUIRED",
            "sections": [{
                "activityTitle": "Guard has triggered SOS alert",
                "facts": [
                    {"name": "Guard", "value": sos_data.get('guard_name', 'Unknown')},
                    {"name": "Location", "value": sos_data.get('location', 'Unknown')},
                    {"name": "Site", "value": sos_data.get('site_name', 'N/A')},
                    {"name": "Time", "value": sos_data.get('timestamp', '')}
                ],
                "markdown": True
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "Respond Now",
                "targets": [{
                    "os": "default",
                    "uri": sos_data.get('url', '#')
                }]
            }]
        }

    @classmethod
    def _build_sla_risk_card(cls, ticket_data: Dict) -> Dict:
        """Build Adaptive Card for SLA risk notification."""
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"SLA Risk: Ticket #{ticket_data.get('ticket_id')}",
            "themeColor": "FF8C00",  # Orange
            "title": "⚠️ SLA Breach Risk Detected",
            "sections": [{
                "activityTitle": ticket_data.get('title', 'Ticket at risk'),
                "facts": [
                    {"name": "Ticket", "value": f"#{ticket_data.get('ticket_id')}"},
                    {"name": "Risk", "value": f"{ticket_data.get('breach_probability', 0) * 100:.1f}%"},
                    {"name": "Time to SLA", "value": ticket_data.get('time_to_sla', 'Unknown')},
                    {"name": "Assigned To", "value": ticket_data.get('assignee', 'Unassigned')}
                ],
                "markdown": True
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "View Ticket",
                "targets": [{
                    "os": "default",
                    "uri": ticket_data.get('url', '#')
                }]
            }]
        }
