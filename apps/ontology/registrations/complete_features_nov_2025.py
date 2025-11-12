"""Complete ontology registration for all 28 strategic features - November 2025."""

from apps.ontology.registry import OntologyRegistry

import logging
logger = logging.getLogger(__name__)



def register_all_28_features():
    """Register all 28 implemented strategic features."""
    
    all_features = [
        # PHASE 1: Foundation (3 features)
        {"qualified_name": "apps.noc.services.alert_rules_service.AlertRulesService", "type": "service", "domain": "noc.alert_suppression", "purpose": "Alert suppression with flapping, deduplication, burst detection", "tags": ["alerts", "noise-reduction"], "criticality": "high", "revenue": "Platform improvement"},
        {"qualified_name": "apps.reports.services.dar_service.DARService", "type": "service", "domain": "reports.compliance", "purpose": "Daily Activity Report generation for shift closeout", "tags": ["compliance", "reports"], "criticality": "high", "revenue": "$50-100/site"},
        {"qualified_name": "apps.integrations.services.webhook_dispatcher.WebhookDispatcher", "type": "service", "domain": "integrations.webhooks", "purpose": "Outbound webhook dispatcher with HMAC signatures and retry", "tags": ["webhooks", "integrations"], "criticality": "high", "revenue": "$100-200/client"},
        
        # PHASE 2: Premium (3 features)
        {"qualified_name": "apps.dashboard.services.command_center_service.CommandCenterService", "type": "service", "domain": "dashboard.realtime", "purpose": "Real-time command center with 6 data sources", "tags": ["websocket", "dashboard", "premium"], "criticality": "high", "revenue": "Premium tier"},
        {"qualified_name": "background_tasks.sla_prevention_tasks.predict_sla_breaches_task", "type": "celery_task", "domain": "helpdesk.sla", "purpose": "Predictive SLA breach prevention with auto-escalation", "tags": ["sla", "predictive", "ml"], "criticality": "high", "revenue": "$75-150/site"},
        {"qualified_name": "apps.monitoring.services.device_health_service.DeviceHealthService", "type": "service", "domain": "monitoring.iot", "purpose": "Device health scoring and proactive alerts", "tags": ["iot", "health", "predictive"], "criticality": "high", "revenue": "$2-5/device"},
        
        # PHASE 3: AI Intelligence (3 features)
        {"qualified_name": "apps.y_helpdesk.services.kb_suggester.KBSuggester", "type": "service", "domain": "helpdesk.knowledge", "purpose": "TF-IDF knowledge base article suggestions", "tags": ["ai", "helpdesk", "kb"], "criticality": "medium", "revenue": "Productivity"},
        {"qualified_name": "apps.noc.services.playbook_engine.PlaybookEngine", "type": "service", "domain": "noc.soar", "purpose": "SOAR automation with playbook execution", "tags": ["soar", "automation"], "criticality": "high", "revenue": "$50-100/site"},
        {"qualified_name": "apps.scheduler.services.pm_optimizer_service.PMOptimizerService", "type": "service", "domain": "scheduler.optimization", "purpose": "Adaptive PM scheduling from telemetry", "tags": ["pm", "optimization", "predictive"], "criticality": "medium", "revenue": "Efficiency"},
        
        # PHASE 4: Enterprise (3 features)
        {"qualified_name": "apps.peoples.sso.saml_backend.SAMLAuthBackend", "type": "auth_backend", "domain": "authentication.sso", "purpose": "SAML 2.0 authentication with JIT provisioning", "tags": ["sso", "saml", "enterprise"], "criticality": "high", "revenue": "Deal enabler"},
        {"qualified_name": "apps.attendance.services.staffing_forecaster.StaffingForecaster", "type": "service", "domain": "attendance.forecasting", "purpose": "Workforce demand prediction by site/shift", "tags": ["forecasting", "staffing"], "criticality": "medium", "revenue": "$50-100/site"},
        {"qualified_name": "apps.reports.services.compliance_pack_service.CompliancePackService", "type": "service", "domain": "reports.compliance", "purpose": "Monthly compliance audit pack generation", "tags": ["compliance", "audit", "psara"], "criticality": "high", "revenue": "$100-200/client"},
        
        # PHASE 5: UX Polish (3 features)
        {"qualified_name": "apps.reports.services.executive_scorecard_service.ExecutiveScoreCardService", "type": "service", "domain": "reports.executive", "purpose": "Enhanced scorecards with MoM deltas and risks", "tags": ["executive", "scorecard"], "criticality": "high", "revenue": "$200-500/client"},
        {"qualified_name": "apps.service.views.client_portal.ClientPortalView", "type": "view", "domain": "portal.client", "purpose": "Read-only client portal with time-bound tokens", "tags": ["portal", "client"], "criticality": "medium", "revenue": "Transparency"},
        {"qualified_name": "apps.y_helpdesk.services.reply_macros.ReplyMacroService", "type": "service", "domain": "helpdesk.productivity", "purpose": "Template replies with variable substitution", "tags": ["helpdesk", "macros"], "criticality": "low", "revenue": "Productivity"},
        
        # PHASE 6: Data Utilization (10 features)
        {"qualified_name": "apps.activity.services.tour_optimization_service.TourOptimizationService", "type": "service", "domain": "tours.optimization", "purpose": "Route optimization from checkpoint analysis", "tags": ["tours", "optimization"], "criticality": "medium", "revenue": "Efficiency"},
        {"qualified_name": "apps.attendance.services.policy_enforcer.AttendancePolicyEnforcer", "type": "service", "domain": "attendance.security", "purpose": "2-factor attendance (geofence+face+QR)", "tags": ["security", "attendance", "2fa"], "criticality": "high", "revenue": "Fraud prevention"},
        {"qualified_name": "apps.reports.services.data_export_service.DataExportService", "type": "service", "domain": "reports.export", "purpose": "Self-service data export (CSV/JSON)", "tags": ["export", "gdpr"], "criticality": "medium", "revenue": "Compliance"},
        {"qualified_name": "apps.noc.services.alert_handler.AlertHandler", "type": "service", "domain": "noc.triage", "purpose": "AI-powered alert priority scoring and routing", "tags": ["ai", "triage", "alerts"], "criticality": "high", "revenue": "Premium"},
        {"qualified_name": "apps.scheduler.services.exception_calendar.ExceptionCalendarService", "type": "service", "domain": "scheduler.calendar", "purpose": "Holiday and blackout window management", "tags": ["scheduler", "calendar"], "criticality": "low", "revenue": "UX"},
        {"qualified_name": "apps.core.services.notification_preferences_service.NotificationPreferencesService", "type": "service", "domain": "notifications.preferences", "purpose": "Per-user notification channel preferences", "tags": ["notifications", "preferences"], "criticality": "low", "revenue": "UX"},
        {"qualified_name": "apps.mqtt.services.environment_anomaly_service.EnvironmentAnomalyService", "type": "service", "domain": "monitoring.environment", "purpose": "Temperature/humidity anomaly detection", "tags": ["sensors", "hvac", "anomalies"], "criticality": "medium", "revenue": "Facility health"},
        {"qualified_name": "apps.work_order_management.services.vendor_performance_service.VendorPerformanceService", "type": "service", "domain": "vendors.performance", "purpose": "Vendor quality scoring with sentiment analysis", "tags": ["vendors", "performance", "sentiment"], "criticality": "medium", "revenue": "Quality"},
        {"qualified_name": "apps.core.services.audit_mining_service.AuditMiningService", "type": "service", "domain": "security.audit", "purpose": "Suspicious admin activity detection", "tags": ["security", "audit", "anomaly"], "criticality": "high", "revenue": "Security"},
        {"qualified_name": "apps.attendance.services.sos_review_service.SOSReviewService", "type": "service", "domain": "attendance.sos", "purpose": "Post-incident SOS review report generation", "tags": ["sos", "incident", "review"], "criticality": "medium", "revenue": "Safety"},
        
        # METER INTELLIGENCE (3 features)
        {"qualified_name": "apps.activity.services.tank_forecasting_service.TankForecastingService", "type": "service", "domain": "meters.forecasting", "purpose": "Predictive tank level forecasting and refill alerts", "tags": ["meters", "forecasting", "tanks"], "criticality": "high", "revenue": "$150-300/site"},
        {"qualified_name": "apps.activity.services.theft_leak_detection_service.TheftLeakDetectionService", "type": "service", "domain": "meters.fraud", "purpose": "Fuel theft and leak detection", "tags": ["meters", "theft", "security"], "criticality": "high", "revenue": "$15K-25K/year savings"},
        {"qualified_name": "apps.activity.services.cost_optimization_service.CostOptimizationService", "type": "service", "domain": "meters.cost", "purpose": "Utility cost optimization and executive dashboards", "tags": ["meters", "cost", "analytics"], "criticality": "high", "revenue": "$150-300/site"},
    ]
    
    for feature in all_features:
        OntologyRegistry.register(feature["qualified_name"], feature)
    
    return len(all_features)


if __name__ != "__main__":
    count = register_all_28_features()
    logger.info(f"Registered {count} strategic features in ontology")
