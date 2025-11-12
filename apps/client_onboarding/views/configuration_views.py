import logging
from typing import Type
import html
from django.utils.translation import gettext_lazy as _
from django.http import response as rp
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Q
from django.db import IntegrityError, transaction
from django.conf import settings
from django.http.request import QueryDict
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError

from ..models import TypeAssist
from apps.core import utils
from apps.peoples.utils import save_userinfo
from .. import forms as client_forms
from apps.core.utils_new.db_utils import get_current_db_name
import apps.peoples.utils as putils

CACHE_TTL = getattr(settings, "CACHE_TTL", DEFAULT_TIMEOUT)

logger = logging.getLogger("django")


def get_caps(request):
    """Get capability data based on selected parents."""
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
    """Handle popup form submissions for TypeAssist."""
    if request.method != "POST":
        return
    form_name = request.POST.get("form_name")
    form_dict = {
        "ta_form": client_forms.TypeAssistForm,
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


class SuperTypeAssist(LoginRequiredMixin, View):
    """Super TypeAssist configuration view."""
    params = {
        "form_class": client_forms.SuperTypeAssistForm,
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
        if R.get("template"):
            return render(request, self.params["template_list"])
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
        """
        Handle POST requests for SuperTypeAssist.

        REFACTORED (Oct 2025): Consolidated overlapping exception handlers
        from 84 lines (4 duplicate blocks) to 30 lines (single comprehensive handler).
        """
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

        except (ValidationError, ValueError, TypeError) as e:
            logger.error(
                f"Validation error in SuperTypeAssist: {type(e).__name__}",
                extra={
                    'error_message': str(e),
                    'user_id': getattr(request.user, 'id', None),
                    'view': self.__class__.__name__,
                    'operation': 'supertypeassist_post'
                },
                exc_info=True
            )
            resp = utils.handle_invalid_form(request, self.params, {"errors": {"form": str(e)}})

        except (DatabaseError, IntegrityError) as e:
            logger.error(
                f"Database error in SuperTypeAssist: {type(e).__name__}",
                extra={
                    'error_message': str(e),
                    'user_id': getattr(request.user, 'id', None),
                    'view': self.__class__.__name__,
                    'operation': 'supertypeassist_post'
                },
                exc_info=True
            )
            resp = utils.handle_intergrity_error("Onboarding")

        except ObjectDoesNotExist as e:
            logger.warning(
                f"Object not found in SuperTypeAssist: {type(e).__name__}",
                extra={
                    'error_message': str(e),
                    'user_id': getattr(request.user, 'id', None),
                    'view': self.__class__.__name__
                }
            )
            resp = utils.handle_Exception(request)

        return resp

    def handle_valid_form(self, form, request, create, designations_count=None, obj=None):
        """Handle valid form submission."""
        logger.info("bu form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            with transaction.atomic(using=get_current_db_name()):
                bu = form.save(commit=False)
                if obj:
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
                    return rp.JsonResponse({"pk": bu.id, "status": "success", "message": str(_("Contract saved successfully"))}, status=200)
                else:
                    from django.contrib import messages
                    messages.success(request, _("Contract saved successfully"))
                    return rp.HttpResponseRedirect(f"/admin/contracts/?id={bu.id}")
        except IntegrityError:
            return handle_intergrity_error("Bu")
