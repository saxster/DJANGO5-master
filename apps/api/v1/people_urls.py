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
from apps.peoples.api.viewsets import PeopleSyncViewSet

app_name = 'people'

router = DefaultRouter()
router.register(r'users', PeopleViewSet, basename='people')

# Mobile sync endpoints (legacy API replacement)
router.register(r'sync', PeopleSyncViewSet, basename='people-sync')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes: list, create, retrieve, update, partial_update, destroy
    # Plus custom actions: profile, capabilities
    #
    # Mobile sync endpoints (replace legacy API):
    # - sync/modified-after/ → get_peoplemodifiedafter
    # - sync/groups/memberships/modified-after/ → get_pgbelongingmodifiedafter
    # - sync/event-logs/history/ → get_peopleeventlog_history
    # - sync/event-logs/punch-ins/ → get_people_event_log_punch_ins
    # - sync/attachments/ → get_attachments
    path('', include(router.urls)),
]
