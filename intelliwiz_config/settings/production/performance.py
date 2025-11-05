"""
Production performance tuning and optimization settings.

Handles:
- Cache configuration
- Redis optimization
- Feature flags
- Rate limiting
- Data upload limits
- Storage configuration
- Personalization settings
"""

import os
from typing import Dict, Any

import environ


def get_performance_settings() -> Dict[str, Any]:
    """
    Get production performance optimization settings.

    Returns:
        Dictionary of performance-related settings
    """
    env = environ.Env()
    environ.Env.read_env()

    return {
        'DATA_UPLOAD_MAX_MEMORY_SIZE': env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10485760),
        'ENABLE_RATE_LIMITING': True,
        'RATE_LIMIT_WINDOW_MINUTES': 15,
        'RATE_LIMIT_MAX_ATTEMPTS': 5,
        'RATE_LIMIT_PATHS': [
            "/login/", "/accounts/login/", "/auth/login/",
            "/api/", "/api/v1/",
            "/reset-password/", "/password-reset/",
            "/admin/", "/admin/django/",
            "/api/upload/"
        ],
        'REDIS_MONITORING_ENABLED': True,
        'REDIS_PERFORMANCE_LOGGING': True,
        'DJANGO_ENVIRONMENT': 'production',
    }


def get_cache_settings() -> Dict[str, Any]:
    """
    Get production cache and Redis configuration.

    Returns:
        Dictionary with CACHES and CHANNEL_LAYERS settings
    """
    from .redis_optimized import OPTIMIZED_CACHES, OPTIMIZED_CHANNEL_LAYERS

    return {
        'CACHES': OPTIMIZED_CACHES,
        'CHANNEL_LAYERS': OPTIMIZED_CHANNEL_LAYERS,
    }


def get_storage_settings() -> Dict[str, Any]:
    """
    Get production storage configuration.

    Returns:
        Dictionary of storage-related settings
    """
    env = environ.Env()
    environ.Env.read_env()

    return {
        'STATIC_ROOT': env("STATIC_ROOT"),
        'MEDIA_ROOT': env("MEDIA_ROOT"),
        'MEDIA_URL': "/youtility4_media/",
        'BUCKET': env("BUCKET", default="prod-attachment-sukhi-group"),
        'TEMP_REPORTS_GENERATED': env("TEMP_REPORTS_GENERATED"),
        'ONDEMAND_REPORTS_GENERATED': env("ONDEMAND_REPORTS_GENERATED"),
    }


def get_feature_flags() -> Dict[str, Any]:
    """
    Get production feature flags (conservative defaults).

    Returns:
        Dictionary of feature flag settings
    """
    env = environ.Env()
    environ.Env.read_env()

    return {
        'ENABLE_CONVERSATIONAL_ONBOARDING': env.bool('ENABLE_CONVERSATIONAL_ONBOARDING', default=False),
        'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER': env.bool('ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', default=False),
        'ENABLE_ONBOARDING_KB': env.bool('ENABLE_ONBOARDING_KB', default=False),
        'ENABLE_ONBOARDING_SSE': env.bool('ENABLE_ONBOARDING_SSE', default=False),
        'ENABLE_API_AUTH': True,
        'API_AUTH_PATHS': ["/api/"],
        'API_REQUIRE_SIGNING': env.bool("API_REQUIRE_SIGNING", default=True),
    }


def get_personalization_settings() -> Dict[str, Any]:
    """
    Get production personalization and ML settings.

    Returns:
        Dictionary of personalization configuration
    """
    env = environ.Env()
    environ.Env.read_env()

    return {
        'ONBOARDING_LEARNING_HOLDBACK_PCT': env.float('ONBOARDING_LEARNING_HOLDBACK_PCT', default=10.0),
        'ONBOARDING_EXPERIMENT_HOLDBACK_PCT': env.float('ONBOARDING_EXPERIMENT_HOLDBACK_PCT', default=5.0),
        'EXPERIMENT_MIN_SAMPLE_SIZE': env.int('EXPERIMENT_MIN_SAMPLE_SIZE', default=100),
        'BANDIT_EPSILON': env.float('BANDIT_EPSILON', default=0.05),
        'PERSONALIZATION_FEATURE_FLAGS': {
            'enable_preference_learning': env.bool('FF_PREFERENCE_LEARNING', default=True),
            'enable_cost_optimization': env.bool('FF_COST_OPTIMIZATION', default=True),
            'enable_experiment_assignments': env.bool('FF_EXPERIMENT_ASSIGNMENTS', default=True),
            'enable_smart_caching': env.bool('FF_SMART_CACHING', default=True),
            'enable_adaptive_budgeting': env.bool('FF_ADAPTIVE_BUDGETING', default=True),
            'enable_provider_routing': env.bool('FF_PROVIDER_ROUTING', default=True),
            'enable_hot_path_precompute': env.bool('FF_HOT_PATH_PRECOMPUTE', default=False),
            'enable_streaming_responses': env.bool('FF_STREAMING_RESPONSES', default=False),
            'enable_anomaly_detection': env.bool('FF_ANOMALY_DETECTION', default=True),
            'enable_audit_logging': env.bool('FF_AUDIT_LOGGING', default=True)
        }
    }
