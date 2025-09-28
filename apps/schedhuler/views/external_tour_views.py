"""
External Tour Views

Thin view layer for external tour scheduling.
All business logic delegated to ExternalTourService.

Follows Rule 8: All view methods < 30 lines
Follows SRP: HTTP handling only
"""

import logging
import json
from datetime import datetime, time, date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, QueryDict
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.http import require_http_methods

from apps.core import utils
from apps.core.exceptions import (
    ValidationError,
    DatabaseException,
    SystemException,
)
from apps.activity.models.job_model import Job
import apps.schedhuler.forms as scd_forms
from apps.schedhuler.services.external_tour_service import ExternalTourService

logger = logging.getLogger(__name__)


class Schd_E_TourFormJob(LoginRequiredMixin, View):
    """Create new external tour."""

    template_path = "schedhuler/schd_e_tourform_job.html"
    form_class = scd_forms.Schd_E_TourJobForm
    service = ExternalTourService()

    initial = {
        "starttime": time(00, 00, 00),
        "endtime": time(00, 00, 00),
        "identifier": Job.Identifier.EXTERNALTOUR,
        "priority": Job.Priority.LOW,
        "scantype": Job.Scantype.QR,
        "fromdate": datetime.combine(date.today(), time(00, 00, 00)),
        "uptodate": datetime.combine(date.today(), time(23, 00, 00)) + timedelta(days=7),
    }

    def get(self, request, *args, **kwargs):
        """Display external tour creation form."""
        logger.info("External tour creation form requested")
        context = {
            "form": self.form_class(request=request, initial=self.initial),
        }
        return render(request, self.template_path, context=context)

    def post(self, request, *args, **kwargs):
        """Handle external tour creation."""
        logger.info("External tour form submitted")
        data = QueryDict(request.POST.get("formData", ""))

        form = self.form_class(data=data, initial=self.initial, request=request)

        if form.is_valid():
            return self._handle_valid_form(form, request)
        return JsonResponse({"errors": form.errors}, status=400)

    def _handle_valid_form(self, form, request):
        """Process valid form submission."""
        try:
            sites = json.loads(request.POST.get("assigned_sites", "[]"))

            job, success = self.service.create_external_tour(
                form_data=form.cleaned_data,
                assigned_sites=sites,
                user=request.user,
                session=request.session
            )

            return JsonResponse({
                "jobname": job.jobname,
                "url": f"/operations/tours/external/update/{job.id}/",
            }, status=200)

        except ValidationError:
            return JsonResponse({"errors": "Validation failed"}, status=400)
        except DatabaseException:
            return JsonResponse({"errors": "Database error"}, status=500)


class Update_E_TourFormJob(LoginRequiredMixin, View):
    """Update existing external tour."""

    template_path = "schedhuler/schd_e_tourform_job.html"
    form_class = scd_forms.Schd_E_TourJobForm
    service = ExternalTourService()
    initial = Schd_E_TourFormJob.initial

    def get(self, request, *args, **kwargs):
        """Display external tour update form."""
        pk = kwargs.get("pk")
        logger.info(f"External tour update form requested for ID: {pk}")

        try:
            job, sites = self.service.get_tour_with_sites(pk)

            form = self.form_class(instance=job, initial=self.initial)

            context = {
                "form": form,
                "edit": True,
                "sites": list(sites),
            }

            return render(request, self.template_path, context=context)

        except ValidationError:
            messages.error(request, "Tour not found", "alert alert-danger")
            return redirect("/operations/tours/external/create/")


class Retrive_E_ToursJob(LoginRequiredMixin, View):
    """List external tours."""

    template_path = "schedhuler/schd_e_tourlist_job.html"
    service = ExternalTourService()

    def get(self, request, *args, **kwargs):
        """Display external tours list."""
        logger.info("External tours list requested")

        try:
            filters = self._extract_filters(request.GET)
            page = int(request.GET.get('page', 1))

            tours = self.service.get_external_tours(filters=filters, page=page)

            context = {"tours": tours, "page": page}
            return render(request, self.template_path, context=context)

        except (DatabaseException, SystemException) as e:
            logger.error(f"Error retrieving tours: {e}")
            return render(request, self.template_path, context={"tours": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters."""
        filters = {}
        if 'jobname' in query_params:
            filters['jobname'] = query_params['jobname']
        return filters


class ExternalTourTracking(LoginRequiredMixin, View):
    """Track external tour execution in real-time."""

    template_path = "schedhuler/site_tour_tracking.html"
    service = ExternalTourService()

    def get(self, request, *args, **kwargs):
        """Display tour tracking page."""
        action = request.GET.get("action")

        if action == "get_checkpoints":
            return self._get_checkpoint_data(request)

        jobneed_id = request.GET.get("jobneed_id")
        return render(request, self.template_path, {"jobneed_id": jobneed_id})

    def _get_checkpoint_data(self, request):
        """Retrieve checkpoint locations for map display."""
        try:
            jobneed_id = request.GET.get("jobneed_id")
            data = self.service.get_site_checkpoints(jobneed_id)

            return JsonResponse(data, status=200, safe=False)

        except ValidationError as e:
            return JsonResponse({"errors": str(e)}, status=404)
        except DatabaseException:
            return JsonResponse({"errors": "Database error"}, status=500)


@login_required
@require_http_methods(["POST"])
def save_assigned_sites_for_externaltour(request):
    """Save assigned sites to external tour (function-based view)."""
    logger.info("Save assigned sites requested")

    try:
        tour_id = request.POST.get("tour_id")
        sites = json.loads(request.POST.get("sites", "[]"))

        service = ExternalTourService()
        job = Job.objects.get(id=tour_id)

        service._update_sites_for_tour(
            job=job,
            sites=sites,
            user=request.user,
            session=request.session
        )

        return JsonResponse({
            "status": "success",
            "message": f"{len(sites)} sites assigned"
        }, status=200)

    except ValidationError as e:
        return JsonResponse({"errors": str(e)}, status=400)
    except DatabaseException:
        return JsonResponse({"errors": "Database error"}, status=500)