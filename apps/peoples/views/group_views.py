"""
People Group Views - Refactored with Service Layer

All view methods < 30 lines (Rule #8 compliant).
Business logic delegated to GroupManagementService.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.http.request import QueryDict

from apps.peoples.services import GroupManagementService
from apps.peoples.forms import PeopleGroupForm
from apps.core.utils_new.http_utils import get_clean_form_data, get_model_obj

logger = logging.getLogger(__name__)


class PeopleGroup(LoginRequiredMixin, View):
    """
    Refactored people group view using GroupManagementService.

    BEFORE: 130+ lines with complex group management logic
    AFTER: < 30 lines per method ✅
    """
    template_list = "peoples/peoplegroup_modern.html"
    template_form = "peoples/partials/partial_pgroup_form.html"

    def __init__(self):
        super().__init__()
        self.group_service = GroupManagementService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests for group data."""
        action = request.GET.get("action")

        if request.GET.get("template"):
            return render(request, self.template_list)

        if action == "list" or request.GET.get("search_term"):
            return self._handle_list(request)
        elif action == "form":
            return self._handle_form_create(request)
        elif action == "delete" and request.GET.get("id"):
            return self._handle_delete(request)
        elif request.GET.get("id"):
            return self._handle_form_update(request)

        return JsonResponse({"error": "Invalid action"}, status=400)

    def _handle_list(self, request: HttpRequest) -> JsonResponse:
        """Handle list view (< 10 lines)."""
        data = self.group_service.get_group_list(
            session=request.session
        )
        return JsonResponse({"data": data}, status=200)

    def _handle_form_create(self, request: HttpRequest) -> HttpResponse:
        """Render empty form (< 10 lines)."""
        context = {
            "pgroup_form": PeopleGroupForm(request=request),
            "msg": "create people group requested"
        }
        return render(request, self.template_form, context)

    def _handle_form_update(self, request: HttpRequest) -> HttpResponse:
        """Render form with existing data (< 20 lines)."""
        group_id = int(request.GET.get("id"))
        group = self.group_service.get_group(group_id)

        if not group:
            return JsonResponse({"error": "Group not found"}, status=404)

        peoples = self.group_service.get_group_members(group_id)

        context = {
            "pgroup_form": PeopleGroupForm(
                request=request,
                instance=group,
                initial={"peoples": peoples}
            )
        }
        return render(request, self.template_form, context)

    def _handle_delete(self, request: HttpRequest) -> JsonResponse:
        """Handle delete request (< 15 lines)."""
        group_id = int(request.GET.get("id"))
        result = self.group_service.delete_group(
            group_id=group_id,
            user=request.user,
            session=request.session
        )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle POST requests (< 30 lines)."""
        data = get_clean_form_data(request)
        pk = request.POST.get("pk", None)

        form = PeopleGroupForm(data, request=request)

        if form.is_valid():
            return self._process_valid_form(request, form, pk)
        else:
            return JsonResponse({"errors": form.errors}, status=400)

    def _process_valid_form(
        self,
        request: HttpRequest,
        form,
        pk: str
    ) -> JsonResponse:
        """Process valid form (< 25 lines)."""
        people_ids = form.cleaned_data.pop('peoples', [])

        if pk:
            result = self.group_service.update_group(
                group_id=int(pk),
                form_data=form.cleaned_data,
                people_ids=people_ids,
                user=request.user,
                session=request.session
            )
        else:
            result = self.group_service.create_group(
                form_data=form.cleaned_data,
                people_ids=people_ids,
                user=request.user,
                session=request.session
            )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)