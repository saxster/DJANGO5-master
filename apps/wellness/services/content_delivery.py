"""
Wellness Content Delivery System - Backward Compatibility Facade

This module maintains backward compatibility while delegating to focused service modules.

NEW ARCHITECTURE (November 2025):
- apps/wellness/services/content/user_profiler.py - User profile building
- apps/wellness/services/content/personalization_engine.py - ML recommendations
- apps/wellness/services/content/content_selector.py - Contextual content selection

MIGRATION GUIDE:
Old import:
    from apps.wellness.services.content_delivery import WellnessContentDeliveryService

New import (recommended):
    from apps.wellness.services.content import WellnessContentDeliveryService

Both imports work identically - this facade ensures backward compatibility.
"""

# Backward-compatible imports - delegate to focused modules
from .content.user_profiler import UserProfileBuilder
from .content.personalization_engine import (
    WellnessTipSelector,
    WellnessRecommendationEngine
)
from .content.content_selector import (
    WellnessContentDeliveryService,
    ContextualContentEngine,
    trigger_pattern_analysis
)

# Export all classes for backward compatibility
__all__ = [
    'UserProfileBuilder',
    'WellnessTipSelector',
    'WellnessRecommendationEngine',
    'WellnessContentDeliveryService',
    'ContextualContentEngine',
    'trigger_pattern_analysis',
]
