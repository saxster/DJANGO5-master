"""
Assets API URLs (v1)

Domain: /api/v1/assets/

Handles asset tracking, geofences, locations, and maintenance.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import viewsets when they're created
# from apps.activity.api import views as asset_views
# from apps.attendance.api import views as geo_views

app_name = 'assets'

router = DefaultRouter()
# router.register(r'', asset_views.AssetViewSet, basename='assets')
# router.register(r'geofences', geo_views.GeofenceViewSet, basename='geofences')
# router.register(r'locations', asset_views.LocationViewSet, basename='locations')

urlpatterns = [
    # Router URLs (CRUD operations)
    path('', include(router.urls)),

    # Additional endpoints (to be implemented)
    # path('geofences/<int:pk>/validate/', geo_views.GeofenceValidateView.as_view(), name='geofence-validate'),
]
