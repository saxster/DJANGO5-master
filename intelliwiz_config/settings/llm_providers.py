"""
LLM Provider Configuration

API keys, quotas, circuit breaker settings, and cost rates for LLM providers.

Following CLAUDE.md:
- Rule #1: Secrets via environment variables
- Rule #7: <150 lines
- Startup validation

Sprint 7-8 Phase 1: LLM Provider Foundation
"""

from django.core.exceptions import ImproperlyConfigured
import os

# =============================================================================
# API KEYS (SECURITY CRITICAL)
# =============================================================================

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_ORGANIZATION_ID = os.getenv('OPENAI_ORGANIZATION_ID', '')

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# =============================================================================
# CIRCUIT BREAKER CONFIGURATION
# =============================================================================

LLM_CIRCUIT_BREAKER = {
    'failure_threshold': int(os.getenv('LLM_CIRCUIT_BREAKER_THRESHOLD', 3)),
    'cooldown_seconds': int(os.getenv('LLM_CIRCUIT_BREAKER_COOLDOWN', 60)),
    'half_open_max_calls': int(os.getenv('LLM_CIRCUIT_BREAKER_HALF_OPEN', 1)),
}

# =============================================================================
# DEFAULT QUOTAS
# =============================================================================

LLM_DEFAULT_QUOTAS = {
    'daily_request_limit': int(os.getenv('LLM_DEFAULT_DAILY_REQUEST_LIMIT', 1000)),
    'monthly_request_limit': int(os.getenv('LLM_DEFAULT_MONTHLY_REQUEST_LIMIT', 30000)),
    'daily_cost_limit_usd': float(os.getenv('LLM_DEFAULT_DAILY_COST_LIMIT', 50.00)),
    'monthly_cost_limit_usd': float(os.getenv('LLM_DEFAULT_MONTHLY_COST_LIMIT', 1000.00)),
}

# =============================================================================
# COST RATES (per 1 million tokens)
# =============================================================================

LLM_COST_RATES = {
    'openai': {
        'gpt-4-turbo-2024-04-09': {
            'input': 10.00,   # $10 per 1M input tokens
            'output': 30.00,  # $30 per 1M output tokens
        },
        'gpt-4': {
            'input': 30.00,
            'output': 60.00,
        },
        'gpt-3.5-turbo': {
            'input': 0.50,
            'output': 1.50,
        },
    },
    'anthropic': {
        'claude-3-5-sonnet-20241022': {
            'input': 3.00,    # $3 per 1M input tokens
            'output': 15.00,  # $15 per 1M output tokens
        },
        'claude-3-opus-20240229': {
            'input': 15.00,
            'output': 75.00,
        },
    },
    'gemini': {
        'gemini-1.5-pro': {
            'input': 1.25,    # $1.25 per 1M input tokens
            'output': 5.00,   # $5 per 1M output tokens
        },
        'gemini-1.5-flash': {
            'input': 0.075,
            'output': 0.30,
        },
    },
}

# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

# Default models for each provider
LLM_DEFAULT_MODELS = {
    'openai': 'gpt-4-turbo-2024-04-09',
    'anthropic': 'claude-3-5-sonnet-20241022',
    'gemini': 'gemini-1.5-pro',
}

# API timeouts (connect_timeout, read_timeout)
LLM_API_TIMEOUT = (
    int(os.getenv('LLM_API_CONNECT_TIMEOUT', 5)),
    int(os.getenv('LLM_API_READ_TIMEOUT', 30)),
)

# Max retries for transient errors
LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', 2))

# Token limits per request
LLM_MAX_INPUT_TOKENS = {
    'openai': 128000,      # GPT-4 Turbo
    'anthropic': 200000,   # Claude 3.5 Sonnet
    'gemini': 1000000,     # Gemini 1.5 Pro
}

# =============================================================================
# FEATURE FLAGS DEFAULTS
# =============================================================================

# Default provider priority (can be overridden per tenant via FeatureFlag model)
LLM_DEFAULT_FALLBACK_CHAIN = ['openai', 'anthropic', 'gemini']

# Enable/disable providers globally
LLM_PROVIDERS_ENABLED = {
    'openai': bool(OPENAI_API_KEY),
    'anthropic': bool(ANTHROPIC_API_KEY),
    'gemini': bool(GOOGLE_API_KEY),
}

# =============================================================================
# VALIDATION
# =============================================================================

def validate_llm_provider_settings():
    """Validate LLM provider settings at startup."""
    errors = []

    # Require at least one provider
    enabled_count = sum(1 for enabled in LLM_PROVIDERS_ENABLED.values() if enabled)
    if enabled_count == 0:
        errors.append(
            "No LLM providers configured. Set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY"
        )

    # Validate circuit breaker thresholds
    if LLM_CIRCUIT_BREAKER['failure_threshold'] < 1:
        errors.append("LLM_CIRCUIT_BREAKER_THRESHOLD must be >= 1")

    if LLM_CIRCUIT_BREAKER['cooldown_seconds'] < 10:
        errors.append("LLM_CIRCUIT_BREAKER_COOLDOWN must be >= 10 seconds")

    if errors:
        raise ImproperlyConfigured(
            f"LLM Provider configuration errors:\n" + "\n".join(errors)
        )


# Run validation on import
validate_llm_provider_settings()
