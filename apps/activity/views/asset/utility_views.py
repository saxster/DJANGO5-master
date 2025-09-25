"""
Asset utility views for specialized asset operations.

This module contains views for asset-related utilities like checkpoints,
people near assets, and asset logs.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.shortcuts import render
from django.views.generic.base import View
from django.http import response as rp

from apps.activity.forms.asset_form import CheckpointForm
from apps.activity.models.asset_model import Asset, AssetLog
from apps.core import utils
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class PeopleNearAsset(LoginRequiredMixin, View):
    """View for displaying people near assets."""

    params = {
        "template_list": "activity/peoplenearasset.html",
        "model": Asset,
        "related": [],
        "fields": ["id", "assetcode", "assetname", "identifier", "gpslocation"],
    }

    def get(self, request, *args, **kwargs):
        """Handle GET requests for people near asset data."""
        R, P = request.GET, self.params

        # first load the template for initial page load
        if R.get("template"):
            return render(request, self.params["template_list"])

        # handle AJAX data requests for table
        if R.get("action", None) == "list" or R.get("search_term"):
            objs = self.params["model"].objects.get_peoplenearasset(request)
            return rp.JsonResponse(data={"data": list(objs)}, safe=False)

        # handle form actions - for now just return the list template
        # In the future, this could be extended to show detail view or edit form
        if R.get("action", None) == "form":
            return render(request, self.params["template_list"])

        # Default case - return the list template
        return render(request, self.params["template_list"])


class Checkpoint(LoginRequiredMixin, View):
    """View for managing checkpoint assets."""

    params = {
        "form_class": CheckpointForm,
        "template_form": "activity/partials/partial_checkpoint_form.html",
        "template_list": "activity/checkpoint_list.html",
        "partial_form": "peoples/partials/partial_checkpoint_form.html",
        "partial_list": "peoples/partials/chekpoint_list.html",
        "related": ["parent", "type", "bu", "location"],
        "model": Asset,
        "fields": [
            "assetname",
            "assetcode",
            "runningstatus",
            "identifier",
            "location__locname",
            "parent__assetname",
            "gps",
            "id",
            "enable",
            "bu__buname",
            "bu__bucode",
        ],
        "form_initials": {
            "runningstatus": "WORKING",
            "identifier": "CHECKPOINT",
            "iscritical": False,
            "enable": True,
        },
    }

    def get(self, request, *args, **kwargs):
        """Handle GET requests for checkpoint operations."""
        R, resp, P = request.GET, None, self.params

        # first load the template
        if R.get("template"):
            return render(request, P["template_list"], {"label": "Checkpoint"})

        # return qset_list data
        if R.get("action", None) == "list":
            objs = P["model"].objects.get_checkpointlistview(
                request, P["related"], P["fields"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if (
            R.get("action", None) == "qrdownload"
            and R.get("code", None)
            and R.get("name", None)
        ):
            return utils.download_qrcode(
                R["code"], R["name"], "CHECKPOINTQR", request.session, request
            )

        # return questionset_form empty
        if R.get("action", None) == "form":
            P["form_initials"].update({"type": 1, "parent": 1})
            cxt = {
                "master_assetform": P["form_class"](
                    request=request, initial=P["form_initials"]
                ),
                "msg": "create checkpoint requested",
                "label": "Checkpoint",
            }

            resp = utils.render_form(request, P, cxt)

        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, P, True)
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            cxt = {"label": "Checkpoint"}
            resp = utils.render_form_for_update(
                request, P, "master_assetform", obj, extra_cxt=cxt
            )
        return resp

    def post(self, request, *args, **kwargs):
        """Handle POST requests for checkpoint operations."""
        resp, create, P = None, False, self.params
        try:
            from apps.core.utils_new.http_utils import get_clean_form_data
            data = get_clean_form_data(request)
            if pk := request.POST.get("pk", None):
                msg = "Checkpoint_view"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), kwargs={"request": request}
                )
                create = False
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, P, cxt)
        except Exception:
            resp = utils.handle_Exception(request)
        return resp

    def handle_valid_form(self, form, request, create):
        """Handle valid checkpoint form submission."""
        P = self.params
        try:
            cp = form.save(commit=False)
            cp.gpslocation = form.cleaned_data["gpslocation"]
            putils.save_userinfo(cp, request.user, request.session, create=create)
            data = {
                "msg": f"{cp.assetcode}",
                "row": Asset.objects.get_checkpointlistview(
                    request, P["related"], P["fields"], id=cp.id
                ),
            }
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return utils.handle_intergrity_error("Checkpoint")


class AssetLogView(LoginRequiredMixin, View):
    """View for displaying asset logs."""

    params = {"model": AssetLog, "template_list": "activity/asset_log.html"}

    def get(self, request):
        """Handle GET requests for asset log data."""
        R, P = request.GET, self.params

        if R.get("template"):
            return render(request, P["template_list"])

        if R.get("action") == "asset_log":
            data = P["model"].objects.get_asset_logs(request)
            return rp.JsonResponse(data, status=200)