"""
Google Gemini Provider for LLM Router

Primary LLM provider with automatic fallback to Claude.
Uses Gemini 1.5 Pro for complex reasoning and Gemini 1.5 Flash for validation.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Integration with existing LLM router infrastructure

Sprint Dashboard Agent Intelligence - Phase 0.2
"""

import logging
import json
from typing import Dict, Any, Optional

# Graceful import handling
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False

from apps.onboarding_api.services.llm.base import MakerLLM, CheckerLLM
from apps.onboarding_api.services.llm.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class GeminiMakerLLM(MakerLLM):
    """
    Google Gemini Maker LLM implementation.

    Uses Gemini 1.5 Pro for complex reasoning tasks like:
    - Task prioritization
    - Route optimization
    - Decision-making
    - Summarization
    """

    def __init__(self, tenant_id: int, api_key: str):
        """
        Initialize Gemini Maker LLM.

        Args:
            tenant_id: Tenant identifier
            api_key: Google AI API key

        Raises:
            LLMProviderError: If Gemini not available or initialization fails
        """
        super().__init__(tenant_id, api_key)

        if not GEMINI_AVAILABLE:
            raise LLMProviderError(
                "Google Gemini not available. Install: pip install google-generativeai>=0.8.3"
            )

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
            self.provider_name = 'gemini'
            logger.info(f"Initialized Gemini Maker LLM for tenant {tenant_id}")
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to initialize Gemini: {e}", exc_info=True)
            raise LLMProviderError(f"Gemini initialization failed: {str(e)}")

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Gemini 1.5 Pro.

        Args:
            prompt: Input prompt
            **kwargs: Generation parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text

        Raises:
            LLMProviderError: If generation fails
        """
        try:
            # Build generation config
            config = genai.GenerationConfig(
                temperature=kwargs.get('temperature', 0.7),
                max_output_tokens=kwargs.get('max_tokens', 4096),
                top_p=kwargs.get('top_p', 0.95),
                top_k=kwargs.get('top_k', 40),
            )

            # Generate with safety settings
            response = self.model.generate_content(
                prompt,
                generation_config=config,
                safety_settings={
                    'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_MEDIUM_AND_ABOVE',
                    'HARM_CATEGORY_HARASSMENT': 'BLOCK_MEDIUM_AND_ABOVE',
                    'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_MEDIUM_AND_ABOVE',
                }
            )

            if not response or not response.text:
                raise LLMProviderError("Gemini returned empty response")

            logger.debug(f"Gemini generated {len(response.text)} chars")
            return response.text

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Gemini generation failed: {e}", exc_info=True)
            raise LLMProviderError(f"Gemini generation error: {str(e)}")


class GeminiCheckerLLM(CheckerLLM):
    """
    Google Gemini Checker LLM implementation.

    Uses Gemini 1.5 Flash for fast validation tasks like:
    - Content validation
    - Quality checks
    - Compliance verification
    """

    def __init__(self, tenant_id: int, api_key: str):
        """
        Initialize Gemini Checker LLM.

        Args:
            tenant_id: Tenant identifier
            api_key: Google AI API key

        Raises:
            LLMProviderError: If Gemini not available or initialization fails
        """
        super().__init__(tenant_id, api_key)

        if not GEMINI_AVAILABLE:
            raise LLMProviderError(
                "Google Gemini not available. Install: pip install google-generativeai>=0.8.3"
            )

        try:
            genai.configure(api_key=api_key)
            # Use Flash model for faster validation
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
            self.provider_name = 'gemini'
            logger.info(f"Initialized Gemini Checker LLM (Flash) for tenant {tenant_id}")
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to initialize Gemini Flash: {e}", exc_info=True)
            raise LLMProviderError(f"Gemini Flash initialization failed: {str(e)}")

    def validate(self, content: str, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate content using Gemini 1.5 Flash.

        Args:
            content: Content to validate
            criteria: Validation criteria

        Returns:
            Validation result with is_valid, issues, score

        Raises:
            LLMProviderError: If validation fails
        """
        try:
            prompt = self._build_validation_prompt(content, criteria)

            # Use Flash for speed
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,  # Lower temperature for consistent validation
                    max_output_tokens=2048,
                )
            )

            result = self._parse_validation_response(response.text)
            logger.debug(f"Gemini validation complete: {result.get('is_valid')}")
            return result

        except (ValueError, AttributeError, RuntimeError, json.JSONDecodeError) as e:
            logger.error(f"Gemini validation failed: {e}", exc_info=True)
            raise LLMProviderError(f"Gemini validation error: {str(e)}")
