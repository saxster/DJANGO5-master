"""
Internal Tour Views

Thin view layer for internal tour scheduling.
All business logic delegated to InternalTourService.

Follows Rule 8: All view methods < 30 lines
Follows SRP: HTTP handling only, no business logic
"""

import logging
import json
from datetime import datetime, time, date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.http import QueryDict, JsonResponse, Http404
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_http_methods

from apps.core import utils
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    SchedulingException,
    DatabaseException,
    SystemException,
    EnhancedValidationException,
)
from apps.activity.models.job_model import Job
import apps.schedhuler.forms as scd_forms
from apps.schedhuler.services.internal_tour_service import (
    InternalTourService,
    InternalTourJobneedService
)

logger = logging.getLogger(__name__)


class Schd_I_TourFormJob(LoginRequiredMixin, View):
    """Create new internal tour."""

    template_path = "schedhuler/schd_i_tourform_job.html"
    form_class = scd_forms.Schd_I_TourJobForm
    subform = scd_forms.SchdChild_I_TourJobForm
    service = InternalTourService()

    initial = {
        "starttime": time(00, 00, 00),
        "endtime": time(00, 00, 00),
        "expirytime": 0,
        "identifier": Job.Identifier.INTERNALTOUR,
        "priority": Job.Priority.LOW,
        "scantype": Job.Scantype.QR,
        "gracetime": 5,
        "fromdate": datetime.combine(date.today(), time(00, 00, 00)),
        "uptodate": datetime.combine(date.today(), time(23, 00, 00)) + timedelta(days=2),
    }

    def get(self, request, *args, **kwargs):
        """Display tour creation form."""
        logger.info("Internal tour creation form requested")
        context = {
            "schdtourform": self.form_class(request=request, initial=self.initial),
            "childtour_form": self.subform(),
        }
        return render(request, self.template_path, context=context)

    def post(self, request, *args, **kwargs):
        """Handle tour creation/update submission."""
        logger.info("Internal tour form submitted")
        data = QueryDict(request.POST["formData"])
        pk = request.POST.get("pk", None)

        form = self._get_form(data, pk, request)

        if form.is_valid():
            return self._handle_valid_form(form, pk, request)
        return self._handle_invalid_form(form)

    def _get_form(self, data, pk, request):
        """Get form instance (create or update)."""
        if pk:
            obj = utils.get_model_obj(pk, request, {"model": Job})
            logger.info(f"Updating existing tour: {obj.jobname}")
            return self.form_class(
                instance=obj, data=data, initial=self.initial, request=request
            )
        else:
            logger.info("Creating new internal tour")
            return self.form_class(data=data, initial=self.initial, request=request)

    def _handle_valid_form(self, form, pk, request):
        """Process valid form submission."""
        try:
            checkpoints = json.loads(request.POST.get("asssigned_checkpoints"))

            if pk:
                job, success = self.service.update_tour_with_checkpoints(
                    tour_id=pk,
                    form_data=form.cleaned_data,
                    checkpoints=checkpoints,
                    user=request.user,
                    session=request.session
                )
            else:
                job, success = self.service.create_tour_with_checkpoints(
                    form_data=form.cleaned_data,
                    checkpoints=checkpoints,
                    user=request.user,
                    session=request.session
                )

            return JsonResponse({
                "jobname": job.jobname,
                "url": f"/operations/tours/update/{job.id}/",
            }, status=200)

        except (ValidationError, EnhancedValidationException):
            return JsonResponse({"errors": "Form validation failed"}, status=400)
        except (IntegrityError, DatabaseException):
            return JsonResponse({"errors": "Database error occurred"}, status=500)
        except SchedulingException:
            return JsonResponse({"errors": "Scheduling conflict detected"}, status=400)
        except PermissionDenied:
            return JsonResponse({"errors": "Access denied"}, status=403)
        except SystemException:
            return JsonResponse({"errors": "System error occurred"}, status=500)

    @staticmethod
    def _handle_invalid_form(form):
        """Handle invalid form submission."""
        logger.warning("Invalid tour form submitted")
        return JsonResponse({"errors": form.errors}, status=404)


class Update_I_TourFormJob(LoginRequiredMixin, View):
    """Update existing internal tour."""

    template_path = "schedhuler/schd_i_tourform_job.html"
    form_class = scd_forms.Schd_I_TourJobForm
    subform = scd_forms.SchdChild_I_TourJobForm
    service = InternalTourService()

    initial = Schd_I_TourFormJob.initial

    def get(self, request, *args, **kwargs):
        """Display tour update form."""
        pk = kwargs.get("pk")
        logger.info(f"Internal tour update form requested for ID: {pk}")

        try:
            job, checkpoints = self.service.get_tour_with_checkpoints(pk)

            form = self.form_class(instance=job, initial=self.initial)

            context = {
                "schdtourform": form,
                "childtour_form": self.subform(),
                "edit": True,
                "checkpoints": list(checkpoints),
            }

            return render(request, self.template_path, context=context)

        except ValidationError:
            messages.error(request, "Tour not found", "alert alert-danger")
            return redirect("/operations/tours/create/")
        except (DatabaseException, SystemException):
            messages.error(request, "System error occurred", "alert alert-danger")
            return redirect("/operations/tours/create/")


class Retrive_I_ToursJob(LoginRequiredMixin, View):
    """List internal tours."""

    template_path = "schedhuler/schd_e_tourlist_job.html"
    service = InternalTourService()

    def get(self, request, *args, **kwargs):
        """Display internal tours list."""
        logger.info("Internal tours list requested")

        try:
            filters = self._extract_filters(request.GET)
            page = int(request.GET.get('page', 1))

            tours = self.service.get_tours_list(filters=filters, page=page)

            context = {"tours": tours, "page": page}
            return render(request, self.template_path, context=context)

        except (DatabaseException, SystemException) as e:
            logger.error(f"Error retrieving tours list: {e}")
            messages.error(request, "Error loading tours", "alert alert-danger")
            return render(request, self.template_path, context={"tours": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters from request."""
        filters = {}
        if 'jobname' in query_params:
            filters['jobname'] = query_params['jobname']
        if 'people_id' in query_params:
            filters['people_id'] = query_params['people_id']
        return filters


class Retrive_I_ToursJobneed(LoginRequiredMixin, View):
    """List internal tour jobneeds."""

    template_path = "schedhuler/jobneed_list.html"
    service = InternalTourJobneedService()

    def get(self, request, *args, **kwargs):
        """Display jobneed list."""
        logger.info("Internal tour jobneeds list requested")

        try:
            filters = self._extract_filters(request.GET)
            page = int(request.GET.get('page', 1))

            jobneeds = self.service.get_jobneed_list(filters=filters, page=page)

            context = {"jobneeds": jobneeds, "page": page}
            return render(request, self.template_path, context=context)

        except (DatabaseException, SystemException) as e:
            logger.error(f"Error retrieving jobneeds: {e}")
            messages.error(request, "Error loading jobneeds", "alert alert-danger")
            return render(request, self.template_path, context={"jobneeds": []})

    @staticmethod
    def _extract_filters(query_params):
        """Extract filter parameters from request."""
        filters = {}
        if 'people_id' in query_params:
            filters['people_id'] = query_params['people_id']
        if 'status' in query_params:
            filters['status'] = query_params['status']
        return filters


class Get_I_TourJobneed(LoginRequiredMixin, View):
    """View specific internal tour jobneed."""

    template_path = "schedhuler/jobneed_detail.html"
    service = InternalTourJobneedService()

    def get(self, request, *args, **kwargs):
        """Display jobneed details."""
        pk = kwargs.get("pk")
        logger.info(f"Internal tour jobneed detail requested for ID: {pk}")

        try:
            jobneed = self.service.get_jobneed_by_id(pk)

            context = {"jobneed": jobneed}
            return render(request, self.template_path, context=context)

        except ValidationError:
            messages.error(request, "Jobneed not found", "alert alert-danger")
            return redirect("/operations/tours/internal/")
        except (DatabaseException, SystemException):
            messages.error(request, "System error occurred", "alert alert-danger")
            return redirect("/operations/tours/internal/")


@login_required
@require_http_methods(["POST"])
def add_cp_internal_tour(request):
    """Add checkpoint to internal tour (function-based view)."""
    logger.info("Add checkpoint to internal tour requested")

    try:
        tour_id = request.POST.get("tour_id")
        checkpoint_data = json.loads(request.POST.get("checkpoint_data"))

        service = InternalTourService()
        job = Job.objects.get(id=tour_id)

        service._save_checkpoints_for_tour(
            checkpoints=[checkpoint_data],
            job=job,
            user=request.user,
            session=request.session
        )

        return JsonResponse({"status": "success", "message": str(_("Checkpoint added"))}, status=200)

    except ValidationError as e:
        return JsonResponse({"errors": str(e)}, status=400)
    except (DatabaseException, SystemException):
        return JsonResponse({"errors": "System error occurred"}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_checkpoint(request):
    """Delete checkpoint from tour."""
    logger.info("Delete checkpoint requested")

    try:
        checkpoint_id = request.POST.get("checkpoint_id")

        service = InternalTourService()
        service.delete_checkpoint(checkpoint_id=checkpoint_id, user=request.user)

        return JsonResponse({"status": "success", "message": str(_("Checkpoint deleted"))}, status=200)

    except ValidationError as e:
        return JsonResponse({"errors": str(e)}, status=400)
    except (DatabaseException, SystemException):
        return JsonResponse({"errors": "System error occurred"}, status=500)