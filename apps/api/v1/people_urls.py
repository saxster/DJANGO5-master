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

# Import viewsets when they're created
# from apps.peoples.api import views

app_name = 'people'

router = DefaultRouter()
# router.register(r'', views.PeopleViewSet, basename='people')

urlpatterns = [
    # Router URLs (CRUD operations)
    path('', include(router.urls)),

    # Additional endpoints (to be implemented)
    # path('<int:pk>/profile/', views.PeopleProfileView.as_view(), name='profile'),
    # path('<int:pk>/organizational/', views.PeopleOrganizationalView.as_view(), name='organizational'),
    # path('<int:pk>/capabilities/', views.PeopleCapabilitiesView.as_view(), name='capabilities'),
]
