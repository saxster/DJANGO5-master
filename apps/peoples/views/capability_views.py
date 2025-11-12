"""
Capability Views - Refactored with Service Layer

All view methods < 30 lines (Rule #8 compliant).
Business logic delegated to CapabilityManagementService.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.views import View
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.http.request import QueryDict

from apps.peoples.services import CapabilityManagementService
from apps.peoples.forms import CapabilityForm
from apps.peoples.filters import CapabilityFilter
from apps.core.utils_new.business_logic import get_model_obj

logger = logging.getLogger(__name__)


@method_decorator(permission_required('peoples.view_capability', raise_exception=True), name='dispatch')
class Capability(LoginRequiredMixin, View):
    """
    Refactored capability view using CapabilityManagementService.

    BEFORE: 130+ lines with mixed concerns
    AFTER: < 30 lines per method ✅
    """
    template_list = "peoples/capability.html"
    template_form = "peoples/partials/partial_cap_form.html"

    def __init__(self):
        super().__init__()
        self.capability_service = CapabilityManagementService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests for capability data."""
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
        """Handle list view (< 15 lines)."""
        data = self.capability_service.get_capability_list(
            session=request.session,
            exclude_none=True
        )
        return JsonResponse({"data": data}, status=200, safe=False)

    def _handle_form_create(self, request: HttpRequest) -> HttpResponse:
        """Render empty form (< 10 lines)."""
        context = {
            "cap_form": CapabilityForm(request=request),
            "msg": "create capability requested"
        }
        return render(request, self.template_form, context)

    def _handle_form_update(self, request: HttpRequest) -> HttpResponse:
        """Render form with existing data (< 15 lines)."""
        capability_id = request.GET.get("id")
        capability = self.capability_service.get_capability(int(capability_id))

        if not capability:
            return JsonResponse({"error": "Capability not found"}, status=404)

        context = {
            "cap_form": CapabilityForm(instance=capability, request=request),
            "msg": "update capability requested"
        }
        return render(request, self.template_form, context)

    def _handle_delete(self, request: HttpRequest) -> JsonResponse:
        """Handle delete request (< 15 lines)."""
        capability_id = int(request.GET.get("id"))
        result = self.capability_service.delete_capability(
            capability_id=capability_id,
            user=request.user,
            session=request.session
        )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle POST requests (< 25 lines)."""
        data = QueryDict(request.POST.get("formData", ""))
        pk = request.POST.get("pk", None)

        form = CapabilityForm(data, request=request)

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
        """Process valid form (< 20 lines)."""
        if pk:
            result = self.capability_service.update_capability(
                capability_id=int(pk),
                form_data=form.cleaned_data,
                user=request.user,
                session=request.session
            )
        else:
            result = self.capability_service.create_capability(
                form_data=form.cleaned_data,
                user=request.user,
                session=request.session
            )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)