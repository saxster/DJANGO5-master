"""
V2 People (User) Management REST API Views - FACADE

This module provides backward-compatible imports for views that have been
refactored into focused modules to comply with .claude/rules.md architecture limits.

Refactoring (Nov 2025):
- people_user_views.py: Core user CRUD operations (List, Detail, Update)
- people_search_views.py: User search functionality

New code should import directly from specific modules:
    from apps.api.v2.views.people_user_views import PeopleUsersListView
    from apps.api.v2.views.people_search_views import PeopleSearchView

This facade maintains backward compatibility with existing imports:
    from apps.api.v2.views import people_views
    people_views.PeopleUsersListView  # Still works
"""

# Import all views from refactored modules
from apps.api.v2.views.people_user_views import (
    PeopleUsersListView,
    PeopleUserDetailView,
    PeopleUserUpdateView,
)
from apps.api.v2.views.people_search_views import PeopleSearchView

__all__ = [
    'PeopleUsersListView',
    'PeopleUserDetailView',
    'PeopleUserUpdateView',
    'PeopleSearchView',
]
