"""
URL configuration for Conversational Onboarding API (Phase 1 MVP + Phase 2 Enhanced + Personalization + Monitoring)
"""
from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from . import views, views_phase2, admin_views, knowledge_views, personalization_views, monitoring_views, views_ui, views_ui_compat
from .views import site_audit  # Refactored 2025-10-12: site_audit_views.py → site_audit/ package
from .openapi_schemas import schema_view

# Backward compatibility alias
site_audit_views = site_audit

app_name = 'onboarding_api'

# DRF Router for ViewSets
router = DefaultRouter()
router.register('knowledge', views.AuthoritativeKnowledgeViewSet, basename='knowledge')
router.register('documents', views_phase2.KnowledgeDocumentViewSet, basename='documents')

urlpatterns = [
    # ========== FEATURE STATUS ENDPOINT ==========
    path(
        'status/',
        views.FeatureStatusView.as_view(),
        name='feature-status'
    ),

    # ========== CONVERSATION ENDPOINTS ==========
    # Phase 1 endpoints
    path(
        'conversation/start/',
        views.ConversationStartView.as_view(),
        name='conversation-start'
    ),
    path(
        'conversation/<uuid:conversation_id>/process/',
        views.ConversationProcessView.as_view(),
        name='conversation-process'
    ),
    path(
        'conversation/<uuid:conversation_id>/status/',
        views.ConversationStatusView.as_view(),
        name='conversation-status'
    ),

    # Voice input endpoints
    path(
        'conversation/<uuid:conversation_id>/voice/',
        views.ConversationVoiceInputView.as_view(),
        name='conversation-voice-input'
    ),
    path(
        'voice/capabilities/',
        views.VoiceCapabilityView.as_view(),
        name='voice-capabilities'
    ),

    # Phase 2 enhanced endpoints
    path(
        'conversation/<uuid:conversation_id>/process-enhanced/',
        views_phase2.EnhancedConversationProcessView.as_view(),
        name='conversation-process-enhanced'
    ),
    path(
        'conversation/<uuid:conversation_id>/events/',
        views_phase2.ConversationEventsView.as_view(),
        name='conversation-events'
    ),
    path(
        'conversation/<uuid:conversation_id>/escalate/',
        views_phase2.ConversationEscalationView.as_view(),
        name='conversation-escalate'
    ),

    # ========== RECOMMENDATION ENDPOINTS ==========
    path(
        'recommendations/approve/',
        views.RecommendationApprovalView.as_view(),
        name='recommendations-approve'
    ),
    path(
        'approvals/<int:approval_id>/decide/',
        views.SecondaryApprovalView.as_view(),
        name='secondary-approval-decide'
    ),

    # ========== CONFIGURATION TEMPLATES ENDPOINTS ==========
    path(
        'templates/',
        views.ConfigurationTemplatesView.as_view(),
        name='configuration-templates'
    ),
    path(
        'templates/<str:template_id>/',
        views.ConfigurationTemplateDetailView.as_view(),
        name='configuration-template-detail'
    ),
    path(
        'templates/<str:template_id>/deploy/',
        views.OneClickDeploymentView.as_view(),
        name='template-deploy'
    ),
    path(
        'templates/analytics/',
        views.TemplateAnalyticsView.as_view(),
        name='template-analytics'
    ),
    path(
        'quickstart/recommendations/',
        views.QuickStartRecommendationsView.as_view(),
        name='quickstart-recommendations'
    ),

    # ========== PREFLIGHT VALIDATION ENDPOINTS ==========
    path(
        'preflight/',
        views.preflight_validation,
        name='preflight-validation'
    ),
    path(
        'preflight/quick/',
        views.preflight_quick_check,
        name='preflight-quick-check'
    ),

    # ========== CHANGESET AND ROLLBACK ENDPOINTS ==========
    path(
        'changesets/',
        views.ChangeSetListView.as_view(),
        name='changesets-list'
    ),
    path(
        'changesets/<uuid:changeset_id>/rollback/',
        views.ChangeSetRollbackView.as_view(),
        name='changesets-rollback'
    ),
    path(
        'changeset/preview/',
        views.ChangeSetDiffPreviewView.as_view(),
        name='changeset-preview'
    ),

    # ========== SITE AUDIT ENDPOINTS (Phase C) ==========
    # Session Management
    path(
        'site-audit/start/',
        site_audit_views.SiteAuditStartView.as_view(),
        name='site-audit-start'
    ),
    path(
        'site-audit/<uuid:session_id>/status/',
        site_audit_views.SiteAuditStatusView.as_view(),
        name='site-audit-status'
    ),

    # Observation Capture
    path(
        'site-audit/<uuid:session_id>/observation/',
        site_audit_views.ObservationCaptureView.as_view(),
        name='site-audit-observation-capture'
    ),
    path(
        'site-audit/<uuid:session_id>/observations/',
        site_audit_views.ObservationListView.as_view(),
        name='site-audit-observations-list'
    ),

    # Guidance & Coverage
    path(
        'site-audit/<uuid:session_id>/next-questions/',
        site_audit_views.NextQuestionsView.as_view(),
        name='site-audit-next-questions'
    ),
    path(
        'site-audit/<uuid:session_id>/coverage/',
        site_audit_views.CoverageMapView.as_view(),
        name='site-audit-coverage'
    ),
    path(
        'site-audit/<uuid:session_id>/speak/',
        site_audit_views.speak_text,
        name='site-audit-speak'
    ),

    # Zone & Asset Management
    path(
        'site/<uuid:site_id>/zones/',
        site_audit_views.ZoneManagementView.as_view(),
        name='site-zones-manage'
    ),
    path(
        'site/<uuid:site_id>/assets/',
        site_audit_views.AssetManagementView.as_view(),
        name='site-assets-manage'
    ),
    path(
        'site/<uuid:site_id>/meter-points/',
        site_audit_views.MeterPointManagementView.as_view(),
        name='site-meter-points-manage'
    ),

    # Analysis & Planning
    path(
        'site-audit/<uuid:session_id>/analyze/',
        site_audit_views.AuditAnalysisView.as_view(),
        name='site-audit-analyze'
    ),
    path(
        'site-audit/<uuid:session_id>/coverage-plan/',
        site_audit_views.CoveragePlanView.as_view(),
        name='site-audit-coverage-plan'
    ),
    path(
        'site-audit/<uuid:session_id>/sops/',
        site_audit_views.SOPListView.as_view(),
        name='site-audit-sops'
    ),

    # Reporting
    path(
        'site-audit/<uuid:session_id>/report/',
        site_audit_views.AuditReportView.as_view(),
        name='site-audit-report'
    ),

    # ========== PERSONALIZATION ENDPOINTS ==========
    # User preferences management (staff-only)
    path(
        'preferences/<str:user_or_client>/',
        personalization_views.PreferencesAPIView.as_view(),
        name='preferences-detail'
    ),

    # Experiment management (staff-only)
    path(
        'experiments/',
        personalization_views.ExperimentsAPIView.as_view(),
        name='experiments-list'
    ),
    path(
        'experiments/<uuid:experiment_id>/',
        personalization_views.ExperimentDetailAPIView.as_view(),
        name='experiments-detail'
    ),
    path(
        'experiments/<uuid:experiment_id>/actions/',
        personalization_views.ExperimentActionAPIView.as_view(),
        name='experiments-actions'
    ),

    # Experiment arm assignment (user-facing)
    path(
        'experiments/<uuid:experiment_id>/assign/',
        personalization_views.ExperimentAssignmentAPIView.as_view(),
        name='experiments-assign'
    ),

    # Real-time experiment metrics (staff-only)
    path(
        'experiments/<uuid:experiment_id>/metrics/',
        personalization_views.experiment_metrics,
        name='experiments-metrics'
    ),

    # Learning signals collection
    path(
        'interactions/',
        personalization_views.record_interaction,
        name='record-interaction'
    ),
    path(
        'cost-signals/',
        personalization_views.record_cost_signal,
        name='record-cost-signal'
    ),

    # ========== KNOWLEDGE ENDPOINTS ==========
    # Basic knowledge endpoints
    path(
        'knowledge/validate/',
        views.validate_knowledge,
        name='knowledge-validate'
    ),
    path(
        'knowledge/search/',
        views_phase2.search_knowledge_enhanced,
        name='knowledge-search-enhanced'
    ),

    # Phase 2 knowledge management
    path(
        'knowledge/documents/<uuid:knowledge_id>/embed/',
        views_phase2.embed_knowledge_document,
        name='knowledge-embed'
    ),

    # ========== PRODUCTION-GRADE KNOWLEDGE MANAGEMENT API ==========
    # Knowledge source management (allowlisted only)
    path(
        'knowledge/sources/',
        knowledge_views.KnowledgeSourceAPIView.as_view(),
        name='knowledge-sources-list'
    ),
    path(
        'knowledge/sources/<uuid:source_id>/',
        knowledge_views.KnowledgeSourceAPIView.as_view(),
        name='knowledge-sources-detail'
    ),

    # Document ingestion management
    path(
        'knowledge/ingestions/',
        knowledge_views.IngestionJobAPIView.as_view(),
        name='knowledge-ingestions-list'
    ),
    path(
        'knowledge/ingestions/<uuid:job_id>/',
        knowledge_views.IngestionJobAPIView.as_view(),
        name='knowledge-ingestions-detail'
    ),

    # Document management operations
    path(
        'knowledge/documents/<uuid:doc_id>/<str:action>/',
        knowledge_views.DocumentManagementAPIView.as_view(),
        name='knowledge-documents-action'
    ),

    # Advanced knowledge search with filtering
    path(
        'knowledge/search-advanced/',
        knowledge_views.KnowledgeSearchAPIView.as_view(),
        name='knowledge-search-advanced'
    ),

    # Document review workflow
    path(
        'knowledge/reviews/',
        knowledge_views.DocumentReviewAPIView.as_view(),
        name='knowledge-reviews'
    ),

    # Knowledge base statistics and monitoring
    path(
        'knowledge/stats/',
        knowledge_views.KnowledgeStatsAPIView.as_view(),
        name='knowledge-stats'
    ),

    # ========== TASK STATUS ENDPOINTS ==========
    path(
        'tasks/<str:task_id>/status/',
        views_phase2.get_task_status,
        name='task-status'
    ),

    # ========== ANALYTICS ENDPOINTS ==========
    # Funnel analytics (NEW - Phase 2.2.3)
    path('analytics/', include('apps.onboarding_api.urls_analytics')),

    # ========== DLQ ADMIN ENDPOINTS ==========
    # Dead Letter Queue management (NEW - Phase 2.1.4)
    path('admin/dlq/', include('apps.onboarding_api.urls_dlq_admin')),

    # ========== SESSION RECOVERY ENDPOINTS ==========
    # Session checkpoint and recovery (NEW - Phase 3.1)
    path('', include('apps.onboarding_api.urls_session_recovery')),

    # ========== ANALYTICS DASHBOARD ENDPOINTS ==========
    # Advanced analytics dashboard (NEW - Phase 3.2)
    path('dashboard/', include('apps.onboarding_api.urls_dashboard')),

    # ========== ADMIN/STAFF ENDPOINTS ==========
    path(
        'admin/knowledge/dashboard/',
        admin_views.KnowledgeManagementDashboard.as_view(),
        name='admin-knowledge-dashboard'
    ),
    path(
        'admin/rollout/dashboard/',
        admin_views.OnboardingRolloutDashboardView.as_view(),
        name='admin-rollout-dashboard'
    ),
    path(
        'admin/rollout/dashboard-data/',
        admin_views.get_rollout_dashboard_data,
        name='admin-rollout-dashboard-data'
    ),
    path(
        'admin/rollout/control/',
        admin_views.control_rollout_phase,
        name='admin-rollout-control'
    ),
    path(
        'admin/knowledge/embedding-progress/',
        admin_views.get_embedding_progress,
        name='admin-embedding-progress'
    ),
    path(
        'admin/knowledge/batch-embed/',
        admin_views.batch_embed_documents,
        name='admin-batch-embed'
    ),
    path(
        'admin/knowledge/freshness-check/',
        admin_views.trigger_freshness_check,
        name='admin-freshness-check'
    ),
    path(
        'admin/knowledge/invalidate-stale/',
        admin_views.invalidate_stale_knowledge,
        name='admin-invalidate-stale'
    ),
    path(
        'admin/metrics/',
        admin_views.SystemMetricsView.as_view(),
        name='admin-metrics'
    ),
    path(
        'admin/alerts/',
        admin_views.get_system_alerts,
        name='admin-alerts'
    ),
    path(
        'admin/costs/',
        admin_views.get_cost_analytics,
        name='admin-costs'
    ),
    path(
        'admin/analytics/export/',
        admin_views.export_conversation_analytics,
        name='admin-analytics-export'
    ),

    # ========== MONITORING AND HEALTH CHECK ENDPOINTS ==========
    path(
        'health/',
        monitoring_views.SystemHealthView.as_view(),
        name='system-health'
    ),
    path(
        'health/quick/',
        monitoring_views.QuickHealthView.as_view(),
        name='quick-health'
    ),
    path(
        'health/cache/',
        views.cache_health_check,
        name='cache-health-check'
    ),
    path(
        'health/logging/',
        views.logging_health_check,
        name='logging-health-check'
    ),
    path(
        'health/system/',
        views.system_health_monitoring,
        name='system-health-monitoring'
    ),
    path(
        'health/reset-degradations/',
        views.reset_degradations,
        name='reset-degradations'
    ),
    path(
        'health/degradations/',
        views.degradation_status,
        name='degradation-status'
    ),
    path(
        'metrics/',
        monitoring_views.PerformanceMetricsView.as_view(),
        name='performance-metrics'
    ),
    path(
        'alerts/',
        monitoring_views.SystemAlertsView.as_view(),
        name='system-alerts'
    ),
    path(
        'resources/',
        monitoring_views.get_resource_utilization,
        name='resource-utilization'
    ),
    path(
        'maintenance/',
        monitoring_views.trigger_maintenance_mode,
        name='maintenance-toggle'
    ),
    path(
        'maintenance/status/',
        monitoring_views.maintenance_status,
        name='maintenance-status'
    ),
    path(
        'config/status/',
        monitoring_views.ConfigurationStatusView.as_view(),
        name='configuration-status'
    ),

    # ========== UI ENDPOINTS ==========
    path(
        'ui/',
        views_ui.conversational_onboarding_ui,
        name='conversational-ui'
    ),
    path(
        'ui/config/',
        views_ui.ui_config,
        name='ui-config'
    ),

    # ========== UI COMPATIBILITY LAYER ==========
    # These endpoints bridge the gap between frontend expectations and backend API
    path(
        'conversation/start/ui/',
        views_ui_compat.UICompatConversationStartView.as_view(),
        name='conversation-start-ui'
    ),
    path(
        'conversation/process/',
        views_ui_compat.UICompatConversationProcessView.as_view(),
        name='conversation-process-ui'
    ),
    path(
        'task-status/<str:task_id>/',
        views_ui_compat.UICompatTaskStatusView.as_view(),
        name='task-status-ui'
    ),
    path(
        'conversation/<uuid:conversation_id>/status/ui/',
        views_ui_compat.ui_compat_conversation_status,
        name='conversation-status-ui'
    ),

    # ========== DOCUMENTATION ENDPOINTS ==========
    path(
        'documentation/logging/',
        views.logging_documentation,
        name='logging-documentation'
    ),

    # Include router URLs
    path('', include(router.urls)),
]

# ========== API DOCUMENTATION (Optional - requires drf-yasg) ==========
# Only add these URLs if drf-yasg is installed
if schema_view is not None:
    urlpatterns += [
        re_path(r'^swagger(?P<format>\.json|\.yaml)$',
                schema_view.without_ui(cache_timeout=0),
                name='schema-json'),
        re_path(r'^swagger/$',
                schema_view.with_ui('swagger', cache_timeout=0),
                name='schema-swagger-ui'),
        re_path(r'^redoc/$',
                schema_view.with_ui('redoc', cache_timeout=0),
                name='schema-redoc'),
    ]