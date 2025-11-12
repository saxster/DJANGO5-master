"""
Wellness Views Package - Refactored into domain-specific modules

This package contains all wellness view classes, split from the original 948-line
views.py file into focused, maintainable modules following ADR 003 (Service Layer).

Architecture:
- All business logic moved to services/wellness/ directory
- Views handle only: request validation, permission checks, service calls, response formatting
- All view methods < 30 lines
- All service files < 150 lines

Modules:
- permissions: Custom permission classes
- content_views: Content listing, filtering, interaction tracking
- personalization_views: Daily tips, contextual content delivery
- recommendation_views: ML-powered personalized recommendations
- progress_views: User progress and gamification
- analytics_views: Engagement analytics and insights

Original file: views.py (948 lines) → views_deprecated.py (backup)
"""

from .permissions import WellnessPermission
from .content_views import WellnessContentViewSet
from .personalization_views import DailyWellnessTipView, ContextualWellnessContentView
from .recommendation_views import PersonalizedWellnessContentView
from .progress_views import WellnessProgressView
from .analytics_views import WellnessAnalyticsView

__all__ = [
    'WellnessPermission',
    'WellnessContentViewSet',
    'DailyWellnessTipView',
    'ContextualWellnessContentView',
    'PersonalizedWellnessContentView',
    'WellnessProgressView',
    'WellnessAnalyticsView',
]
