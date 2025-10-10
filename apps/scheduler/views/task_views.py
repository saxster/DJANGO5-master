"""
Task Views

Thin view layer for task scheduling.
All business logic delegated to TaskService.

Follows Rule 8: All view methods < 30 lines
Follows SRP: HTTP handling only
"""

import logging
from datetime import datetime, time, date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, QueryDict
from django.shortcuts import render, redirect
from django.views import View

from apps.core import utils
from apps.core.exceptions import ValidationError, DatabaseException
from apps.activity.models.job_model import Job
import apps.schedhuler.forms as scd_forms
from apps.schedhuler.services.task_service import TaskService, TaskJobneedService

logger = logging.getLogger(__name__)


class SchdTaskFormJob(LoginRequiredMixin, View):
    """Create new task."""

    template_path = "schedhuler/schd_task_form.html"
    form_class = scd_forms.SchdTaskJobForm
    service = TaskService()

    initial = {
        "starttime": time(00, 00, 00),
        "endtime": time(00, 00, 00),
        "identifier": Job.Identifier.TASK,
        "priority": Job.Priority.MEDIUM,
        "fromdate": datetime.combine(date.today(), time(00, 00, 00)),
        "uptodate": datetime.combine(date.today(), time(23, 00, 00)) + timedelta(days=1),
    }

    def get(self, request, *args, **kwargs):
        """Display task creation form."""
        logger.info("Task creation form requested")
        context = {
            "form": self.form_class(request=request, initial=self.initial),
        }
        return render(request, self.template_path, context=context)

    def post(self, request, *args, **kwargs):
        """Handle task creation."""
        logger.info("Task form submitted")
        data = QueryDict(request.POST.get("formData", ""))

        form = self.form_class(data=data, initial=self.initial, request=request)

        if form.is_valid():
            return self._handle_valid_form(form, request)
        return JsonResponse({"errors": form.errors}, status=400)

    def _handle_valid_form(self, form, request):
        """Process valid form submission."""
        try:
            job, success = self.service.create_task(
                form_data=form.cleaned_data,
                user=request.user,
                session=request.session
            )

            return JsonResponse({
                "jobname": job.jobname,
                "url": f"/operations/tasks/update/{job.id}/",
            }, status=200)

        except ValidationError:
            return JsonResponse({"errors": "Validation failed"}, status=400)
        except DatabaseException:
            return JsonResponse({"errors": "Database error"}, status=500)


class UpdateSchdTaskJob(LoginRequiredMixin, View):
    """Update existing task."""

    template_path = "schedhuler/schd_task_form.html"
    form_class = scd_forms.SchdTaskJobForm
    service = TaskService()
    initial = SchdTaskFormJob.initial

    def get(self, request, *args, **kwargs):
        """Display task update form."""
        pk = kwargs.get("pk")
        logger.info(f"Task update form requested for ID: {pk}")

        try:
            job = self.service.get_task_by_id(pk)

            form = self.form_class(instance=job, initial=self.initial)

            context = {
                "form": form,
                "edit": True,
            }

            return render(request, self.template_path, context=context)

        except ValidationError:
            messages.error(request, "Task not found", "alert alert-danger")
            return redirect("/operations/tasks/create/")


class RetriveSchdTasksJob(LoginRequiredMixin, View):
    """List tasks."""

    template_path = "schedhuler/task_list.html"
    service = TaskService()

    def get(self, request, *args, **kwargs):
        """Display tasks list."""
        logger.info("Tasks list requested")

        try:
            filters = self._extract_filters(request.GET)
            page = int(request.GET.get('page', 1))

            tasks = self.service.get_tasks_list(filters=filters, page=page)

            context = {"tasks": tasks, "page": page}
            return render(request, self.template_path, context=context)

        except DatabaseException as e:
            logger.error(f"Error retrieving tasks: {e}")
            return render(request, self.template_path, context={"tasks": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters."""
        filters = {}
        if 'jobname' in query_params:
            filters['jobname'] = query_params['jobname']
        if 'asset_id' in query_params:
            filters['asset_id'] = query_params['asset_id']
        return filters


class RetrieveTasksJobneed(LoginRequiredMixin, View):
    """List task jobneeds."""

    template_path = "schedhuler/task_jobneed_list.html"
    service = TaskJobneedService()

    def get(self, request, *args, **kwargs):
        """Display task jobneeds list."""
        logger.info("Task jobneeds list requested")

        try:
            filters = self._extract_filters(request.GET)
            page = int(request.GET.get('page', 1))

            jobneeds = self.service.get_task_jobneeds(filters=filters, page=page)

            context = {"jobneeds": jobneeds, "page": page}
            return render(request, self.template_path, context=context)

        except DatabaseException as e:
            logger.error(f"Error retrieving task jobneeds: {e}")
            return render(request, self.template_path, context={"jobneeds": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters."""
        filters = {}
        if 'people_id' in query_params:
            filters['people_id'] = query_params['people_id']
        if 'status' in query_params:
            filters['status'] = query_params['status']
        return filters


class GetTaskFormJobneed(LoginRequiredMixin, View):
    """View specific task jobneed."""

    template_path = "schedhuler/task_jobneed_detail.html"
    service = TaskJobneedService()

    def get(self, request, *args, **kwargs):
        """Display task jobneed details."""
        pk = kwargs.get("pk")
        logger.info(f"Task jobneed detail requested for ID: {pk}")

        try:
            jobneed = self.service.get_task_jobneed_by_id(pk)

            context = {"jobneed": jobneed}
            return render(request, self.template_path, context=context)

        except ValidationError:
            messages.error(request, "Task jobneed not found", "alert alert-danger")
            return redirect("/operations/tasks/jobneeds/")