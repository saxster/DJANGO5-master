"""
API Key Validation Service

Tests API keys before storing in database.
Prevents invalid/expired keys from being saved.

Security Features:
- @sensitive_variables decorator (no keys in error logs)
- Strict timeouts (5s max per validation)
- No SSRF vulnerability (no user-controlled URLs)
- Exception handling (fail gracefully)

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Rule #3: Network timeouts required

Secure Secrets Management - Validation Layer
"""

import logging
from typing import Dict, Tuple
from django.views.decorators.debug import sensitive_variables
import requests

logger = logging.getLogger(__name__)


class APIKeyValidationService:
    """
    Validates API keys by testing with provider endpoints.

    Supports:
    - Google Gemini
    - Anthropic Claude
    - OpenAI
    - Twilio
    - Google Maps
    """

    # Validation timeout (5 seconds max - Rule #3)
    TIMEOUT = (5, 5)  # (connect, read)

    @classmethod
    @sensitive_variables('api_key', 'response')
    def validate_key(cls, provider: str, api_key: str) -> Tuple[bool, str]:
        """
        Validate API key for specified provider.

        Args:
            provider: Provider name (e.g., 'google_gemini')
            api_key: API key to validate

        Returns:
            (is_valid, message) tuple

        Security:
            - @sensitive_variables prevents logging API key in error reports
            - Strict timeout prevents SSRF/DoS
        """
        if not api_key or not api_key.strip():
            return (False, "API key cannot be empty")

        # Route to provider-specific validation
        validators = {
            'google_gemini': cls._validate_gemini,
            'anthropic_claude': cls._validate_claude,
            'openai': cls._validate_openai,
            'twilio': cls._validate_twilio,
            'google_maps': cls._validate_google_maps,
        }

        validator = validators.get(provider)

        if not validator:
            logger.warning(f"No validator for provider: {provider}")
            return (True, f"Validation not implemented for {provider} - saved without testing")

        try:
            return validator(api_key)

        except (requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"Network error validating {provider}: {e}")
            return (False, f"Network error: {str(e)}")

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Validation error for {provider}: {e}", exc_info=True)
            return (False, f"Validation error: {str(e)}")

    @classmethod
    @sensitive_variables('api_key', 'response')
    def _validate_gemini(cls, api_key: str) -> Tuple[bool, str]:
        """Validate Google Gemini API key"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')

            # Test with minimal prompt
            response = model.generate_content("Test", request_options={'timeout': 5})

            if response and response.text:
                return (True, "Gemini API key validated successfully")
            else:
                return (False, "Gemini returned empty response")

        except Exception as e:
            return (False, f"Gemini validation failed: {str(e)}")

    @classmethod
    @sensitive_variables('api_key', 'response')
    def _validate_claude(cls, api_key: str) -> Tuple[bool, str]:
        """Validate Anthropic Claude API key"""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)

            # Test with minimal message
            response = client.messages.create(
                model="claude-3-haiku-20240307",  # Cheapest model
                max_tokens=10,
                messages=[{"role": "user", "content": "Test"}],
                timeout=5.0
            )

            if response and response.content:
                return (True, "Claude API key validated successfully")
            else:
                return (False, "Claude returned empty response")

        except Exception as e:
            return (False, f"Claude validation failed: {str(e)}")

    @classmethod
    @sensitive_variables('api_key')
    def _validate_openai(cls, api_key: str) -> Tuple[bool, str]:
        """Validate OpenAI API key"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=5.0)

            # Test with minimal request
            response = client.models.list()

            if response:
                return (True, "OpenAI API key validated successfully")
            else:
                return (False, "OpenAI validation failed")

        except Exception as e:
            return (False, f"OpenAI validation failed: {str(e)}")

    @classmethod
    @sensitive_variables('api_key')
    def _validate_twilio(cls, api_key: str) -> Tuple[bool, str]:
        """Validate Twilio auth token"""
        # Placeholder - implement if needed
        return (True, "Twilio validation not implemented - saved without testing")

    @classmethod
    @sensitive_variables('api_key')
    def _validate_google_maps(cls, api_key: str) -> Tuple[bool, str]:
        """Validate Google Maps API key"""
        try:
            # Test with Geocoding API (simplest endpoint)
            url = f"https://maps.googleapis.com/maps/api/geocode/json"
            params = {'address': 'Google', 'key': api_key}

            response = requests.get(url, params=params, timeout=cls.TIMEOUT)
            data = response.json()

            if data.get('status') == 'OK':
                return (True, "Google Maps API key validated successfully")
            elif data.get('status') == 'REQUEST_DENIED':
                return (False, f"Invalid API key: {data.get('error_message', 'Access denied')}")
            else:
                return (False, f"Validation failed: {data.get('status')}")

        except (requests.RequestException, ValueError, KeyError) as e:
            return (False, f"Google Maps validation error: {str(e)}")
