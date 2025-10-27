"""
Help Desk API URLs (v1)

Domain: /api/v1/help-desk/

Handles tickets, escalations, SLA policies, and workflow management.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.y_helpdesk.api.viewsets import TicketViewSet

app_name = 'helpdesk'

router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='tickets')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes custom actions:
    # - POST /tickets/{id}/transition/
    # - POST /tickets/{id}/escalate/
    # - GET  /tickets/sla-breaches/
    path('', include(router.urls)),
]
