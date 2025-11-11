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
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache

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

    TENANT_CHAIN_CACHE_KEY = "llm_provider_chain:{tenant_id}"
    FLAG_CACHE_KEY = "llm_provider_flag:{flag_name}"
    CHAIN_CACHE_TTL = 60

    def __init__(self, tenant_id: int):
        """
        Initialize router for tenant.

        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id

    def _build_fallback_chain(self) -> List[str]:
        """
        Build provider fallback chain from feature flags and tenant overrides.

        Returns:
            List of provider names in priority order
        """
        enabled_providers = self._get_enabled_providers()
        tenant_chain = self._get_tenant_override_chain()
        if tenant_chain:
            chain = tenant_chain
        else:
            chain = self._get_feature_flag_chain() or getattr(
                settings, 'LLM_DEFAULT_FALLBACK_CHAIN', ['openai', 'anthropic', 'gemini']
            )

        filtered_chain = [provider for provider in chain if enabled_providers.get(provider, False)]

        if not filtered_chain:
            filtered_chain = [provider for provider, enabled in enabled_providers.items() if enabled]

        if not filtered_chain:
            logger.warning("No LLM providers enabled, falling back to openai")
            return ['openai']

        return filtered_chain

    def get_maker_llm(self) -> MakerLLM:
        """
        Get maker LLM with fallback.

        Returns:
            MakerLLM instance from first available provider

        Raises:
            AllProvidersFailedError: If all providers unavailable
        """
        attempted = []

        for provider_name in self._get_fallback_chain():
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

        for provider_name in self._get_fallback_chain():
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

    # ------------------------------------------------------------------
    # Chain helpers
    # ------------------------------------------------------------------
    def _get_fallback_chain(self) -> List[str]:
        cache_key = self.TENANT_CHAIN_CACHE_KEY.format(tenant_id=self.tenant_id)
        cached_chain = cache.get(cache_key)
        if cached_chain:
            return cached_chain

        chain = self._build_fallback_chain()
        cache.set(cache_key, chain, self.CHAIN_CACHE_TTL)
        return chain

    def _get_enabled_providers(self) -> dict:
        enabled = getattr(settings, 'LLM_PROVIDERS_ENABLED', {})
        if not enabled:
            # Default to providers known by registry
            enabled = {provider: True for provider in PROVIDER_REGISTRY.keys()}
        return enabled

    def _get_feature_flag_chain(self) -> List[str]:
        metadata_chain = self._fetch_flag_metadata('llm_provider_chain')
        chain = self._extract_chain(metadata_chain)
        if chain:
            return chain

        ordered_providers: List[str] = []
        for flag_name in ('llm_provider_primary', 'llm_provider_secondary', 'llm_provider_tertiary'):
            metadata = self._fetch_flag_metadata(flag_name)
            provider = self._extract_provider_from_metadata(metadata)
            if provider:
                ordered_providers.append(provider)

        return ordered_providers

    def _get_tenant_override_chain(self) -> List[str]:
        metadata = self._fetch_flag_metadata('llm_provider_overrides')
        if metadata:
            overrides = (metadata.get('deployment_metadata') or {}).get('tenants', {})
            tenant_key = str(self.tenant_id)
            tenant_override = overrides.get(tenant_key) or overrides.get(self.tenant_id)
            chain = self._coerce_chain(tenant_override)
            if chain:
                logger.info("Using tenant-specific LLM chain for tenant %s", self.tenant_id)
                return chain

        overrides = getattr(settings, 'LLM_PROVIDER_OVERRIDES', {})
        tenant_override = overrides.get(self.tenant_id) or overrides.get(str(self.tenant_id))
        chain = self._coerce_chain(tenant_override)
        if chain:
            logger.info(
                "Using settings-defined LLM chain for tenant %s: %s",
                self.tenant_id,
                chain,
            )
            return chain

        return []

    def _fetch_flag_metadata(self, flag_name: str) -> Optional[dict]:
        cache_key = self.FLAG_CACHE_KEY.format(flag_name=flag_name)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from apps.core.feature_flags.models import FeatureFlagMetadata
        except ImportError:
            return None

        try:
            metadata = FeatureFlagMetadata.objects.filter(flag_name=flag_name).values(
                'deployment_metadata',
                'impact_metrics',
            ).first()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to load feature flag metadata %s: %s", flag_name, exc)
            return None

        if not metadata:
            return None

        cache.set(cache_key, metadata, self.CHAIN_CACHE_TTL)
        return metadata

    def _extract_chain(self, metadata: Optional[dict]) -> List[str]:
        if not metadata:
            return []
        deployment = metadata.get('deployment_metadata') or {}
        chain = deployment.get('chain') or deployment.get('providers')
        coerced = self._coerce_chain(chain)
        return coerced or []

    def _extract_provider_from_metadata(self, metadata: Optional[dict]) -> Optional[str]:
        if not metadata:
            return None
        deployment = metadata.get('deployment_metadata') or {}
        for key in ('provider', 'value', 'default'):
            value = deployment.get(key)
            if value:
                return str(value)

        chain = self._extract_chain(metadata)
        if chain:
            return chain[0]
        return None

    def _coerce_chain(self, value: Optional[object]) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, dict):
            nested = value.get('chain') or value.get('providers')
            return self._coerce_chain(nested)
        if isinstance(value, str):
            # Support comma-separated values
            return [item.strip() for item in value.split(',') if item.strip()]
        return []


# Convenience function
def get_llm_router(tenant_id: int) -> LLMProviderRouter:
    """Get LLM provider router for tenant."""
    return LLMProviderRouter(tenant_id)
