"""
Site Group Views - Refactored with Service Layer

All view methods < 30 lines (Rule #8 compliant).
Business logic delegated to SiteGroupManagementService.
"""

import logging
import json
import html
import urllib.parse
from typing import List, Dict, Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from django.shortcuts import render
from django.views import View
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.http.request import QueryDict

from apps.peoples.services import SiteGroupManagementService
from apps.peoples.forms import SiteGroupForm
from apps.client_onboarding.models import Bt

logger = logging.getLogger(__name__)


@method_decorator(permission_required('peoples.view_pgbelonging', raise_exception=True), name='dispatch')
class SiteGroup(LoginRequiredMixin, View):
    """
    Refactored site group view using SiteGroupManagementService.

    BEFORE: 230+ lines with complex site assignment logic
    AFTER: < 30 lines per method ✅
    """
    template_list = "peoples/sitegroup_list_modern.html"
    template_form = "peoples/sitegroup_form.html"

    def __init__(self):
        super().__init__()
        self.site_group_service = SiteGroupManagementService()

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle GET requests for site group data."""
        action = request.GET.get("action")

        if request.GET.get("template"):
            return render(request, self.template_list)

        if action == "list":
            return self._handle_list(request)
        elif action == "allsites":
            return self._handle_all_sites(request)
        elif action == "loadSites":
            return self._handle_load_sites(request)
        elif action == "form":
            return self._handle_form_create(request)
        elif action == "delete" and request.GET.get("id"):
            return self._handle_delete(request)
        elif request.GET.get("id"):
            return self._handle_form_update(request)

        return JsonResponse({"error": "Invalid action"}, status=400)

    def _handle_list(self, request: HttpRequest) -> JsonResponse:
        """Handle list view with pagination (< 10 lines)."""
        result = self.site_group_service.get_site_group_list(
            request_params=request.GET.dict(),
            session=request.session
        )
        return JsonResponse(result, status=200)

    def _handle_all_sites(self, request: HttpRequest) -> JsonResponse:
        """Handle all sites query (< 10 lines)."""
        butype = request.GET.get("sel_butype")
        objs, idfs = Bt.objects.get_bus_idfs(
            request.GET, request=request, idf=butype
        )
        return JsonResponse({"data": list(objs), "idfs": list(idfs)})

    def _handle_load_sites(self, request: HttpRequest) -> JsonResponse:
        """Handle load assigned sites (< 20 lines)."""
        site_group_id = request.GET.get("id")

        if not site_group_id or not site_group_id.strip():
            return JsonResponse(
                {"assigned_sites": [], "error": "Site group ID required"},
                status=400
            )

        try:
            group_id = int(site_group_id)
            data = self.site_group_service.get_assigned_sites(group_id)
            return JsonResponse({"assigned_sites": data})
        except (ValueError, TypeError):
            return JsonResponse(
                {"assigned_sites": [], "error": "Invalid site group ID"},
                status=400
            )

    def _handle_form_create(self, request: HttpRequest) -> HttpResponse:
        """Render empty form (< 10 lines)."""
        context = {
            "sitegrpform": SiteGroupForm(request=request),
            "msg": "create site group requested"
        }
        return render(request, self.template_form, context)

    def _handle_form_update(self, request: HttpRequest) -> HttpResponse:
        """Render form with existing data (< 15 lines)."""
        group_id = int(request.GET.get("id"))
        group = self.site_group_service.get_site_group(group_id)

        if not group:
            return JsonResponse({"error": "Site group not found"}, status=404)

        sites = self.site_group_service.get_assigned_sites(group_id)
        context = {
            "sitegrpform": SiteGroupForm(request=request, instance=group),
            "assignedsites": sites
        }
        return render(request, self.template_form, context)

    def _handle_delete(self, request: HttpRequest) -> JsonResponse:
        """Handle delete request (< 15 lines)."""
        group_id = int(request.GET.get("id"))
        result = self.site_group_service.delete_site_group(
            group_id=group_id,
            user=request.user,
            session=request.session
        )

        if result.success:
            return JsonResponse(None, status=200, safe=False)
        else:
            return JsonResponse({"error": result.error_message}, status=400)

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle POST requests (< 30 lines)."""
        raw_form_data = request.POST.get("formData", "")
        data = QueryDict(html.unescape(raw_form_data) if '&amp;' in raw_form_data else raw_form_data)

        assigned_sites = self._parse_assigned_sites(request)
        if isinstance(assigned_sites, JsonResponse):
            return assigned_sites

        form = SiteGroupForm(data, request=request)

        if form.is_valid():
            return self._process_valid_form(request, form, data, assigned_sites)
        else:
            return JsonResponse({"errors": form.errors}, status=400)

    def _parse_assigned_sites(
        self,
        request: HttpRequest
    ) -> List[Dict[str, Any]]:
        """Parse assigned sites JSON (< 20 lines)."""
        try:
            assigned_sites_raw = request.POST.get("assignedSites", "[]")

            if assigned_sites_raw.startswith('%5B'):
                assigned_sites_raw = urllib.parse.unquote(assigned_sites_raw)

            assigned_sites_raw = html.unescape(assigned_sites_raw)
            return json.loads(assigned_sites_raw)

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse assignedSites: {str(e)}")
            return JsonResponse(
                {"error": "Invalid JSON format for assigned sites"},
                status=400
            )

    def _process_valid_form(
        self,
        request: HttpRequest,
        form,
        data: QueryDict,
        assigned_sites: List[Dict[str, Any]]
    ) -> JsonResponse:
        """Process valid form (< 25 lines)."""
        pk = data.get("pk", None)

        if pk and pk not in ["None", ""] and pk.strip():
            result = self.site_group_service.update_site_group(
                group_id=int(pk),
                form_data=form.cleaned_data,
                assigned_sites=assigned_sites,
                user=request.user,
                session=request.session
            )
        else:
            result = self.site_group_service.create_site_group(
                form_data=form.cleaned_data,
                assigned_sites=assigned_sites,
                user=request.user,
                session=request.session
            )

        if result.success:
            return JsonResponse(result.data, status=200)
        else:
            return JsonResponse({"error": result.error_message}, status=400)