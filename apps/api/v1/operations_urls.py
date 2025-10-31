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
    QuestionSetViewSet,
)
from apps.activity.api.viewsets.task_sync_viewset import TaskSyncViewSet
from apps.activity.api.viewsets.question_viewset import QuestionViewSet
from apps.work_order_management.api.viewsets import WorkPermitViewSet

app_name = 'operations'

router = DefaultRouter()
router.register(r'jobs', JobViewSet, basename='jobs')
router.register(r'jobneeds', JobneedViewSet, basename='jobneeds')
router.register(r'questionsets', QuestionSetViewSet, basename='questionsets')

# Mobile sync endpoints (legacy API replacement)
router.register(r'tasks', TaskSyncViewSet, basename='task-sync')

# Work permit endpoints (legacy API replacement)
router.register(r'work-permits', WorkPermitViewSet, basename='work-permits')

# Question sync endpoints (legacy API replacement)
router.register(r'questions', QuestionViewSet, basename='questions')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes custom actions:
    # - jobs/{id}/complete/
    # - jobneeds/{id}/details/
    # - jobneeds/{id}/schedule/
    # - jobneeds/{id}/generate/
    #
    # Mobile sync endpoints (replace legacy API):
    # - tasks/modified-after/ → get_jobneedmodifiedafter
    # - tasks/details/modified-after/ → get_jndmodifiedafter
    # - tasks/tours/external/modified-after/ → get_externaltourmodifiedafter
    # - tasks/sync/ → InsertRecord mutation
    # - tasks/{id}/update/ → TaskTourUpdate mutation
    #
    # Work permit endpoints (replace legacy API):
    # - work-permits/ → get_wom_records
    # - work-permits/{uuid}/pdf/ → get_pdf_url
    # - work-permits/{uuid}/approve/ → get_approve_workpermit
    # - work-permits/{uuid}/reject/ → get_reject_workpermit
    # - work-permits/approvers/ → get_approvers
    # - work-permits/vendors/ → get_vendors
    #
    # Question endpoints (replace legacy API):
    # - questions/questions/modified-after/ → get_questionsmodifiedafter
    # - questions/question-sets/modified-after/ → get_qsetmodifiedafter
    # - questions/question-set-belongings/modified-after/ → get_qsetbelongingmodifiedafter
    # - questions/{id}/conditional-logic/ → get_questionset_with_conditional_logic
    path('', include(router.urls)),
]
