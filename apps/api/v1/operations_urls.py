"""
Operations API URLs (v1)

Domain: /api/v1/operations/

Handles jobs, tours, tasks, schedules, and question sets.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.activity.api.viewsets import (
    JobViewSet,
    JobneedViewSet,
    TaskViewSet,
    QuestionSetViewSet,
)

app_name = 'operations'

router = DefaultRouter()
router.register(r'jobs', JobViewSet, basename='jobs')
router.register(r'jobneeds', JobneedViewSet, basename='jobneeds')
router.register(r'tasks', TaskViewSet, basename='tasks')
router.register(r'questionsets', QuestionSetViewSet, basename='questionsets')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes custom actions:
    # - jobs/{id}/complete/
    # - jobneeds/{id}/details/
    # - jobneeds/{id}/schedule/
    # - jobneeds/{id}/generate/
    path('', include(router.urls)),
]
