"""
V2 Help Desk Ticket Management REST API Views (Facade)

REFACTORED: Original 673-line file split into focused modules (Nov 2025)

This facade maintains backward compatibility for imports while delegating
to focused modules:
- helpdesk_list_views.py: List, search, filter operations
- helpdesk_detail_views.py: Detail, create, update operations
- helpdesk_workflow_views.py: Transition, escalate, assign operations

Following .claude/rules.md:
- View methods < 30 lines
- File size limits < 200 lines
- Single responsibility principle
"""

# Import all views from focused modules for backward compatibility
from apps.api.v2.views.helpdesk_list_views import (
    TicketListView,
    TicketSearchView,
    TicketFilterView,
)
from apps.api.v2.views.helpdesk_detail_views import (
    TicketDetailView,
    TicketCreateView,
    TicketUpdateView,
)
from apps.api.v2.views.helpdesk_workflow_views import (
    TicketTransitionView,
    TicketEscalateView,
    TicketAssignView,
)

__all__ = [
    # List & Search Views
    'TicketListView',
    'TicketSearchView',
    'TicketFilterView',
    # Detail & CRUD Views
    'TicketDetailView',
    'TicketCreateView',
    'TicketUpdateView',
    # Workflow Views
    'TicketTransitionView',
    'TicketEscalateView',
    'TicketAssignView',
]
