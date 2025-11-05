"""
Wellness App Views - REFACTORED (Phase 2)

MIGRATION COMPLETE: This file has been split into views/ directory
Original 948-line file backed up as views_deprecated.py

NEW ARCHITECTURE:
=================
Business logic moved to services/wellness/:
- PatternAnalysisService: User journal pattern analysis
- UrgencyAnalysisService: Journal entry urgency scoring
- UserProfileService: Comprehensive user profile building
- PersonalizationService: Personalized content selection
- ContentSelectionService: Context-based content selection
- MLRecommendationService: ML-based recommendations
- AnalyticsService: Engagement analytics

Views split into focused modules:
- views/permissions.py: Custom permission classes
- views/content_views.py: Content listing, filtering, interaction tracking
- views/personalization_views.py: Daily tips, contextual content delivery
- views/recommendation_views.py: ML-powered recommendations
- views/progress_views.py: User progress and gamification
- views/analytics_views.py: Engagement analytics

All view methods now < 30 lines (business logic in services)
All service files < 150 lines

VERIFICATION RESULTS:
====================
✅ File split: 948 lines → 7 view modules + 7 service modules
✅ All methods < 30 lines (previously 11 violations)
✅ Business logic extracted to services (ADR 003 compliance)
✅ Backward compatibility maintained (same imports)
✅ Original file backed up as views_deprecated.py

Refactored: November 5, 2025
Agent: Phase 2 Wellness Views Refactor
"""

# Import all views from new views/ directory for backward compatibility
from .views import (
    WellnessPermission,
    WellnessContentViewSet,
    DailyWellnessTipView,
    ContextualWellnessContentView,
    PersonalizedWellnessContentView,
    WellnessProgressView,
    WellnessAnalyticsView,
)

__all__ = [
    'WellnessPermission',
    'WellnessContentViewSet',
    'DailyWellnessTipView',
    'ContextualWellnessContentView',
    'PersonalizedWellnessContentView',
    'WellnessProgressView',
    'WellnessAnalyticsView',
]
