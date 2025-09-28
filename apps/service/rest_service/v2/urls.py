"""
URL configuration for REST API v2
Placeholder for future v2 endpoints.

When v2 is needed, implement endpoints here following .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #13: Explicit form validation
- Rule #17: Transaction management
"""

from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

router = DefaultRouter()

urlpatterns = router.urls + [
    path('status/', views.V2StatusView.as_view(), name='v2-status'),
]