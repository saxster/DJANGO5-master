"""
Jobneed Management Views

Generic CRUD views for jobneed management across all job types.

Follows Rule 8: All view methods < 30 lines
Follows SRP: HTTP handling only
"""

import logging
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from apps.core.exceptions import ValidationError, DatabaseException
from apps.activity.models.job_model import Jobneed, JobneedDetails, Job
from apps.schedhuler.services.jobneed_management_service import JobneedManagementService

logger = logging.getLogger(__name__)


class JobneedTours(LoginRequiredMixin, View):
    """Manage jobneed for internal tours."""

    template_path = "schedhuler/jobneed_tours_management.html"
    service = JobneedManagementService()

    def get(self, request, *args, **kwargs):
        """Display internal tour jobneeds."""
        logger.info("Internal tour jobneeds management requested")

        try:
            filters = self._extract_filters(request.GET)
            jobneeds = self.service.get_jobneeds_by_job_type(
                job_type=Job.Identifier.INTERNALTOUR,
                filters=filters
            )

            context = {"jobneeds": jobneeds}
            return render(request, self.template_path, context=context)

        except DatabaseException as e:
            logger.error(f"Error retrieving jobneeds: {e}")
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


class JobneedExternalTours(LoginRequiredMixin, View):
    """Manage jobneed for external tours."""

    template_path = "schedhuler/jobneed_external_tours_management.html"
    service = JobneedManagementService()

    def get(self, request, *args, **kwargs):
        """Display external tour jobneeds."""
        logger.info("External tour jobneeds management requested")

        try:
            filters = self._extract_filters(request.GET)
            jobneeds = self.service.get_jobneeds_by_job_type(
                job_type=Job.Identifier.EXTERNALTOUR,
                filters=filters
            )

            context = {"jobneeds": jobneeds}
            return render(request, self.template_path, context=context)

        except DatabaseException as e:
            logger.error(f"Error retrieving jobneeds: {e}")
            return render(request, self.template_path, context={"jobneeds": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters."""
        filters = {}
        if 'people_id' in query_params:
            filters['people_id'] = query_params['people_id']
        return filters


class JobneedTasks(LoginRequiredMixin, View):
    """Manage jobneed for tasks."""

    template_path = "schedhuler/jobneed_tasks_management.html"
    service = JobneedManagementService()

    def get(self, request, *args, **kwargs):
        """Display task jobneeds."""
        logger.info("Task jobneeds management requested")

        try:
            filters = self._extract_filters(request.GET)
            jobneeds = self.service.get_jobneeds_by_job_type(
                job_type=Job.Identifier.TASK,
                filters=filters
            )

            context = {"jobneeds": jobneeds}
            return render(request, self.template_path, context=context)

        except DatabaseException as e:
            logger.error(f"Error retrieving jobneeds: {e}")
            return render(request, self.template_path, context={"jobneeds": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters."""
        filters = {}
        if 'people_id' in query_params:
            filters['people_id'] = query_params['people_id']
        return filters


class JobneednJNDEditor(LoginRequiredMixin, View):
    """Edit jobneed and jobneed details."""

    service = JobneedManagementService()

    def get(self, request, *args, **kwargs):
        """Get jobneed details for editing."""
        action = request.GET.get("action")

        if action == "get_jndofjobneed" and request.GET.get("jobneedid"):
            return self._get_jnd_for_jobneed(request.GET.get("jobneedid"))

        return JsonResponse({"data": []}, status=200)

    def post(self, request, *args, **kwargs):
        """Handle jobneed update requests."""
        if request.POST.get("tourjobneed"):
            return self._handle_jobneed_update(request)

        return JsonResponse({"errors": "Invalid request"}, status=400)

    def _get_jnd_for_jobneed(self, jobneed_id):
        """Retrieve jobneed details."""
        try:
            data = self.service.get_jobneed_with_details(jobneed_id)
            return JsonResponse({"data": data['details']}, status=200)

        except ValidationError:
            return JsonResponse({"errors": "Jobneed not found"}, status=404)

    def _handle_jobneed_update(self, request):
        """Handle jobneed update."""
        try:
            jobneed_id = request.POST.get("jobneed_id")
            details = json.loads(request.POST.get("details", "[]"))

            self.service.update_jobneed_details(jobneed_id, details)

            return JsonResponse({"status": "success"}, status=200)

        except ValidationError:
            return JsonResponse({"errors": "Validation failed"}, status=400)