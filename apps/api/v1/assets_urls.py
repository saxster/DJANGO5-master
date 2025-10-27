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
from apps.attendance.api.viewsets import GeofenceViewSet

app_name = 'assets'

router = DefaultRouter()
router.register(r'geofences', GeofenceViewSet, basename='geofences')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes custom actions:
    # - POST /geofences/validate/
    path('', include(router.urls)),
]
