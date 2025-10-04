"""
LLM (Large Language Model) configuration settings.
Handles provider configurations, embedding services, and cost controls.
"""

import os
import environ

env = environ.Env()

# LLM Provider Configuration
LLM_PROVIDER = env('LLM_PROVIDER', default='dummy')  # 'openai', 'anthropic', 'dummy'
LLM_MODEL = env('LLM_MODEL', default='dummy-model')
LLM_API_KEY = env('LLM_API_KEY', default='')

# Production LLM Service Configuration
ENABLE_PRODUCTION_LLM = env.bool('ENABLE_PRODUCTION_LLM', default=False)

# LLM provider configurations with cost controls
LLM_PROVIDERS = {
    'openai': {
        'api_key': env('OPENAI_API_KEY', default=''),
        'model': env('OPENAI_LLM_MODEL', default='gpt-3.5-turbo'),
        'max_tokens': env.int('OPENAI_LLM_MAX_TOKENS', default=2048),
        'cost_per_input_token': env.float('OPENAI_LLM_COST_PER_INPUT_TOKEN', default=0.0015),
        'cost_per_output_token': env.float('OPENAI_LLM_COST_PER_OUTPUT_TOKEN', default=0.002),
        'daily_budget_cents': env.int('OPENAI_LLM_DAILY_BUDGET_CENTS', default=2000),  # $20/day
        'timeout_seconds': env.int('OPENAI_LLM_TIMEOUT', default=30),
        'retry_attempts': env.int('OPENAI_LLM_RETRIES', default=3)
    },
    'anthropic': {
        'api_key': env('ANTHROPIC_API_KEY', default=''),
        'model': env('ANTHROPIC_LLM_MODEL', default='claude-3-sonnet-20240229'),
        'max_tokens': env.int('ANTHROPIC_LLM_MAX_TOKENS', default=2048),
        'cost_per_input_token': env.float('ANTHROPIC_LLM_COST_PER_INPUT_TOKEN', default=0.003),
        'cost_per_output_token': env.float('ANTHROPIC_LLM_COST_PER_OUTPUT_TOKEN', default=0.015),
        'daily_budget_cents': env.int('ANTHROPIC_LLM_DAILY_BUDGET_CENTS', default=1500),  # $15/day
        'timeout_seconds': env.int('ANTHROPIC_LLM_TIMEOUT', default=30),
        'retry_attempts': env.int('ANTHROPIC_LLM_RETRIES', default=3)
    },
    'azure': {
        'api_key': env('AZURE_OPENAI_API_KEY', default=''),
        'model': env('AZURE_OPENAI_LLM_MODEL', default='gpt-35-turbo'),
        'azure_endpoint': env('AZURE_OPENAI_ENDPOINT', default=''),
        'api_version': env('AZURE_OPENAI_API_VERSION', default='2024-02-01'),
        'max_tokens': env.int('AZURE_OPENAI_LLM_MAX_TOKENS', default=2048),
        'cost_per_input_token': env.float('AZURE_OPENAI_LLM_COST_PER_INPUT_TOKEN', default=0.0015),
        'cost_per_output_token': env.float('AZURE_OPENAI_LLM_COST_PER_OUTPUT_TOKEN', default=0.002),
        'daily_budget_cents': env.int('AZURE_OPENAI_LLM_DAILY_BUDGET_CENTS', default=1800),  # $18/day
        'timeout_seconds': env.int('AZURE_OPENAI_LLM_TIMEOUT', default=30),
        'retry_attempts': env.int('AZURE_OPENAI_LLM_RETRIES', default=3)
    }
}

# LLM provider fallback order (first is preferred)
LLM_FALLBACK_ORDER = env.list('LLM_FALLBACK_ORDER', default=['openai', 'anthropic', 'azure'])

# Global LLM settings
LLM_REQUEST_TIMEOUT = env.int('LLM_REQUEST_TIMEOUT', default=30)
LLM_MAX_RETRIES = env.int('LLM_MAX_RETRIES', default=3)
LLM_CACHE_TIMEOUT = env.int('LLM_CACHE_TIMEOUT', default=3600)  # 1 hour

# Quality and safety settings
LLM_MIN_QUALITY_SCORE = env.float('LLM_MIN_QUALITY_SCORE', default=0.6)
LLM_ENABLE_SAFETY_FILTER = env.bool('LLM_ENABLE_SAFETY_FILTER', default=True)

# Budget control settings
LLM_DAILY_SPEND_ALERT_CENTS = env.int('LLM_DAILY_SPEND_ALERT_CENTS', default=1000)  # Alert at $10/day
LLM_MONTHLY_SPEND_LIMIT_CENTS = env.int('LLM_MONTHLY_SPEND_LIMIT_CENTS', default=20000)  # $200/month limit

# LLM Cost Models (cents per 1K tokens)
LLM_COST_MODELS = {
    'openai': {
        'gpt-4': {'input_cost_per_1k': 3.0, 'output_cost_per_1k': 6.0},
        'gpt-3.5-turbo': {'input_cost_per_1k': 0.15, 'output_cost_per_1k': 0.2}
    },
    'anthropic': {
        'claude-3-opus': {'input_cost_per_1k': 1.5, 'output_cost_per_1k': 7.5},
        'claude-3-sonnet': {'input_cost_per_1k': 0.3, 'output_cost_per_1k': 1.5}
    },
    'dummy': {
        'dummy-model': {'input_cost_per_1k': 0.0, 'output_cost_per_1k': 0.0}
    }
}

# EMBEDDING SERVICE CONFIGURATION

# Enable production-grade embedding service
ENABLE_PRODUCTION_EMBEDDINGS = env.bool('ENABLE_PRODUCTION_EMBEDDINGS', default=False)

# Embedding provider configurations
EMBEDDING_PROVIDERS = {
    'openai': {
        'api_key': env('OPENAI_API_KEY', default=''),
        'model': env('OPENAI_EMBEDDING_MODEL', default='text-embedding-3-small'),
        'max_tokens': env.int('OPENAI_EMBEDDING_MAX_TOKENS', default=8192),
        'cost_per_token': env.float('OPENAI_EMBEDDING_COST_PER_TOKEN', default=0.00002),
        'daily_budget_cents': env.int('OPENAI_EMBEDDING_DAILY_BUDGET_CENTS', default=1000),  # $10/day
        'timeout_seconds': env.int('OPENAI_EMBEDDING_TIMEOUT', default=30),
        'retry_attempts': env.int('OPENAI_EMBEDDING_RETRIES', default=3)
    },
    'azure': {
        'api_key': env('AZURE_OPENAI_API_KEY', default=''),
        'model': env('AZURE_OPENAI_EMBEDDING_MODEL', default='text-embedding-3-small'),
        'max_tokens': env.int('AZURE_OPENAI_EMBEDDING_MAX_TOKENS', default=8192),
        'cost_per_token': env.float('AZURE_OPENAI_EMBEDDING_COST_PER_TOKEN', default=0.00002),
        'daily_budget_cents': env.int('AZURE_OPENAI_EMBEDDING_DAILY_BUDGET_CENTS', default=750),  # $7.50/day
        'timeout_seconds': env.int('AZURE_OPENAI_EMBEDDING_TIMEOUT', default=30),
        'retry_attempts': env.int('AZURE_OPENAI_EMBEDDING_RETRIES', default=3)
    },
    'local': {
        'api_key': '',  # Not needed for local models
        'model': env('LOCAL_EMBEDDING_MODEL', default='all-MiniLM-L6-v2'),
        'max_tokens': env.int('LOCAL_EMBEDDING_MAX_TOKENS', default=8192),
        'cost_per_token': 0.0,  # Local models are free
        'daily_budget_cents': 0,  # No budget limit for local
        'timeout_seconds': env.int('LOCAL_EMBEDDING_TIMEOUT', default=60),
        'retry_attempts': env.int('LOCAL_EMBEDDING_RETRIES', default=2)
    }
}

# Provider fallback order (first is preferred)
EMBEDDING_FALLBACK_ORDER = env.list('EMBEDDING_FALLBACK_ORDER', default=['openai', 'azure', 'local'])

# Azure OpenAI specific settings
AZURE_OPENAI_ENDPOINT = env('AZURE_OPENAI_ENDPOINT', default='')
AZURE_OPENAI_API_VERSION = env('AZURE_OPENAI_API_VERSION', default='2024-02-01')

# Global embedding settings
EMBEDDING_CACHE_TIMEOUT = env.int('EMBEDDING_CACHE_TIMEOUT', default=86400)  # 24 hours
EMBEDDING_MAX_BATCH_SIZE = env.int('EMBEDDING_MAX_BATCH_SIZE', default=100)
EMBEDDING_RATE_LIMIT_PER_MINUTE = env.int('EMBEDDING_RATE_LIMIT_PER_MINUTE', default=60)

# Cost control settings
EMBEDDING_DAILY_SPEND_ALERT_CENTS = env.int('EMBEDDING_DAILY_SPEND_ALERT_CENTS', default=500)  # Alert at $5/day
EMBEDDING_MONTHLY_SPEND_LIMIT_CENTS = env.int('EMBEDDING_MONTHLY_SPEND_LIMIT_CENTS', default=10000)  # $100/month limit

# COST TRACKING AND BUDGET CONTROLS

ENABLE_COST_TRACKING = env.bool('ENABLE_COST_TRACKING', default=True)
DAILY_COST_BUDGET_CENTS = env.int('DAILY_COST_BUDGET_CENTS', default=10000)  # $100

# Rate Limits by Resource Type
ONBOARDING_RATE_LIMITS = {
    'llm_calls': {
        'requests': {
            'daily': env.int('LLM_DAILY_REQUEST_LIMIT', default=100),
            'hourly': env.int('LLM_HOURLY_REQUEST_LIMIT', default=20)
        },
        'tokens': {
            'daily': env.int('LLM_DAILY_TOKEN_LIMIT', default=50000),
            'hourly': env.int('LLM_HOURLY_TOKEN_LIMIT', default=10000)
        },
        'cost': {
            'daily': env.int('LLM_DAILY_COST_LIMIT_CENTS', default=1000)
        }
    },
    'translations': {
        'requests': {
            'daily': env.int('TRANSLATION_DAILY_REQUEST_LIMIT', default=500),
            'hourly': env.int('TRANSLATION_HOURLY_REQUEST_LIMIT', default=100)
        },
        'characters': {
            'daily': env.int('TRANSLATION_DAILY_CHAR_LIMIT', default=100000),
            'hourly': env.int('TRANSLATION_HOURLY_CHAR_LIMIT', default=20000)
        }
    }
}

# Caching Configuration
LLM_CACHE_TTL = env.int('LLM_CACHE_TTL', default=3600)  # 1 hour
LLM_MAX_CACHE_SIZE = env.int('LLM_MAX_CACHE_SIZE', default=10000)
CACHE_VERSION = env('CACHE_VERSION', default='1.0')

# Provider Configuration
DEFAULT_LLM_PROVIDER = env('DEFAULT_LLM_PROVIDER', default='gpt-3.5-turbo')

# ============================================================================
# Parlant Conversational AI Agent Configuration (Phase 3 - October 2025)
# ============================================================================
# Parlant provides ensured rule compliance for Security & Facility Mentor
# conversations. See: https://github.com/emcie-co/parlant

# Enable/Disable Parlant Agent
ENABLE_PARLANT_AGENT = env.bool('ENABLE_PARLANT_AGENT', default=False)

# Parlant LLM Provider Configuration
PARLANT_LLM_PROVIDER = env('PARLANT_LLM_PROVIDER', default='openai')  # openai, anthropic, huggingface
PARLANT_MODEL_NAME = env('PARLANT_MODEL_NAME', default='gpt-4-turbo')  # Model for Parlant agent
PARLANT_TEMPERATURE = env.float('PARLANT_TEMPERATURE', default=0.3)  # Lower = more consistent
PARLANT_MAX_TOKENS = env.int('PARLANT_MAX_TOKENS', default=1000)

# Parlant Agent Behavior
PARLANT_AGENT_NAME = env('PARLANT_AGENT_NAME', default='SecurityFacilityMentor')
PARLANT_ENABLE_JOURNEYS = env.bool('PARLANT_ENABLE_JOURNEYS', default=True)
PARLANT_ENABLE_TOOLS = env.bool('PARLANT_ENABLE_TOOLS', default=True)
PARLANT_STRICT_COMPLIANCE = env.bool('PARLANT_STRICT_COMPLIANCE', default=True)  # Enforce prohibition rules

# Parlant Performance
PARLANT_RESPONSE_TIMEOUT = env.int('PARLANT_RESPONSE_TIMEOUT', default=30)  # seconds
PARLANT_MAX_CONVERSATION_TURNS = env.int('PARLANT_MAX_CONVERSATION_TURNS', default=50)

# Parlant Monitoring
PARLANT_LOG_GUIDELINES = env.bool('PARLANT_LOG_GUIDELINES', default=True)  # Log guideline matches
PARLANT_LOG_TOOLS = env.bool('PARLANT_LOG_TOOLS', default=True)  # Log tool executions
PARLANT_LOG_JOURNEYS = env.bool('PARLANT_LOG_JOURNEYS', default=True)  # Log journey states