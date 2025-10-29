"""
People API ViewSets

ViewSets for people domain REST API.
"""

# Import from parent people_viewsets.py file (renamed to avoid circular import)
from ..people_viewsets import PeopleViewSet

# Import from submodules
from .people_sync_viewset import PeopleSyncViewSet

__all__ = [
    'PeopleViewSet',  # From viewsets.py file
    'PeopleSyncViewSet',  # From viewsets/ directory
]
