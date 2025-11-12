"""
Help Desk API URLs (V2)

Domain: /api/v2/helpdesk/

Handles ticket management, escalations, and workflow with V2 enhancements.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v2.views import helpdesk_views

app_name = 'helpdesk'

urlpatterns = [
    # Ticket management endpoints (V2)
    path('tickets/', helpdesk_views.TicketListView.as_view(), name='tickets-list'),
    path('tickets/create/', helpdesk_views.TicketCreateView.as_view(), name='tickets-create'),
    path('tickets/<int:ticket_id>/', helpdesk_views.TicketUpdateView.as_view(), name='tickets-update'),
    path('tickets/<int:ticket_id>/transition/', helpdesk_views.TicketTransitionView.as_view(), name='tickets-transition'),
    path('tickets/<int:ticket_id>/escalate/', helpdesk_views.TicketEscalateView.as_view(), name='tickets-escalate'),
]
