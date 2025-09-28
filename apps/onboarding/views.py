import logging
from typing import Type
import os
import html
from django.http import response as rp
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Q, F, Count, Case, When, IntegerField
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db import IntegrityError, transaction
from django.conf import settings
from django.http.request import QueryDict
from .models import Shift, TypeAssist, Bt, GeofenceMaster, Device, Subscription
from apps.peoples.utils import save_userinfo
from apps.core import utils
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Job, Jobneed
from apps.peoples.models import Pgbelonging
from apps.attendance.models import PeopleEventlog
import apps.onboarding.forms as obforms
import apps.peoples.utils as putils
import apps.onboarding.utils as obutils
from apps.peoples import admin as people_admin
from apps.onboarding import admin as ob_admin
from apps.activity.admin.asset_admin import AssetResource, AssetResourceUpdate
from apps.activity.admin.location_admin import LocationResource, LocationResourceUpdate
from apps.activity.admin.question_admin import (
    QuestionResource,
    QuestionResourceUpdate,
    QuestionSetResource,
    QuestionSetResourceUpdate,
    QuestionSetBelongingResource,
    QuestionSetBelongingResourceUpdate,
)
from apps.schedhuler import admin as sc_admin
from apps.y_helpdesk.models import Ticket
from apps.work_order_management.models import Wom
from apps.work_order_management.admin import VendorResource, VendorResourceUpdate
from django.core.exceptions import ObjectDoesNotExist, ValidationError, DatabaseError
from pprint import pformat
import uuid
import json
from apps.core.utils import polygon_to_address
from apps.core.utils_new.db_utils import get_current_db_name

CACHE_TTL = getattr(settings, "CACHE_TTL", DEFAULT_TIMEOUT)

logger = logging.getLogger("django")
log = logger


def get_caps(request):  # sourcery skip: extract-method
    logger.info("get_caps requested")
    selected_parents = request.GET.getlist("webparents[]")
    logger.info(f"selected_parents {selected_parents}")
    cfor = request.GET.get("cfor")
    logger.info(f"cfor {cfor}")
    if selected_parents:
        from apps.peoples.models import Capability

        childs = []
        for i in selected_parents:
            child = Capability.objects.get_child_data(i, cfor)
            childs.extend({"capscode": j.capscode} for j in child)
        logger.info(f"childs = [] {childs}")
        return rp.JsonResponse(data=childs, safe=False)


def handle_pop_forms(request):
    if request.method != "POST":
        return
    form_name = request.POST.get("form_name")
    form_dict = {
        "ta_form": obforms.TypeAssistForm,
    }
    form = form_dict[form_name](request.POST, request=request)
    if not form.is_valid():
        return rp.JsonResponse({"saved": False, "errors": form.errors})
    ta = form.save(commit=False)
    ta.enable = True
    form.save(commit=True)
    save_userinfo(ta, request.user, request.session)
    if request.session.get("wizard_data"):
        request.session["wizard_data"]["taids"].append(ta.id)
    return rp.JsonResponse({"saved": True, "id": ta.id, "tacode": ta.tacode})


# -------------------- END Client View Classes ------------------------------#

# ---------------------------- END client onboarding   ---------------------------#


class SuperTypeAssist(LoginRequiredMixin, View):
    params = {
        "form_class": obforms.SuperTypeAssistForm,
        "template_form": "onboarding/partials/partial_ta_form.html",
        "template_list": "onboarding/supertypeassist.html",
        "partial_form": "onboarding/partials/partial_ta_form.html",
        "related": ["parent", "cuser", "muser"],
        "model": TypeAssist,
        "fields": [
            "id",
            "tacode",
            "client__bucode",
            "bu__bucode",
            "taname",
            "tatype__tacode",
            "cuser__peoplecode",
        ],
        "form_initials": {},
    }

    def get(self, request, *args, **kwargs):
        R, resp = request.GET, None
        # first load the template
        if R.get("template"):
            return render(request, self.params["template_list"])
        # then load the table with objects for table_view
        if R.get("action") == "list":
            objs = (
                self.params["model"]
                .objects.select_related(*self.params["related"])
                .filter(~Q(tacode="NONE"), enable=True)
                .values(*self.params["fields"])
                .iterator()
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if R.get("action", None) == "form":
            cxt = {
                "ta_form": self.params["form_class"](request=request),
                "msg": "create supertypeassist requested",
            }
            resp = utils.render_form(request, self.params, cxt)

        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, self.params, True)

        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, self.params)
            resp = utils.render_form_for_update(request, self.params, "ta_form", obj)
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        R = request.POST
        try:
            form_data = html.unescape(request.POST["formData"])
            data = QueryDict(form_data)
            pk = request.POST.get("pk", None)
            if pk:
                msg = "supertypeassist_view"
                form = utils.get_instance_for_update(
                    data, self.params, msg, int(pk), {"request": request}
                )
                create = False
            else:
                form = self.params["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)
        except (ValidationError, ValueError) as e:

            logger.error(

                f"Validation error in onboarding view: {type(e).__name__}",

                extra={'error_message': str(e), 'user_id': request.user.id, 'view': self.__class__.__name__}

            )

            resp = utils.handle_invalid_form(request, self.params, {"errors": {"form": str(e)}})

        except (DatabaseError, IntegrityError) as e:

            logger.error(

                f"Database error in onboarding view: {type(e).__name__}",

                extra={'error_message': str(e), 'user_id': request.user.id, 'view': self.__class__.__name__}

            )

            resp = utils.handle_intergrity_error("Onboarding")

        except (ValidationError, ValueError, TypeError) as e:


            logger.error(


                f"Validation error: {type(e).__name__}",


                extra={'error_message': str(e), 'user_id': getattr(request, 'user', {}), 'operation': 'onboarding'},


                exc_info=True


            )


            resp = utils.handle_Exception(request)


        except (DatabaseError, IntegrityError) as e:


            logger.error(


                f"Database error: {type(e).__name__}",


                extra={'error_message': str(e), 'operation': 'onboarding'},


                exc_info=True


            )


            resp = utils.handle_Exception(request)


        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:


            logger.critical(


                f"Unexpected error: {type(e).__name__}",


                extra={'error_message': str(e), 'operation': 'onboarding'},


                exc_info=True


            )


            resp = utils.handle_Exception(request)
        return resp

    def handle_valid_form(self, form, request, create, designations_count, obj):
        logger.info("bu form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            with transaction.atomic(using=get_current_db_name()):
                bu = form.save(commit=False)
                bu.enable = obj.enable
                bu.gpslocation = obj.gpslocation
                bu.bupreferences["permissibledistance"] = obj.bupreferences[
                    "permissibledistance"
                ]
                bu.bupreferences["controlroom"] = obj.bupreferences["controlroom"]
                bu.bupreferences["address"] = obj.bupreferences["address"]
                bu.bupreferences["address2"] = obj.bupreferences["address2"]
                bu.butype = obj.butype
                bu.ctzoffset = obj.ctzoffset
                bu.deviceevent = obj.deviceevent
                bu.enablesleepingguard = obj.enablesleepingguard
                bu.gpsenable = obj.gpsenable
                bu.identifier = obj.identifier
                bu.isserviceprovider = obj.isserviceprovider
                bu.isvendor = obj.isvendor
                bu.iswarehouse = obj.iswarehouse
                bu.parent = obj.parent
                bu.siteincharge = obj.siteincharge
                bu.skipsiteaudit = obj.skipsiteaudit
                bu.solid = obj.solid

                bu.bupreferences["posted_people"] = form.cleaned_data["posted_people"]
                bu.bupreferences["contract_designcount"] = form.cleaned_data["jsonData"]
                bu.bupreferences["total_people_count"] = form.cleaned_data[
                    "total_people_count"
                ]
                putils.save_userinfo(bu, request.user, request.session, create=create)
                logger.info("bu form saved")

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return rp.JsonResponse({"pk": bu.id, "status": "success", "message": "Contract saved successfully"}, status=200)
                else:
                    from django.contrib import messages
                    messages.success(request, "Contract saved successfully")
                    return rp.HttpResponseRedirect(f"/admin/contracts/?id={bu.id}")
        except IntegrityError:
            return handle_intergrity_error("Bu")


class GetAllSites(LoginRequiredMixin, View):
    def get(self, request):
        try:
            qset = Bt.objects.get_all_sites_of_client(request.session["client_id"])
            sites = qset.values("id", "bucode", "buname")
            return rp.JsonResponse(list(sites), status=200)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error("get_allsites() exception: %s", e)
        return rp.JsonResponse({"error": "Invalid Request"}, status=404)


class GetAssignedSites(LoginRequiredMixin, View):
    def get(self, request):
        try:
            if data := Pgbelonging.objects.get_assigned_sites_to_people(
                request.user.id
            ):
                sites = Bt.objects.filter(id__in=data).values("id", "bucode", "buname")
                return rp.JsonResponse(list(sites), status=200, safe=False)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error("get_assignedsites() exception: %s", e)
        return rp.JsonResponse({"error": "Invalid Request"}, status=404)


class SwitchSite(LoginRequiredMixin, View):
    def post(self, request):
        req_buid = request.POST["buid"]
        resp = {}
        if req_buid != " ":
            sites = Bt.objects.filter(id=req_buid).values(
                "id", "bucode", "buname", "enable"
            )[:1]
            if len(sites) > 0:
                if sites[0]["enable"] == True:
                    request.session["bu_id"] = sites[0]["id"]
                    request.session["sitecode"] = sites[0]["bucode"]
                    request.session["sitename"] = sites[0]["buname"]
                    resp["rc"] = 0
                    resp["message"] = "successfully switched to site."
                    log.info("successfully switched to site")
                else:
                    resp["rc"] = 1
                    resp["errMsg"] = "Inactive Site"
                    log.info("Inactive Site")
            else:
                resp["rc"] = 1
                resp["errMsg"] = "unable to find site."
                log.info("unable to find site.")
        else:
            resp["rc"] = 1
            resp["errMsg"] = "unable to find site."
            log.info("unable to find site.")
        return rp.JsonResponse(resp, status=200)


def get_list_of_peoples(request):
    if request.method == "POST":
        return
    Model = apps.get_model("activity", request.GET["model"])
    obj = Model.objects.get(id=request.GET["id"])
    Pgbelonging = apps.get_model("peoples", "Pgbelonging")
    data = (
        Pgbelonging.objects.filter(
            Q(assignsites_id=1) | Q(assignsites__isnull=True), pgroup_id=obj.pgroup_id
        ).values("people__peoplecode", "people__peoplename", "id")
        or Pgbelonging.objects.none()
    )
    return rp.JsonResponse({"data": list(data)}, status=200)
