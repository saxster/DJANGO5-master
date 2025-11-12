"""
Journal Views Package

Refactored from single 804-line views.py into modular domain-specific views.

Structure:
- entry_views.py: CRUD operations for journal entries
- sync_views.py: Mobile sync with conflict resolution
- search_views.py: Advanced search and filtering
- analytics_views.py: Wellbeing analytics and insights
- privacy_views.py: Privacy settings management
- permissions.py: Shared permission classes

All business logic delegated to services for testability and maintainability.
"""

from .entry_views import JournalEntryViewSet
from .sync_views import JournalSyncView
from .search_views import JournalSearchView
from .analytics_views import JournalAnalyticsView
from .privacy_views import JournalPrivacySettingsView
from .permissions import JournalPermission

__all__ = [
    'JournalEntryViewSet',
    'JournalSyncView',
    'JournalSearchView',
    'JournalAnalyticsView',
    'JournalPrivacySettingsView',
    'JournalPermission',
]
