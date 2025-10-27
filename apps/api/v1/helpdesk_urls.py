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

# Import viewsets when they're created
# from apps.y_helpdesk.api import views

app_name = 'helpdesk'

router = DefaultRouter()
# router.register(r'tickets', views.TicketViewSet, basename='tickets')
# router.register(r'escalation-policies', views.EscalationPolicyViewSet, basename='escalation-policies')
# router.register(r'sla-policies', views.SLAPolicyViewSet, basename='sla-policies')

urlpatterns = [
    # Router URLs (CRUD operations)
    path('', include(router.urls)),

    # Additional endpoints (to be implemented)
    # path('tickets/<int:pk>/transition/', views.TicketTransitionView.as_view(), name='ticket-transition'),
    # path('tickets/<int:pk>/escalate/', views.TicketEscalateView.as_view(), name='ticket-escalate'),
    # path('sla-breaches/', views.SLABreachView.as_view(), name='sla-breaches'),
]
