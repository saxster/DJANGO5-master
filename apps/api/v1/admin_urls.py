"""
Admin API URLs (v1)

Domain: /api/v1/admin/

Handles business configuration, locations, shifts, and client verification.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.client_onboarding.api.viewsets import BusinessUnitViewSet

app_name = 'admin'

router = DefaultRouter()

# Business unit and admin configuration (legacy API replacement)
router.register(r'config', BusinessUnitViewSet, basename='admin-config')

urlpatterns = [
    # Admin configuration endpoints (replace legacy API):
    # - config/locations/ → get_locations
    # - config/sites/ → getsitelist
    # - config/shifts/ → get_shifts
    # - config/groups/ → get_groupsmodifiedafter
    # - config/clients/verify/ → verifyclient
    path('', include(router.urls)),
]
