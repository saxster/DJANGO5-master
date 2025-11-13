"""
Django Admin Registration for Question Models.

Registers Question, QuestionSet, and QuestionSetBelonging models with
Django admin interface using ImportExportModelAdmin.

Extracted from: apps/activity/admin/question_admin.py (lines 630-646)
Date: 2025-10-10
"""
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from import_export.admin import ImportExportModelAdmin

from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from .question_create import QuestionResource


class QuestionAdmin(ImportExportModelAdmin):
    list_per_page = 50
    """
    Admin interface for Question model with import/export functionality.

    Uses QuestionResource for bulk import/export operations.
    Optimized queryset with select_related for performance.
    """
    resource_class = QuestionResource
    list_display = ["id", "quesname"]
    list_select_related = ('qset', 'cuser', 'muser', 'tenant')

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pass request context to resource for audit trail."""
        return {"request": request}

    def get_queryset(self, request):
        """Optimized queryset with related models pre-loaded."""
        return Question.objects.select_related(
            'qset', 'cuser', 'muser', 'tenant'
        ).all()


# Register Question model (only if not already registered)
try:
    admin.site.register(Question, QuestionAdmin)
except AlreadyRegistered:
    pass
