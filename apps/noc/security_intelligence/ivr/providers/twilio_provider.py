"""
Twilio IVR Provider.

Integrates with Twilio Voice API for automated guard verification calls.
Handles call initiation, DTMF gathering, and status tracking.

Follows .claude/rules.md:
- Rule #7: Class < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from decimal import Decimal
from typing import Dict, Any
from .base import BaseIVRProvider
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger('noc.security_intelligence.ivr')


class TwilioProvider(BaseIVRProvider):
    """Twilio voice call provider."""

    def __init__(self, config):
        """Initialize Twilio client."""
        super().__init__(config)
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Twilio client."""
        try:
            from twilio.rest import Client

            account_sid = self.config.credentials.get('account_sid')
            auth_token = self.config.credentials.get('auth_token')

            if not account_sid or not auth_token:
                logger.error("Twilio credentials not configured")
                return

            self.client = Client(account_sid, auth_token)
            logger.info("Twilio client initialized successfully")

        except ImportError:
            logger.warning("twilio package not installed")
            self.client = None
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Twilio initialization error: {e}", exc_info=True)
            self.client = None

    def make_call(self, phone_number: str, script_text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Make outbound call via Twilio."""
        if not self.client:
            return {'success': False, 'error': 'Twilio client not initialized'}

        try:
            from_number = self.config.credentials.get('from_number')
            callback_url = metadata.get('callback_url', '')

            call = self.client.calls.create(
                to=phone_number,
                from_=from_number,
                url=metadata.get('twiml_url', ''),
                status_callback=callback_url,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                timeout=30,
                record=metadata.get('record', False)
            )

            return {
                'success': True,
                'call_sid': call.sid,
                'status': call.status,
                'error': None
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Twilio call error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """Get call status from Twilio."""
        if not self.client:
            return {'status': 'UNKNOWN', 'error': 'Client not initialized'}

        try:
            call = self.client.calls(call_sid).fetch()

            return {
                'call_sid': call.sid,
                'status': call.status.upper(),
                'duration': int(call.duration or 0),
                'answered': call.status in ['in-progress', 'completed'],
                'cost': Decimal(str(call.price or '0.00')).copy_abs(),
            }

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Twilio status fetch error: {e}", exc_info=True)
            return {'status': 'ERROR', 'error': str(e)}

    def gather_input(self, call_sid: str, prompt: str, options: Dict[str, str]) -> Dict[str, Any]:
        """Gather DTMF input (handled via TwiML in webhook)."""
        return {
            'success': True,
            'message': 'DTMF gathering handled via webhook'
        }

    def hangup_call(self, call_sid: str) -> bool:
        """Hangup active call."""
        if not self.client:
            return False

        try:
            self.client.calls(call_sid).update(status='completed')
            return True
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Twilio hangup error: {e}", exc_info=True)
            return False

    def validate_config(self) -> bool:
        """Validate Twilio configuration."""
        required = ['account_sid', 'auth_token', 'from_number']
        return all(self.config.credentials.get(k) for k in required)