"""
API v2 URL Configuration

Enhanced API with:
- legacy API mutations
- Real-time push
- ML predictions
- Cross-device sync
"""

from django.urls import path, include
from .views import sync_views, ml_views, device_views, telemetry_views

app_name = 'api_v2'

urlpatterns = [
    # Authentication (V2)
    path('auth/', include('apps.api.v2.auth_urls', namespace='auth')),

    # People management (V2)
    path('people/', include('apps.api.v2.people_urls', namespace='people')),

    # Help Desk (V2)
    path('helpdesk/', include('apps.api.v2.helpdesk_urls', namespace='helpdesk')),

    # Calendar (V2)
    path('calendar/', include('apps.api.v2.calendar_urls', namespace='calendar')),

    # Reports (V2)
    path('reports/', include('apps.api.v2.reports_urls', namespace='reports')),

    # Wellness & Journal (V2)
    path('wellness/', include('apps.api.v2.wellness_urls', namespace='wellness')),

    # Command Center (V2) - Scope, Alerts, Overview, Saved Views
    path('', include('apps.api.v2.command_center_urls')),

    # HelpBot (V2)
    path('helpbot/', include('apps.api.v2.helpbot_urls', namespace='helpbot')),

    # Telemetry (V2) - Kotlin SDK integration
    path('telemetry/stream-events/batch', telemetry_views.TelemetryBatchView.as_view(), name='telemetry-batch'),

    # Sync endpoints (enhanced)
    path('sync/voice/', sync_views.SyncVoiceView.as_view(), name='sync-voice'),
    path('sync/batch/', sync_views.SyncBatchView.as_view(), name='sync-batch'),

    # ML predictions
    path('predict/conflict/', ml_views.ConflictPredictionView.as_view(), name='predict-conflict'),

    # ML training feedback
    path('ml-training/corrections/', ml_views.OCRCorrectionView.as_view(), name='ml-training-corrections'),

    # Device management
    path('devices/', device_views.DeviceListView.as_view(), name='device-list'),
    path('devices/register/', device_views.DeviceRegisterView.as_view(), name='device-register'),
    path('devices/<str:device_id>/', device_views.DeviceDetailView.as_view(), name='device-detail'),
    path('devices/<str:device_id>/sync-state/', device_views.DeviceSyncStateView.as_view(), name='device-sync-state'),

    # Version info
    path('version/', sync_views.VersionInfoView.as_view(), name='version-info'),
]
