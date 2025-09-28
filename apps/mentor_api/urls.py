"""
URL configuration for Mentor API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PlanViewSet, PatchViewSet, TestViewSet, GuardViewSet, ExplainViewSet,
    MentorStatusView, MentorHealthView
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'plan', PlanViewSet, basename='mentor-plan')
router.register(r'patch', PatchViewSet, basename='mentor-patch')
router.register(r'test', TestViewSet, basename='mentor-test')
router.register(r'guard', GuardViewSet, basename='mentor-guard')
router.register(r'explain', ExplainViewSet, basename='mentor-explain')

app_name = 'mentor_api'

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),

    # System status endpoints
    path('status/', MentorStatusView.as_view(), name='mentor-status'),
    path('health/', MentorHealthView.as_view(), name='mentor-health'),
]