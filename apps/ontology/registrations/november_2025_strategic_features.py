"""
import logging
logger = logging.getLogger(__name__)
Ontology registrations for November 6, 2025 strategic features.

This module registers all components from the Strategic Enhancement Initiative:
- Alert suppression and noise reduction (3 components)
- Daily Activity Reports (2 components)
- Outbound webhooks and integrations (5 components)
- Future features (documented but not yet implemented)

Total registered: 10 components (Phase 1)
Planned: 25+ additional components (Phases 2-6)
"""

from apps.ontology.registry import OntologyRegistry


def register_strategic_features_phase1():
    """Register Phase 1 strategic features (Alert Suppression, DAR, Webhooks)."""

    features = [
        # ===================================================================
        # ALERT SUPPRESSION & NOISE REDUCTION (3 components)
        # ===================================================================

        {
            "qualified_name": "apps.noc.services.alert_rules_service.AlertRulesService",
            "type": "service",
            "domain": "noc.alert_management",
            "purpose": "Alert suppression, deduplication, and noise reduction service with flapping detection, burst detection, and maintenance windows",
            "tags": ["alerts", "suppression", "noise-reduction", "premium", "operations"],
            "criticality": "high",
            "implements": [
                "should_suppress_alert",
                "set_maintenance_window",
                "clear_maintenance_window",
                "get_suppression_stats",
                "reset_flap_detection"
            ],
            "dependencies": [
                "django.core.cache",
                "apps.core.constants.datetime_constants"
            ],
            "metrics": {
                "target_noise_reduction": "40-60%",
                "flap_threshold": 3,
                "dedupe_window_seconds": 600,
                "burst_threshold": 5
            }
        },

        {
            "qualified_name": "apps.noc.services.alert_rules_service.AlertRulesService._is_flapping",
            "type": "method",
            "domain": "noc.alert_management",
            "purpose": "Detect flapping alerts (3+ state changes within 5 minutes) using Redis sorted sets",
            "tags": ["alerts", "flapping", "detection", "redis"],
            "criticality": "high",
            "algorithm": "Sliding window with Redis sorted set, 5-minute window, 3-change threshold"
        },

        {
            "qualified_name": "background_tasks.alert_suppression_tasks.monitor_suppression_effectiveness",
            "type": "celery_task",
            "domain": "noc.monitoring",
            "purpose": "Monitor alert suppression effectiveness hourly and alert if thresholds breached (too high or too low suppression)",
            "tags": ["celery", "monitoring", "alerts", "metrics"],
            "criticality": "medium",
            "schedule": "hourly",
            "retry": {
                "max_retries": 3,
                "retry_delay_seconds": 60
            }
        },

        # ===================================================================
        # DAILY ACTIVITY REPORTS (2 components)
        # ===================================================================

        {
            "qualified_name": "apps.reports.services.dar_service.DARService",
            "type": "service",
            "domain": "reports.compliance",
            "purpose": "Generate comprehensive Daily Activity Reports (DAR) for security shift closeout with incidents, tours, SOS, device events, and exceptions",
            "tags": ["reports", "compliance", "security", "shift-management", "premium"],
            "criticality": "high",
            "implements": [
                "generate_dar",
                "_get_shift_summary",
                "_get_incidents",
                "_get_tours_completed",
                "_get_sos_alerts",
                "_get_device_events",
                "_get_attendance_exceptions"
            ],
            "dependencies": [
                "apps.attendance.models",
                "apps.activity.models",
                "apps.scheduler.models"
            ],
            "revenue_impact": "$50-100/month per site",
            "compliance_standards": ["PSARA", "industry-standard shift reporting"]
        },

        {
            "qualified_name": "apps.reports.report_designs.daily_activity_report.html",
            "type": "template",
            "domain": "reports.compliance",
            "purpose": "Professional PDF template for Daily Activity Reports with client branding, shift summary, incidents, tours, SOS alerts, and signature blocks",
            "tags": ["template", "pdf", "compliance", "weasyprint"],
            "criticality": "high",
            "features": [
                "client_logo_support",
                "shift_summary_statistics",
                "incident_table",
                "tour_completion_progress_bars",
                "sos_alert_section",
                "device_events_section",
                "attendance_exceptions",
                "supervisor_notes",
                "signature_blocks"
            ]
        },

        # ===================================================================
        # OUTBOUND WEBHOOKS & INTEGRATIONS (5 components)
        # ===================================================================

        {
            "qualified_name": "apps.integrations.services.webhook_dispatcher.WebhookDispatcher",
            "type": "service",
            "domain": "integrations.webhooks",
            "purpose": "Dispatch events to configured webhooks with HMAC signatures, retry logic, dead-letter queue, and rate limiting",
            "tags": ["integrations", "webhooks", "enterprise", "automation", "premium"],
            "criticality": "high",
            "implements": [
                "dispatch_event",
                "verify_webhook_signature",
                "get_dead_letter_queue_entries",
                "retry_dead_letter_entry"
            ],
            "dependencies": [
                "requests",
                "django.core.cache",
                "apps.onboarding.models.TypeAssist"
            ],
            "security": {
                "signature_algorithm": "HMAC-SHA256",
                "rate_limit": "100/minute per tenant",
                "timeout_seconds": "(5, 30)"
            },
            "reliability": {
                "max_retries": 3,
                "retry_delays_seconds": [60, 300, 900],
                "dead_letter_queue": True
            },
            "revenue_impact": "$100-200/month per client"
        },

        {
            "qualified_name": "apps.integrations.services.webhook_dispatcher.WebhookDispatcher._generate_signature",
            "type": "method",
            "domain": "integrations.security",
            "purpose": "Generate HMAC-SHA256 signature for webhook payload verification",
            "tags": ["security", "hmac", "signatures", "webhooks"],
            "criticality": "high",
            "algorithm": "HMAC-SHA256 with sorted JSON keys"
        },

        {
            "qualified_name": "apps.integrations.services.teams_connector.TeamsConnector",
            "type": "service",
            "domain": "integrations.teams",
            "purpose": "Send notifications to Microsoft Teams channels via incoming webhooks using Adaptive Cards format",
            "tags": ["integrations", "microsoft-teams", "notifications", "enterprise"],
            "criticality": "medium",
            "implements": [
                "send_alert_notification",
                "send_sos_notification",
                "send_sla_risk_notification"
            ],
            "dependencies": [
                "requests",
                "apps.integrations.services.webhook_dispatcher"
            ],
            "supported_card_types": [
                "alert_card",
                "sos_card",
                "sla_risk_card"
            ]
        },

        {
            "qualified_name": "apps.integrations.apps.IntegrationsConfig",
            "type": "app_config",
            "domain": "integrations",
            "purpose": "Django app configuration for external integrations (webhooks, SSO, third-party APIs)",
            "tags": ["django-app", "integrations", "configuration"],
            "criticality": "medium",
            "app_label": "integrations",
            "verbose_name": "External Integrations"
        },

        {
            "qualified_name": "apps.integrations.models",
            "type": "module",
            "domain": "integrations.configuration",
            "purpose": "Integration configuration storage using TypeAssist.other_data for webhook, Teams, and Slack configurations",
            "tags": ["configuration", "typeassist", "schema-less"],
            "criticality": "medium",
            "configuration_structure": {
                "webhooks": "List of webhook configs with URL, events, secret",
                "teams": "Teams webhook URL and event subscriptions",
                "slack": "Slack webhook URL and channel config"
            },
            "note": "No database models - uses TypeAssist.other_data for flexibility"
        },
    ]

    # Register all features
    for feature in features:
        OntologyRegistry.register(
            qualified_name=feature["qualified_name"],
            metadata=feature
        )

    return len(features)


def register_strategic_features_phase2_blueprint():
    """
    Blueprint registrations for Phase 2 features (not yet implemented).

    These registrations document planned features for:
    - Real-Time Command Center
    - Predictive SLA Prevention
    - Device Health & Assurance
    """

    blueprint_features = [
        # Phase 2 features to be implemented
        {
            "qualified_name": "apps.dashboard.services.command_center_service.CommandCenterService",
            "type": "service",
            "domain": "dashboard.command_center",
            "purpose": "Real-time operational intelligence aggregation for unified command center view",
            "tags": ["real-time", "websocket", "dashboard", "premium", "planned"],
            "status": "PLANNED",
            "phase": 2,
            "estimated_effort_days": 3
        },

        {
            "qualified_name": "apps.y_helpdesk.services.sla_alert_service.SLAAlertService",
            "type": "service",
            "domain": "helpdesk.sla_prevention",
            "purpose": "Proactive SLA breach prevention with predictive alerts and auto-escalation",
            "tags": ["sla", "predictive", "ml", "premium", "planned"],
            "status": "PLANNED",
            "phase": 2,
            "estimated_effort_days": 2,
            "revenue_impact": "$75-150/month per site"
        },

        {
            "qualified_name": "apps.monitoring.services.device_health_service.DeviceHealthService",
            "type": "service",
            "domain": "monitoring.device_health",
            "purpose": "Device health scoring, leaderboards, and proactive maintenance alerts",
            "tags": ["iot", "monitoring", "predictive", "premium", "planned"],
            "status": "PLANNED",
            "phase": 2,
            "estimated_effort_days": 3,
            "revenue_impact": "$2-5/device/month ($400-1000/site)"
        },

        # Phase 3-6 features (abbreviated)
        {
            "qualified_name": "apps.y_helpdesk.services.kb_suggester.KBSuggester",
            "type": "service",
            "domain": "helpdesk.knowledge_base",
            "purpose": "TF-IDF based knowledge base article suggestions for tickets",
            "tags": ["ai", "helpdesk", "knowledge-base", "planned"],
            "status": "PLANNED",
            "phase": 3,
            "estimated_effort_days": 2
        },

        {
            "qualified_name": "apps.scheduler.services.pm_optimizer_service.PMOptimizerService",
            "type": "service",
            "domain": "scheduler.pm_optimization",
            "purpose": "Adaptive preventive maintenance scheduling based on telemetry and failure prediction",
            "tags": ["scheduler", "predictive", "optimization", "planned"],
            "status": "PLANNED",
            "phase": 3,
            "estimated_effort_days": 3
        },

        {
            "qualified_name": "apps.peoples.sso.jit_provisioning.JITProvisioningService",
            "type": "service",
            "domain": "authentication.sso",
            "purpose": "Just-in-time user provisioning from SAML/OIDC identity providers",
            "tags": ["sso", "enterprise", "authentication", "planned"],
            "status": "PLANNED",
            "phase": 4,
            "estimated_effort_days": 3,
            "business_impact": "Enterprise deal enabler"
        },
    ]

    # Register blueprints (for documentation and planning)
    for feature in blueprint_features:
        OntologyRegistry.register(
            qualified_name=feature["qualified_name"],
            metadata=feature
        )

    return len(blueprint_features)


def register_meter_intelligence_features():
    """Register Meter Intelligence Platform features (Phase 7)."""

    features = [
        {
            "qualified_name": "apps.activity.services.tank_forecasting_service.TankForecastingService",
            "type": "service",
            "domain": "utilities.tank_management",
            "purpose": "Predict when tanks will be empty and generate proactive refill alerts based on consumption trends",
            "tags": ["meter-intelligence", "predictive", "tanks", "premium", "utilities"],
            "criticality": "high",
            "implements": [
                "predict_empty_date",
                "create_refill_alert",
                "get_all_tank_forecasts"
            ],
            "algorithm": "Linear regression on 30-day consumption history with trend adjustment",
            "metrics": {
                "forecast_accuracy_target": "85%",
                "buffer_days": 3,
                "confidence_threshold": 0.7
            },
            "revenue_impact": "$150-300/month per site (Utility Intelligence Pack)",
            "client_savings": "$8,000/year (prevent stockouts)"
        },

        {
            "qualified_name": "apps.activity.services.theft_leak_detection_service.TheftLeakDetectionService",
            "type": "service",
            "domain": "utilities.fraud_detection",
            "purpose": "Detect fuel theft, pilferage, and water/diesel leaks through sudden drops and gradual consumption anomalies",
            "tags": ["meter-intelligence", "fraud", "theft", "leaks", "security", "premium"],
            "criticality": "high",
            "implements": [
                "detect_sudden_drop",
                "detect_gradual_leak",
                "create_theft_leak_alert"
            ],
            "detection_methods": {
                "sudden_drop": "15%+ drop = potential theft",
                "gradual_leak": "10%+ excess consumption over baseline",
                "off_hours": "Night consumption when site closed"
            },
            "revenue_impact": "$150-300/month per site (Utility Intelligence Pack)",
            "client_savings": "$15,000-25,000/year (theft/leak prevention)"
        },

        {
            "qualified_name": "apps.activity.services.cost_optimization_service.CostOptimizationService",
            "type": "service",
            "domain": "utilities.cost_optimization",
            "purpose": "Analyze utility costs, identify peak usage inefficiencies, and generate CFO-ready executive dashboards with savings opportunities",
            "tags": ["meter-intelligence", "cost-optimization", "analytics", "executive", "premium"],
            "criticality": "high",
            "implements": [
                "analyze_peak_usage",
                "generate_cost_dashboard",
                "track_budget_variance"
            ],
            "cost_multipliers": {
                "peak_hours": "9AM-9PM at 2.5x cost",
                "off_peak_hours": "9PM-9AM at 1.0x cost"
            },
            "revenue_impact": "$150-300/month per site (Utility Intelligence Pack)",
            "client_savings": "$12,500-42,000/year (20-30% electricity savings)"
        },

        {
            "qualified_name": "background_tasks.meter_intelligence_tasks.forecast_all_tanks_task",
            "type": "celery_task",
            "domain": "utilities.forecasting",
            "purpose": "Daily tank level forecasting for all diesel/fuel/gas/water tanks with proactive refill alerts",
            "tags": ["celery", "meter-intelligence", "forecasting", "tanks"],
            "criticality": "high",
            "schedule": "daily at 6:00 AM",
            "retry": {
                "max_retries": 3,
                "retry_delay_seconds": 300
            }
        },

        {
            "qualified_name": "background_tasks.meter_intelligence_tasks.detect_theft_leaks_task",
            "type": "celery_task",
            "domain": "utilities.fraud_detection",
            "purpose": "Hourly theft and leak detection across all fuel and water meters",
            "tags": ["celery", "meter-intelligence", "fraud", "security"],
            "criticality": "high",
            "schedule": "hourly",
            "detection_coverage": "Diesel, Fuel, Water meters"
        },

        {
            "qualified_name": "background_tasks.meter_intelligence_tasks.generate_cost_dashboards_task",
            "type": "celery_task",
            "domain": "utilities.cost_analytics",
            "purpose": "Weekly executive cost dashboard generation with optimization opportunities",
            "tags": ["celery", "meter-intelligence", "analytics", "executive"],
            "criticality": "medium",
            "schedule": "weekly on Monday at 9:00 AM"
        },
    ]

    for feature in features:
        OntologyRegistry.register(
            qualified_name=feature["qualified_name"],
            metadata=feature
        )

    return len(features)


def register_all_strategic_features():
    """Register all strategic features (implemented and planned)."""

    phase1_count = register_strategic_features_phase1()
    blueprint_count = register_strategic_features_phase2_blueprint()
    meter_count = register_meter_intelligence_features()

    return {
        "phase1_implemented": phase1_count,
        "phase2_6_planned": blueprint_count,
        "meter_intelligence": meter_count,
        "total_registered": phase1_count + blueprint_count + meter_count
    }


# Auto-register when module imported
if __name__ != "__main__":
    register_all_strategic_features()
