"""
SMS Provider.

SMS fallback for failed voice calls or low-priority verifications.
Much cheaper than voice calls (~₹0.50 vs ₹2.50).

Follows .claude/rules.md:
- Rule #7: Class < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
import uuid
from decimal import Decimal
from typing import Dict, Any
from .base import BaseIVRProvider
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger('noc.security_intelligence.ivr')


class SMSProvider(BaseIVRProvider):
    """SMS fallback provider."""

    def __init__(self, config):
        """Initialize SMS client (uses Twilio SMS)."""
        super().__init__(config)
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize SMS client (Twilio)."""
        try:
            from twilio.rest import Client

            account_sid = self.config.credentials.get('account_sid')
            auth_token = self.config.credentials.get('auth_token')

            if not account_sid or not auth_token:
                logger.error("SMS credentials not configured")
                return

            self.client = Client(account_sid, auth_token)
            logger.info("SMS client initialized successfully")

        except ImportError:
            logger.warning("twilio package not installed")
            self.client = None
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"SMS initialization error: {e}", exc_info=True)
            self.client = None

    def make_call(self, phone_number: str, script_text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send SMS message (not a voice call).

        Args:
            phone_number: Phone number
            script_text: Message text
            metadata: Additional data

        Returns:
            dict: Send result
        """
        if not self.client:
            return {'success': False, 'error': 'SMS client not initialized'}

        try:
            from_number = self.config.credentials.get('from_number')

            message_body = self._format_sms_message(script_text, metadata)

            message = self.client.messages.create(
                to=phone_number,
                from_=from_number,
                body=message_body,
                status_callback=metadata.get('callback_url', '')
            )

            return {
                'success': True,
                'call_sid': message.sid,
                'status': 'SENT',
                'error': None
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"SMS send error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _format_sms_message(self, script_text, metadata):
        """Format SMS message from script."""
        max_length = 160
        message = script_text[:max_length]

        response_code = metadata.get('verification_code', '1234')
        message += f"\n\nReply with {response_code} to confirm."

        return message

    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """Get SMS delivery status."""
        if not self.client:
            return {'status': 'UNKNOWN', 'error': 'Client not initialized'}

        try:
            message = self.client.messages(call_sid).fetch()

            return {
                'call_sid': message.sid,
                'status': message.status.upper(),
                'duration': 0,
                'answered': message.status in ['delivered', 'sent'],
                'cost': Decimal('0.50'),
            }

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"SMS status error: {e}", exc_info=True)
            return {'status': 'ERROR', 'error': str(e)}

    def gather_input(self, call_sid: str, prompt: str, options: Dict[str, str]) -> Dict[str, Any]:
        """SMS input gathering (via reply message)."""
        return {
            'success': True,
            'message': 'SMS response handled via webhook'
        }

    def hangup_call(self, call_sid: str) -> bool:
        """Not applicable for SMS."""
        return True

    def validate_config(self) -> bool:
        """Validate SMS configuration."""
        required = ['account_sid', 'auth_token', 'from_number']
        return all(self.config.credentials.get(k) for k in required)