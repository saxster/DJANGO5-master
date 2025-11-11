"""
Feature Flag System

Provides feature toggle functionality for safe deployments and experimentation.
Follows .claude/rules.md Rule #16 (explicit __all__).

Features:
- Feature flags with percentage rollout
- User/group-based targeting
- A/B testing support
- Gradual rollout management
"""

from importlib import import_module
from typing import Any

__all__ = [
    "feature_required",
    "feature_enabled_for_user",
    "FeatureFlagService",
    "FeatureFlagMiddleware",
]

_EXPORTS = {
    "feature_required": ("apps.core.feature_flags.decorators", "feature_required"),
    "feature_enabled_for_user": ("apps.core.feature_flags.decorators", "feature_enabled_for_user"),
    "FeatureFlagService": ("apps.core.feature_flags.service", "FeatureFlagService"),
    "FeatureFlagMiddleware": ("apps.core.feature_flags.middleware", "FeatureFlagMiddleware"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'apps.core.feature_flags' has no attribute '{name}'")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
