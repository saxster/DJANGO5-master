"""
Operations API v2 URL Configuration
Domain: Operations (Tasks, Tours, Jobs, PPM, Questions/Answers)
Generated from Kotlin SDK documentation
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.activity.api.v2 import viewsets

router = DefaultRouter()
router.register(r'jobs', viewsets.JobViewSetV2, basename='job')
router.register(r'tours', viewsets.TourViewSetV2, basename='tour')
router.register(r'tasks', viewsets.TaskViewSetV2, basename='task')
router.register(r'ppm/schedules', viewsets.PPMScheduleViewSetV2, basename='ppm-schedule')
router.register(r'questions', viewsets.QuestionViewSetV2, basename='question')

app_name = 'operations_v2'

urlpatterns = [
    path('', include(router.urls)),
    path('answers/', viewsets.AnswerSubmissionView.as_view(), name='answer-submission'),
    path('answers/batch/', viewsets.AnswerBatchSubmissionView.as_view(), name='answer-batch-submission'),
    path('attachments/upload/', viewsets.AttachmentUploadView.as_view(), name='attachment-upload'),

    # Work Permits (V2) - Placeholder for future full implementation
    # For now, can use V1 endpoint or add minimal V2 wrapper
    # path('work-permits/', WorkPermitListView.as_view(), name='work-permits-list'),
]
