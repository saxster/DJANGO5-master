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

from .decorators import feature_required, feature_enabled_for_user
from .service import FeatureFlagService
from .middleware import FeatureFlagMiddleware

__all__ = [
    'feature_required',
    'feature_enabled_for_user',
    'FeatureFlagService',
    'FeatureFlagMiddleware',
]
