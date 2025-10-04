"""
Mock IVR Provider.

Mock provider for testing without real API calls.
Simulates call lifecycle and responses.

Follows .claude/rules.md:
- Rule #7: Class < 150 lines
- Rule #8: Methods < 30 lines
"""

import uuid
import logging
from decimal import Decimal
from typing import Dict, Any
from .base import BaseIVRProvider

logger = logging.getLogger('noc.security_intelligence.ivr')


class MockProvider(BaseIVRProvider):
    """Mock provider for testing."""

    _call_registry = {}

    _config = {
        'will_answer': True,
        'answer_delay_seconds': 2,
        'dtmf_response': '1',
        'call_duration_seconds': 30,
        'will_fail': False,
    }

    @classmethod
    def set_behavior(cls, **kwargs):
        """Configure mock behavior for testing."""
        cls._config.update(kwargs)

    @classmethod
    def reset(cls):
        """Reset mock state."""
        cls._call_registry = {}
        cls._config = {
            'will_answer': True,
            'answer_delay_seconds': 2,
            'dtmf_response': '1',
            'call_duration_seconds': 30,
            'will_fail': False,
        }

    def make_call(self, phone_number: str, script_text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate call initiation."""
        if self._config['will_fail']:
            return {'success': False, 'error': 'Mock failure'}

        call_sid = f"MOCK_{uuid.uuid4().hex[:16]}"

        self._call_registry[call_sid] = {
            'phone': phone_number,
            'script': script_text,
            'status': 'QUEUED',
            'answered': False,
            'duration': 0,
            'response': None,
        }

        return {
            'success': True,
            'call_sid': call_sid,
            'status': 'QUEUED',
            'error': None
        }

    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """Get mock call status."""
        call_data = self._call_registry.get(call_sid, {})

        if not call_data:
            return {'status': 'NOT_FOUND', 'error': 'Call not found'}

        will_answer = self._config['will_answer']
        duration = self._config['call_duration_seconds']

        status = 'COMPLETED' if will_answer else 'NO_ANSWER'
        answered = will_answer

        return {
            'call_sid': call_sid,
            'status': status,
            'duration': duration if answered else 0,
            'answered': answered,
            'cost': Decimal('0.00'),
        }

    def gather_input(self, call_sid: str, prompt: str, options: Dict[str, str]) -> Dict[str, Any]:
        """Simulate DTMF input gathering."""
        return {
            'success': True,
            'input_type': 'dtmf',
            'input_value': self._config['dtmf_response'],
            'confidence': 1.0,
        }

    def hangup_call(self, call_sid: str) -> bool:
        """Simulate call hangup."""
        if call_sid in self._call_registry:
            self._call_registry[call_sid]['status'] = 'COMPLETED'
            return True
        return False

    def validate_config(self) -> bool:
        """Mock provider always valid."""
        return True