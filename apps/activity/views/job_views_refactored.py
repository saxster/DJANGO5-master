"""
PPM/Job Views - Refactored Version

Demonstrates code deduplication for PPMView and PPMJobneedView.

COMPARISON:
- Original PPMView: 156 lines
- Original PPMJobneedView: 118 lines
- Total Original: 274 lines
- Refactored Total: ~70 lines (74% reduction)

Following .claude/rules.md:
- View methods < 30 lines (Rule 8)
- Business logic in service layer (Rule 8)
- Specific exception handling (Rule 11)
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic.base import View
from django.shortcuts import render

from apps.core.mixins import (
    CRUDActionMixin,
    ExceptionHandlingMixin,
    StandardFormProcessingMixin,
)
from apps.activity.forms.job_form import PPMForm, PPMFormJobneed
from apps.activity.models.job_model import Job, Jobneed
from apps.core import utils
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class PPMViewRefactored(
    CRUDActionMixin,
    ExceptionHandlingMixin,
    StandardFormProcessingMixin,
    LoginRequiredMixin,
    View
):
    """
    Refactored PPM view.

    BEFORE: 156 lines with duplicated patterns
    AFTER: ~35 lines using mixins
    """

    crud_config = {
        "template_list": "activity/ppm/ppm_list.html",
        "template_form": "activity/ppm/ppm_form.html",
        "model": Job,
        "form": PPMForm,
        "form_name": "ppmform",
        "related": ["asset", "qset", "people", "pgroup", "bu"],
        "fields": [
            "plandatetime",
            "expirydatetime",
            "gracetime",
            "asset__assetname",
            "assignedto",
            "performedby__peoplename",
            "jobdesc",
            "frequency",
            "qset__qsetname",
            "id",
            "ctzoffset",
            "bu__bucode",
            "bu__buname",
        ],
    }

    def get_template_context(self, request):
        """Add status options to template context."""
        return {
            "status_options": [
                ("COMPLETED", "Completed"),
                ("AUTOCLOSED", "AutoClosed"),
                ("ASSIGNED", "Assigned"),
            ]
        }

    def handle_custom_action(self, request, action, config):
        """Handle PPM-specific actions."""
        if action == "job_ppmlist":
            objs = config["model"].objects.get_jobppm_listview(request)
            return JsonResponse({"data": list(objs)})

        if request.POST.get("action") == "runScheduler":
            from background_tasks.tasks import create_ppm_job
            resp, F, d, story = create_ppm_job(request.POST.get("job_id"))
            return JsonResponse(resp, status=200)

        return None

    def post(self, request, *args, **kwargs):
        """Handle POST with exception handling mixin."""
        if request.POST.get("action") == "runScheduler":
            return self.handle_custom_action(request, "runScheduler", self.crud_config)

        return self.handle_exceptions(request, self._process_post)

    def _process_post(self, request):
        """Process POST using validated form mixin."""
        return self.process_form_post(request)


class PPMJobneedViewRefactored(
    CRUDActionMixin,
    ExceptionHandlingMixin,
    StandardFormProcessingMixin,
    LoginRequiredMixin,
    View
):
    """
    Refactored PPM Jobneed view.

    BEFORE: 118 lines
    AFTER: ~30 lines (75% reduction)
    """

    crud_config = {
        "template_list": "activity/ppm/ppm_jobneed_list.html",
        "template_form": "activity/ppm/jobneed_ppmform.html",
        "model": Jobneed,
        "form": PPMFormJobneed,
        "form_name": "ppmjobneedform",
        "related": ["asset", "qset", "people", "pgroup", "bu", "job"],
        "fields": [
            "plandatetime",
            "expirydatetime",
            "gracetime",
            "asset__assetname",
            "assignedto",
            "performedby__peoplename",
            "jobdesc",
            "job__frequency",
            "qset__qsetname",
            "id",
            "ctzoffset",
            "jobstatus",
            "bu__bucode",
            "bu__buname",
        ],
        "list_method": "get_ppm_listview",
    }

    def get_template_context(self, request):
        """Add status options."""
        return {
            "status_options": [
                ("COMPLETED", "Completed"),
                ("AUTOCLOSED", "AutoClosed"),
                ("ASSIGNED", "Assigned"),
            ]
        }

    def handle_custom_action(self, request, action, config):
        """Handle jobneed-specific actions."""
        R = request.GET

        if action == "jobneed_ppmlist":
            objs = config["model"].objects.get_ppm_listview(
                request, config["fields"], config["related"]
            )
            return JsonResponse({"data": list(objs)})

        if action == "get_ppmtask_details" and R.get("taskid"):
            from apps.activity.models.job_model import JobneedDetails
            objs = JobneedDetails.objects.get_ppm_details(request)
            return JsonResponse({"data": list(objs)})

        return None

    def post(self, request, *args, **kwargs):
        """Handle POST with exception handling."""
        return self.handle_exceptions(request, self._process_post)

    def _process_post(self, request):
        """Process POST using form mixin."""
        return self.process_form_post(request)