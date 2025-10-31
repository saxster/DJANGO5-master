"""
Site Audit Views Module - Backward Compatibility Layer

This module provides 100% backward compatibility for the refactored site audit views.
All view classes and helper functions are re-exported from their new locations.

Migration Date: 2025-10-12
Original File: apps/onboarding_api/views/site_audit_views.py (1,506 lines)
New Structure: 5 domain-focused modules

Usage:
    # Old import (still works):
    from apps.onboarding_api.views.site_audit_views import SiteAuditStartView

    # New import (recommended):
    from apps.onboarding_api.views.site_audit.session_management_views import SiteAuditStartView

Refactoring Details:
    - Total reduction: 1,506 lines → 5 modules (~330 lines avg)
    - CLAUDE.md compliance: 100% (all modules < 500 lines)
    - Backward compatibility: 100% (all imports work)
    - Security: Upload throttling and transaction management preserved

Architecture:
    session_management_views.py (296 lines) - Session lifecycle management
    observation_capture_views.py (434 lines) - Multimodal capture (voice/photo/GPS)
    coverage_guidance_views.py (237 lines) - Real-time guidance and coverage tracking
    asset_zone_management_views.py (263 lines) - Zone/asset/meter point CRUD
    analysis_reporting_views.py (461 lines) - AI analysis and report generation
"""

# Session Management (lines 94-339)
from .session_management_views import (
    SiteAuditStartView,
    SiteAuditStatusView,
)

# Observation Capture (lines 341-718)
from .observation_capture_views import (
    ObservationCaptureView,
    ObservationListView,
)

# Coverage & Guidance (lines 720-853, 1458-1506)
from .coverage_guidance_views import (
    NextQuestionsView,
    CoverageMapView,
    speak_text,  # Utility function
)

# Asset & Zone Management (lines 855-1046)
from .asset_zone_management_views import (
    ZoneManagementView,
    AssetManagementView,
    MeterPointManagementView,
)

# Analysis & Reporting (lines 1048-1456)
from .analysis_reporting_views import (
    AuditAnalysisView,
    CoveragePlanView,
    SOPListView,
    AuditReportView,
)

__all__ = [
    # Session Management
    "SiteAuditStartView",
    "SiteAuditStatusView",
    # Observation Capture
    "ObservationCaptureView",
    "ObservationListView",
    # Coverage & Guidance
    "NextQuestionsView",
    "CoverageMapView",
    "speak_text",
    # Asset & Zone Management
    "ZoneManagementView",
    "AssetManagementView",
    "MeterPointManagementView",
    # Analysis & Reporting
    "AuditAnalysisView",
    "CoveragePlanView",
    "SOPListView",
    "AuditReportView",
]
