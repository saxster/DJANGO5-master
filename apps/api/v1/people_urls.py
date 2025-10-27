"""
People Management API URLs (v1)

Domain: /api/v1/people/

Handles user management, profiles, capabilities, and organizational hierarchy.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.peoples.api.viewsets import PeopleViewSet

app_name = 'people'

router = DefaultRouter()
router.register(r'', PeopleViewSet, basename='people')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes: list, create, retrieve, update, partial_update, destroy
    # Plus custom actions: profile, capabilities
    path('', include(router.urls)),
]
