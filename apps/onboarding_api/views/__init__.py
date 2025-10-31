"""
Backward Compatibility Imports for Refactored Views

This module maintains 100% backward compatibility for existing imports while
the codebase is refactored into focused, domain-driven modules.

OLD USAGE (deprecated but still works):
    from apps.onboarding_api.views import ConversationStartView

NEW USAGE (preferred):
    from apps.onboarding_api.views.conversation_views import ConversationStartView

Both import patterns work during the transition period.

Refactoring Date: 2025-09-30
Phase: God File Elimination - Phase 3
Original File: apps/onboarding_api/views.py (2,399 lines)
New Structure: 7 focused modules (~300 lines each)
"""

# Conversation Management Views
from .conversation_views import (
    ConversationStartView,
    ConversationProcessView,
    ConversationStatusView,
)

# Approval Workflow Views
from .approval_views import (
    RecommendationApprovalView,
    SecondaryApprovalView,
)

# Changeset Management Views
from .changeset_views import (
    ChangeSetRollbackView,
    ChangeSetListView,
    ChangeSetDiffPreviewView,
)

# Knowledge Base Views
from .knowledge_views import (
    AuthoritativeKnowledgeViewSet,
    validate_knowledge,
)

# Template Management Views
from .template_views import (
    ConfigurationTemplatesView,
    ConfigurationTemplateDetailView,
    QuickStartRecommendationsView,
    OneClickDeploymentView,
    TemplateAnalyticsView,
)

# Health Check & Analytics Views
from .health_analytics_views import (
    FeatureStatusView,
    cache_health_check,
    logging_health_check,
    logging_documentation,
    preflight_validation,
    preflight_quick_check,
    system_health_monitoring,
    reset_degradations,
    degradation_status,
)

# Voice Input Views
from .voice_views import (
    ConversationVoiceInputView,
    VoiceCapabilityView,
)

# Site Audit Views (Refactored 2025-10-12: 1,506 lines → 5 modules)
from .site_audit import (
    # Session Management
    SiteAuditStartView,
    SiteAuditStatusView,
    # Observation Capture
    ObservationCaptureView,
    ObservationListView,
    # Coverage & Guidance
    NextQuestionsView,
    CoverageMapView,
    speak_text,
    # Asset & Zone Management
    ZoneManagementView,
    AssetManagementView,
    MeterPointManagementView,
    # Analysis & Reporting
    AuditAnalysisView,
    CoveragePlanView,
    SOPListView,
    AuditReportView,
)

# Export all views for backward compatibility
__all__ = [
    # Conversation Management
    'ConversationStartView',
    'ConversationProcessView',
    'ConversationStatusView',

    # Approval Workflows
    'RecommendationApprovalView',
    'SecondaryApprovalView',

    # Changeset Management
    'ChangeSetRollbackView',
    'ChangeSetListView',
    'ChangeSetDiffPreviewView',

    # Knowledge Base
    'AuthoritativeKnowledgeViewSet',
    'validate_knowledge',

    # Template Management
    'ConfigurationTemplatesView',
    'ConfigurationTemplateDetailView',
    'QuickStartRecommendationsView',
    'OneClickDeploymentView',
    'TemplateAnalyticsView',

    # Health & Analytics
    'FeatureStatusView',
    'cache_health_check',
    'logging_health_check',
    'logging_documentation',
    'preflight_validation',
    'preflight_quick_check',
    'system_health_monitoring',
    'reset_degradations',
    'degradation_status',

    # Voice Input
    'ConversationVoiceInputView',
    'VoiceCapabilityView',

    # Site Audit (refactored 2025-10-12)
    'SiteAuditStartView',
    'SiteAuditStatusView',
    'ObservationCaptureView',
    'ObservationListView',
    'NextQuestionsView',
    'CoverageMapView',
    'speak_text',
    'ZoneManagementView',
    'AssetManagementView',
    'MeterPointManagementView',
    'AuditAnalysisView',
    'CoveragePlanView',
    'SOPListView',
    'AuditReportView',
]

# Module-level documentation
"""
Module Structure:

1. conversation_views.py (~350 lines)
   - ConversationStartView: Start new conversation sessions
   - ConversationProcessView: Process user inputs (sync/async)
   - ConversationStatusView: Track conversation progress

2. approval_views.py (~380 lines)
   - RecommendationApprovalView: Approve/reject AI recommendations
   - SecondaryApprovalView: Handle two-person approval rule

3. changeset_views.py (~280 lines)
   - ChangeSetRollbackView: Rollback applied changes
   - ChangeSetListView: List and filter changesets
   - ChangeSetDiffPreviewView: Preview pending changes

4. knowledge_views.py (~140 lines)
   - AuthoritativeKnowledgeViewSet: Manage knowledge base
   - validate_knowledge: Validate against authoritative sources

5. template_views.py (~320 lines)
   - ConfigurationTemplatesView: List/recommend templates
   - ConfigurationTemplateDetailView: Get/apply specific template
   - QuickStartRecommendationsView: Quick-start recommendations
   - OneClickDeploymentView: One-click template deployment
   - TemplateAnalyticsView: Template usage analytics

6. health_analytics_views.py (~240 lines)
   - FeatureStatusView: Check feature status
   - cache_health_check: Validate cache backend
   - logging_health_check: Validate logging config
   - preflight_validation: Comprehensive readiness checks
   - system_health_monitoring: System health dashboard

7. voice_views.py (~180 lines)
   - ConversationVoiceInputView: Process voice input
   - VoiceCapabilityView: Voice capability information

Total: 1,890 lines across 7 focused modules (down from 2,399 in single file)
Reduction: 21% reduction + improved testability & maintainability
"""