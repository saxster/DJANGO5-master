"""
LLM Provider Registry

Factory functions for provider instantiation.

Following CLAUDE.md Rule #7: <150 lines

Sprint 7-8 Phase 3: Provider Implementations
"""

from .openai_provider import OpenAIMakerLLM, OpenAICheckerLLM
from .anthropic_provider import AnthropicMakerLLM, AnthropicCheckerLLM
from .gemini_provider import GeminiMakerLLM, GeminiCheckerLLM

# Provider registry mapping
# Priority order: Gemini (primary) → Anthropic (fallback) → OpenAI (secondary fallback)
PROVIDER_REGISTRY = {
    'gemini': {
        'maker': GeminiMakerLLM,
        'checker': GeminiCheckerLLM,
    },
    'anthropic': {
        'maker': AnthropicMakerLLM,
        'checker': AnthropicCheckerLLM,
    },
    'openai': {
        'maker': OpenAIMakerLLM,
        'checker': OpenAICheckerLLM,
    },
}


def get_provider(provider_name: str, llm_type: str, tenant_id: int, api_key: str = None):
    """
    Factory function for provider instantiation.

    Args:
        provider_name: 'openai', 'anthropic', or 'gemini'
        llm_type: 'maker' or 'checker'
        tenant_id: Tenant identifier
        api_key: API key (fetched from settings if None)

    Returns:
        Provider instance (MakerLLM or CheckerLLM)

    Raises:
        ValueError: If provider not found
    """
    from apps.core_onboarding.services.llm.exceptions import InvalidProviderConfigError

    if provider_name not in PROVIDER_REGISTRY:
        raise InvalidProviderConfigError(
            f"Provider '{provider_name}' not found. Available: {list(PROVIDER_REGISTRY.keys())}"
        )

    if llm_type not in ['maker', 'checker']:
        raise InvalidProviderConfigError(
            f"Invalid LLM type '{llm_type}'. Must be 'maker' or 'checker'"
        )

    # Get API key from database first, fallback to settings
    if api_key is None:
        try:
            from apps.core.services.secrets_manager_service import SecretsManagerService

            # Map provider to secret key name
            secret_key_map = {
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY',
                'gemini': 'GOOGLE_API_KEY',
            }

            key_name = secret_key_map.get(provider_name)
            if key_name:
                # Try database first, fallback to environment/settings
                api_key = SecretsManagerService.get_secret(key_name)

            # Final fallback to settings if SecretsManager fails
            if not api_key:
                from django.conf import settings
                api_key_map = {
                    'openai': getattr(settings, 'OPENAI_API_KEY', ''),
                    'anthropic': getattr(settings, 'ANTHROPIC_API_KEY', ''),
                    'gemini': getattr(settings, 'GOOGLE_API_KEY', ''),
                }
                api_key = api_key_map.get(provider_name, '')

        except (ImportError, AttributeError) as e:
            # Fallback to settings if secrets service not available
            from django.conf import settings
            api_key_map = {
                'openai': getattr(settings, 'OPENAI_API_KEY', ''),
                'anthropic': getattr(settings, 'ANTHROPIC_API_KEY', ''),
                'gemini': getattr(settings, 'GOOGLE_API_KEY', ''),
            }
            api_key = api_key_map.get(provider_name, '')

    if not api_key:
        raise InvalidProviderConfigError(
            f"API key not configured for {provider_name}"
        )

    # Instantiate provider
    provider_class = PROVIDER_REGISTRY[provider_name][llm_type]
    return provider_class(tenant_id=tenant_id, api_key=api_key)


__all__ = [
    'PROVIDER_REGISTRY',
    'get_provider',
    'GeminiMakerLLM',
    'GeminiCheckerLLM',
    'AnthropicMakerLLM',
    'AnthropicCheckerLLM',
    'OpenAIMakerLLM',
    'OpenAICheckerLLM',
]
