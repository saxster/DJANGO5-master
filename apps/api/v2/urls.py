"""
API v2 URL Configuration

Enhanced API with:
- legacy API mutations
- Real-time push
- ML predictions
- Cross-device sync
"""

from django.urls import path, include
from .views import sync_views, ml_views, device_views

app_name = 'api_v2'

urlpatterns = [
    # Sync endpoints (enhanced)
    path('sync/voice/', sync_views.SyncVoiceView.as_view(), name='sync-voice'),
    path('sync/batch/', sync_views.SyncBatchView.as_view(), name='sync-batch'),

    # ML predictions
    path('predict/conflict/', ml_views.ConflictPredictionView.as_view(), name='predict-conflict'),

    # Device management
    path('devices/', device_views.DeviceListView.as_view(), name='device-list'),
    path('devices/register/', device_views.DeviceRegisterView.as_view(), name='device-register'),
    path('devices/<str:device_id>/', device_views.DeviceDetailView.as_view(), name='device-detail'),
    path('devices/<str:device_id>/sync-state/', device_views.DeviceSyncStateView.as_view(), name='device-sync-state'),

    # Version info
    path('version/', sync_views.VersionInfoView.as_view(), name='version-info'),
]