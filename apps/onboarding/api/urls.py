"""
URL configuration for Onboarding Admin Configuration API

Provides REST API endpoints for:
- Business Units
- Shifts
- Geofences
- Contracts
- Type Assists
- Clients
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.onboarding.api.viewsets.business_unit_viewset import BusinessUnitViewSet
from apps.onboarding.api.viewsets.geofence_viewset import GeofenceViewSet
from apps.onboarding.api.viewsets.contract_viewset import ContractViewSet

app_name = 'onboarding_admin_api'

# DRF Router for ViewSets
router = DefaultRouter()

# Register ViewSets
router.register(r'business-units', BusinessUnitViewSet, basename='business-unit')
router.register(r'shifts', BusinessUnitViewSet, basename='shift')  # Uses BusinessUnitViewSet.shifts() action
router.register(r'geofences', GeofenceViewSet, basename='geofence')
router.register(r'contracts', ContractViewSet, basename='contract')

# Additional admin config endpoints can use BusinessUnitViewSet actions:
# - GET /api/v1/admin/config/locations/ → BusinessUnitViewSet.locations()
# - GET /api/v1/admin/config/sites/ → BusinessUnitViewSet (default list)
# - GET /api/v1/admin/config/shifts/ → BusinessUnitViewSet.shifts()
# - GET /api/v1/admin/config/groups/ → BusinessUnitViewSet (add action if needed)
# - GET /api/v1/admin/config/type-assist/ → BusinessUnitViewSet (add action if needed)

urlpatterns = [
    path('', include(router.urls)),
]
