"""
People Views - Refactored with Service Layer

All view methods < 30 lines (Rule #8 compliant).
Business logic delegated to PeopleManagementService.
"""

import logging
import html
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.http.request import QueryDict

from apps.peoples.services import PeopleManagementService
from apps.peoples.forms import PeopleForm, PeopleExtrasForm
from apps.core_onboarding.forms import TypeAssistForm
from apps.core.utils_new.business_logic import get_model_obj
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class PeopleView(LoginRequiredMixin, View):
    """
    Refactored people view using PeopleManagementService.

    BEFORE: 230+ lines with complex business logic
    AFTER: < 30 lines per method ✅
    """
    template_list = "peoples/people_list_modern.html"
    template_form = "peoples/people_form.html"

    def __init__(self):
        super().__init__()
        self.people_service = PeopleManagementService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests for people data."""
        action = request.GET.get("action")

        if request.GET.get("template") == "true":
            return render(request, self.template_list)

        if action == "list" or request.GET.get("search_term"):
            return self._handle_list(request)
        elif action == "form":
            return self._handle_form_create(request)
        elif action == "delete" and request.GET.get("id"):
            return self._handle_delete(request)
        elif request.GET.get("id"):
            return self._handle_form_update(request)
        else:
            return redirect(f"{request.path}?template=true")

    def _handle_list(self, request: HttpRequest) -> JsonResponse:
        """Handle list view with pagination (< 20 lines)."""
        result = self.people_service.get_people_list(
            request_params=request.GET.dict(),
            session=request.session
        )

        return JsonResponse({
            "draw": result.draw,
            "recordsTotal": result.total,
            "recordsFiltered": result.filtered,
            "data": result.data
        }, status=200)

    def _handle_form_create(self, request: HttpRequest) -> HttpResponse:
        """Render empty form for creation (< 15 lines)."""
        context = {
            "peopleform": PeopleForm(request=request),
            "pref_form": PeopleExtrasForm(request=request),
            "ta_form": TypeAssistForm(auto_id=False, request=request),
            "msg": "create people requested"
        }
        return render(request, self.template_form, context)

    def _handle_form_update(self, request: HttpRequest) -> HttpResponse:
        """Render form with existing data (< 20 lines)."""
        people_id = request.GET.get("id")
        people = self.people_service.get_people(
            people_id=people_id,
            session=request.session
        )

        if not people:
            return JsonResponse({"error": "People not found"}, status=404)

        context = {
            "peopleform": PeopleForm(instance=people, request=request),
            "pref_form": putils.get_people_prefform(people, request),
            "ta_form": TypeAssistForm(auto_id=False, request=request),
            "msg": "update people requested"
        }
        return render(request, self.template_form, context)

    def _handle_delete(self, request: HttpRequest) -> JsonResponse:
        """Handle delete request (< 15 lines)."""
        people_id = request.GET.get("id")
        result = self.people_service.delete_people(
            people_id=people_id,
            user=request.user,
            session=request.session
        )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle POST requests for create/update (< 30 lines)."""
        form_data_string = request.POST.get("formData", "")
        decoded_form_data = html.unescape(form_data_string)
        data = QueryDict(decoded_form_data)

        pk = request.POST.get("pk", None)
        form = PeopleForm(data, files=request.FILES, request=request)
        jsonform = PeopleExtrasForm(data, request=request)

        if form.is_valid() and jsonform.is_valid():
            return self._process_valid_form(request, form, jsonform, pk)
        else:
            errors = dict(form.errors)
            errors.update(jsonform.errors)
            return JsonResponse({"errors": errors}, status=400)

    def _process_valid_form(
        self,
        request: HttpRequest,
        form,
        jsonform,
        pk: str
    ) -> JsonResponse:
        """Process valid form data (< 20 lines)."""
        if pk:
            result = self.people_service.update_people(
                people_id=int(pk),
                form_data=form.cleaned_data,
                json_form_data=jsonform.cleaned_data,
                user=request.user,
                session=request.session,
                files=request.FILES
            )
        else:
            result = self.people_service.create_people(
                form_data=form.cleaned_data,
                json_form_data=jsonform.cleaned_data,
                user=request.user,
                session=request.session,
                files=request.FILES
            )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)