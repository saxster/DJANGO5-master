"""
Asset list views for displaying asset data in various formats.

This module contains views for listing and filtering assets.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.db.models.functions import AsWKT
from django.shortcuts import render
from django.views.generic.base import View
from django.http import response as rp

from apps.activity.filters import MasterAssetFilter
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Jobneed
from apps.core import utils

logger = logging.getLogger(__name__)


class MasterAsset(LoginRequiredMixin, View):
    """View for master asset listing and management."""

    params = {
        "form_class": None,
        "template_form": "activity/partials/partial_masterasset_form.html",
        "template_list": "activity/master_asset_list.html",
        "partial_form": "peoples/partials/partial_masterasset_form.html",
        "partial_list": "peoples/partials/master_asset_list.html",
        "related": ["parent", "type"],
        "model": Asset,
        "filter": MasterAssetFilter,
        "fields": [
            "assetname",
            "assetcode",
            "runningstatus",
            "parent__assetcode",
            "gps",
            "id",
            "enable",
        ],
        "form_initials": {},
    }
    list_grid_lookups = {}
    view_of = label = None

    def get(self, request, *args, **kwargs):
        """Handle GET requests for master asset operations."""
        R, resp = request.GET, None

        # first load the template
        if R.get("template"):
            return render(request, self.params["template_list"], {"label": self.label})

        # return qset_list data
        if R.get("action", None) == "list" or R.get("search_term"):
            d = {"list": "master_assetlist", "filt_name": "master_asset_filter"}
            self.params.update(d)
            objs = (
                self.params["model"]
                .objects.annotate(gps=AsWKT("gpslocation"))
                .select_related(*self.params["related"])
                .filter(**self.list_grid_lookups)
                .values(*self.params["fields"])
            )
            utils.printsql(objs)
            return rp.JsonResponse(data={"data": list(objs)})

        # return questionset_form empty
        if R.get("action", None) == "form":
            self.params["form_initials"].update({"type": 1, "parent": 1})
            cxt = {
                "master_assetform": self.params["form_class"](
                    request=request, initial=self.params["form_initials"]
                ),
                "msg": f"create {self.label} requested",
                "label": self.label,
            }
            resp = utils.render_form(request, self.params, cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, self.params, True)
        # return form with instance
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, self.params)
            cxt = {"label": self.label}
            resp = utils.render_form_for_update(
                request, self.params, "master_assetform", obj, extra_cxt=cxt
            )
        return resp

    def post(self, request, *args, **kwargs):
        """Handle POST requests for master asset operations."""
        resp, create = None, False
        try:
            from apps.core.utils_new.http_utils import get_clean_form_data
            data = get_clean_form_data(request)
            if pk := request.POST.get("pk", None):
                msg = f"{self.label}_view"
                form = utils.get_instance_for_update(data, self.params, msg, int(pk))
                create = False
            else:
                form = self.params["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)
        except Exception:
            resp = utils.handle_Exception(request)
        return resp

    def handle_valid_form(self, form, request, create):
        """Handle valid form submission - must be implemented by subclasses."""
        raise NotImplementedError()


class AssetMaintenanceList(LoginRequiredMixin, View):
    """View for displaying asset maintenance list."""

    params = {
        "template_list": "activity/assetmaintainance_list.html",
        "model": Jobneed,
        "fields": [
            "id",
            "plandatetime",
            "jobdesc",
            "people__peoplename",
            "asset__assetname",
            "ctzoffset",
            "asset__runningstatus",
            "gpslocation",
            "identifier",
        ],
        "related": ["asset", "people"],
    }

    def get(self, request, *args, **kwargs):
        """Handle GET requests for asset maintenance list."""
        R, P = request.GET, self.params

        # first load the template
        if R.get("template"):
            return render(request, P["template_list"])

        if R.get("action") == "list":
            # last 3 months
            objs = P["model"].objects.get_assetmaintainance_list(
                request, P["related"], P["fields"]
            )
            return rp.JsonResponse({"data": list(objs)}, status=200)