"""
LLM Provider Router - Orchestration with Fallback

Routes requests to primary provider with automatic fallback on failure.
Integrates circuit breaker and feature flags.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Resilience through fallback chains

Sprint 7-8 Phase 4: Routing & Fallback
"""

import logging
from typing import List
from apps.core_onboarding.services.llm.base import MakerLLM, CheckerLLM
from apps.core_onboarding.services.llm.providers import get_provider, PROVIDER_REGISTRY
from apps.core_onboarding.services.llm.circuit_breaker import CircuitBreaker
from apps.core_onboarding.services.llm.exceptions import (
    AllProvidersFailedError,
    CircuitBreakerOpenError,
    LLMProviderError
)

logger = logging.getLogger(__name__)


class LLMProviderRouter:
    """
    Routes LLM requests to providers with automatic fallback.

    Features:
    - Circuit breaker integration
    - Feature flag-based provider selection
    - Automatic fallback chain
    - Comprehensive logging
    """

    def __init__(self, tenant_id: int):
        """
        Initialize router for tenant.

        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self.fallback_chain = self._build_fallback_chain()

    def _build_fallback_chain(self) -> List[str]:
        """
        Build provider fallback chain from feature flags.

        Returns:
            List of provider names in priority order

        TODO Sprint 7-8 Phase 4.2: Integrate with FeatureFlag model
        """
        # For now, use default chain from settings
        from django.conf import settings
        default_chain = getattr(settings, 'LLM_DEFAULT_FALLBACK_CHAIN', ['openai', 'anthropic', 'gemini'])

        # Filter to only enabled providers
        enabled_providers = getattr(settings, 'LLM_PROVIDERS_ENABLED', {})
        enabled_chain = [p for p in default_chain if enabled_providers.get(p, False)]

        if not enabled_chain:
            logger.warning("No LLM providers enabled, using default: openai")
            return ['openai']

        return enabled_chain

    def get_maker_llm(self) -> MakerLLM:
        """
        Get maker LLM with fallback.

        Returns:
            MakerLLM instance from first available provider

        Raises:
            AllProvidersFailedError: If all providers unavailable
        """
        attempted = []

        for provider_name in self.fallback_chain:
            attempted.append(provider_name)

            try:
                # Check circuit breaker
                circuit = CircuitBreaker(provider_name, self.tenant_id)
                if circuit.is_open():
                    logger.warning(f"Skipping {provider_name} - circuit breaker open")
                    continue

                # Get provider via circuit breaker
                maker_llm = circuit.call(get_provider, provider_name, 'maker', self.tenant_id)

                logger.info(f"Using {provider_name} maker LLM for tenant {self.tenant_id}")
                return maker_llm

            except CircuitBreakerOpenError:
                logger.warning(f"Circuit open for {provider_name}, trying next provider")
                continue
            except LLMProviderError as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                continue

        # All providers failed
        raise AllProvidersFailedError(attempted)

    def get_checker_llm(self) -> CheckerLLM:
        """
        Get checker LLM with fallback.

        Returns:
            CheckerLLM instance from first available provider

        Raises:
            AllProvidersFailedError: If all providers unavailable
        """
        attempted = []

        for provider_name in self.fallback_chain:
            attempted.append(provider_name)

            try:
                circuit = CircuitBreaker(provider_name, self.tenant_id)
                if circuit.is_open():
                    logger.warning(f"Skipping {provider_name} - circuit breaker open")
                    continue

                checker_llm = circuit.call(get_provider, provider_name, 'checker', self.tenant_id)

                logger.info(f"Using {provider_name} checker LLM for tenant {self.tenant_id}")
                return checker_llm

            except (CircuitBreakerOpenError, LLMProviderError) as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                continue

        raise AllProvidersFailedError(attempted)


# Convenience function
def get_llm_router(tenant_id: int) -> LLMProviderRouter:
    """Get LLM provider router for tenant."""
    return LLMProviderRouter(tenant_id)
