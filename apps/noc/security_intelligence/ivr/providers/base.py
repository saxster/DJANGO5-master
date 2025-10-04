"""
Base IVR Provider.

Abstract base class for all IVR providers.
Defines common interface for Twilio, Google Voice, SMS, etc.

Follows .claude/rules.md:
- Rule #7: Class < 150 lines
- Rule #8: Methods < 30 lines
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('noc.security_intelligence.ivr')


class BaseIVRProvider(ABC):
    """Abstract base class for IVR providers."""

    def __init__(self, config):
        """
        Initialize provider with configuration.

        Args:
            config: IVRProviderConfig instance
        """
        self.config = config
        self.provider_name = config.provider_type

    @abstractmethod
    def make_call(self, phone_number: str, script_text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initiate outbound call.

        Args:
            phone_number: Phone number to call
            script_text: Voice script to play
            metadata: Additional call metadata

        Returns:
            {
                'success': bool,
                'call_sid': str,
                'status': str,
                'error': str | None
            }
        """
        pass

    @abstractmethod
    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """
        Get current call status.

        Args:
            call_sid: Call identifier

        Returns:
            {
                'call_sid': str,
                'status': str,
                'duration': int,
                'answered': bool,
                'cost': Decimal,
            }
        """
        pass

    @abstractmethod
    def gather_input(self, call_sid: str, prompt: str, options: Dict[str, str]) -> Dict[str, Any]:
        """
        Gather DTMF or voice input.

        Args:
            call_sid: Call identifier
            prompt: Prompt text
            options: Expected response options

        Returns:
            {
                'success': bool,
                'input_type': 'dtmf' | 'voice',
                'input_value': str,
                'confidence': float,
            }
        """
        pass

    @abstractmethod
    def hangup_call(self, call_sid: str) -> bool:
        """
        Terminate call.

        Args:
            call_sid: Call identifier

        Returns:
            bool: Success status
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate provider configuration.

        Returns:
            bool: True if config is valid
        """
        pass

    def mask_phone_number(self, phone: str) -> str:
        """
        Mask phone number for logging.

        Args:
            phone: Full phone number

        Returns:
            str: Masked phone (e.g., "****1234")
        """
        if not phone or len(phone) < 4:
            return "****"
        return "*" * (len(phone) - 4) + phone[-4:]

    def calculate_cost(self, duration_seconds: int) -> Decimal:
        """
        Calculate call cost.

        Args:
            duration_seconds: Call duration

        Returns:
            Decimal: Cost in rupees
        """
        if self.config.cost_per_minute > 0:
            minutes = Decimal(duration_seconds) / Decimal(60)
            return minutes * self.config.cost_per_minute
        return self.config.cost_per_call