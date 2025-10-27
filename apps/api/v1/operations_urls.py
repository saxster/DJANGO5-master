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

# Import viewsets when they're created
# from apps.activity.api import views as activity_views
# from apps.scheduler.api import views as scheduler_views

app_name = 'operations'

router = DefaultRouter()
# router.register(r'jobs', activity_views.JobViewSet, basename='jobs')
# router.register(r'jobneeds', activity_views.JobneedViewSet, basename='jobneeds')
# router.register(r'tasks', activity_views.TaskViewSet, basename='tasks')
# router.register(r'tours', scheduler_views.TourViewSet, basename='tours')
# router.register(r'questionsets', activity_views.QuestionSetViewSet, basename='questionsets')

urlpatterns = [
    # Router URLs (CRUD operations)
    path('', include(router.urls)),

    # Additional endpoints (to be implemented)
    # path('jobneeds/<int:pk>/details/', activity_views.JobneedDetailsView.as_view(), name='jobneed-details'),
    # path('jobneeds/schedule/', activity_views.JobneedScheduleView.as_view(), name='jobneed-schedule'),
    # path('jobs/<int:job_id>/questionset/', activity_views.JobQuestionSetView.as_view(), name='job-questionset'),
]
