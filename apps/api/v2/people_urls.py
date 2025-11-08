"""
People Management API URLs (V2)

Domain: /api/v2/people/

Handles user directory, profiles, and search with V2 enhancements.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v2.views import people_views

app_name = 'people'

urlpatterns = [
    # User management endpoints (V2)
    path('users/', people_views.PeopleUsersListView.as_view(), name='users-list'),
    path('users/<int:user_id>/', people_views.PeopleUserDetailView.as_view(), name='users-detail'),
    path('users/<int:user_id>/update/', people_views.PeopleUserUpdateView.as_view(), name='users-update'),
    path('search/', people_views.PeopleSearchView.as_view(), name='search'),
]
