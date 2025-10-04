"""
NOC URL Configuration for REST API Endpoints.

Complete REST API routing for NOC Phases 1-6 implementation.
Follows Django URL patterns with CSRF protection and DRF compatibility.
"""

from django.urls import path
from .monitoring import noc_health_check
from .views import (
    overview_views, drilldown_views, alert_views, incident_views,
    maintenance_views, map_views, analytics_views, export_views, ui_views,
    view_config_views, api_key_views
)

app_name = 'noc'

urlpatterns = [
    # UI views
    path('', ui_views.noc_dashboard_view, name='dashboard'),
    path('incidents/', ui_views.noc_incidents_view, name='incidents'),
    path('maintenance/', ui_views.noc_maintenance_view, name='maintenance'),

    # Health check
    path('health/', noc_health_check, name='health'),

    # Dashboard data
    path('overview/', overview_views.NOCOverviewView.as_view(), name='overview'),
    path('drilldown/', drilldown_views.NOCDrilldownView.as_view(), name='drilldown'),

    # Alert management
    path('alerts/', alert_views.NOCAlertListView.as_view(), name='alert-list'),
    path('alerts/<int:pk>/', alert_views.NOCAlertDetailView.as_view(), name='alert-detail'),
    path('alerts/<int:pk>/ack/', alert_views.noc_alert_acknowledge, name='alert-acknowledge'),
    path('alerts/<int:pk>/assign/', alert_views.noc_alert_assign, name='alert-assign'),
    path('alerts/<int:pk>/escalate/', alert_views.noc_alert_escalate, name='alert-escalate'),
    path('alerts/<int:pk>/resolve/', alert_views.noc_alert_resolve, name='alert-resolve'),
    path('alerts/bulk-action/', alert_views.noc_alert_bulk_action, name='alert-bulk-action'),

    # Incident management
    path('incidents/', incident_views.NOCIncidentListCreateView.as_view(), name='incident-list-create'),
    path('incidents/<int:pk>/', incident_views.NOCIncidentDetailView.as_view(), name='incident-detail'),
    path('incidents/<int:pk>/assign/', incident_views.noc_incident_assign, name='incident-assign'),
    path('incidents/<int:pk>/resolve/', incident_views.noc_incident_resolve, name='incident-resolve'),

    # Maintenance windows
    path('maintenance/', maintenance_views.MaintenanceWindowListCreateView.as_view(), name='maintenance-list-create'),
    path('maintenance/<int:pk>/', maintenance_views.MaintenanceWindowDetailView.as_view(), name='maintenance-detail'),

    # Visualization
    path('map-data/', map_views.NOCMapDataView.as_view(), name='map-data'),

    # Analytics
    path('analytics/trends/', analytics_views.NOCAnalyticsTrendsView.as_view(), name='analytics-trends'),
    path('analytics/mttr/', analytics_views.NOCMTTRAnalyticsView.as_view(), name='analytics-mttr'),

    # Data export (Phase 3)
    path('export/alerts/', export_views.NOCExportAlertsView.as_view(), name='export-alerts'),
    path('export/incidents/', export_views.NOCExportIncidentsView.as_view(), name='export-incidents'),
    path('export/audit/', export_views.NOCExportAuditLogView.as_view(), name='export-audit'),

    # Saved views (Phase 6)
    path('views/', view_config_views.NOCSavedViewListCreateView.as_view(), name='view-list-create'),
    path('views/<int:pk>/', view_config_views.NOCSavedViewDetailView.as_view(), name='view-detail'),
    path('views/<int:pk>/set-default/', view_config_views.set_default_view, name='view-set-default'),
    path('views/<int:pk>/share/', view_config_views.share_view, name='view-share'),
    path('views/<int:pk>/clone/', view_config_views.clone_view, name='view-clone'),

    # API key management (Phase 6)
    path('api-keys/', api_key_views.NOCAPIKeyListCreateView.as_view(), name='api-key-list-create'),
    path('api-keys/<int:pk>/', api_key_views.NOCAPIKeyDetailView.as_view(), name='api-key-detail'),
    path('api-keys/<int:pk>/rotate/', api_key_views.rotate_api_key, name='api-key-rotate'),
    path('api-keys/<int:pk>/usage/', api_key_views.api_key_usage_stats, name='api-key-usage'),
]