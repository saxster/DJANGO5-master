import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.http import response as rp
from django.shortcuts import render
from django.views.generic.base import View
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import ActivityManagementException, DatabaseException, SystemException
from apps.activity.models.location_model import Location
from apps.activity.forms.location_form import LocationForm
import apps.peoples.utils as putils
from apps.core import utils

logger = logging.getLogger("django")


class LocationView(LoginRequiredMixin, View):
    P = {
        "template_form": "activity/location_form.html",
        "template_list": "activity/location_list.html",
        "model": Location,
        "form": LocationForm,
        "related": ["parent", "bu"],
        "fields": [
            "id",
            "loccode",
            "locname",
            "parent__locname",
            "locstatus",
            "enable",
            "bu__bucode",
            "bu__buname",
            "gps",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.P

        # first load the template
        if R.get("template"):
            return render(request, P["template_list"])

        # return qset_list data
        if R.get("action", None) == "list":
            objs = P["model"].objects.get_locationlistview(
                P["related"], P["fields"], request
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if (
            R.get("action", None) == "qrdownload"
            and R.get("code", None)
            and R.get("name", None)
        ):
            return utils.download_qrcode(
                R["code"], R["name"], "LOCATIONQR", request.session, request
            )

        # return questionset_form empty
        if R.get("action", None) == "form":
            cxt = {
                "locationform": P["form"](request=request),
                "msg": "create location requested",
            }
            resp = render(request, P["template_form"], cxt)

        if R.get("action", None) == "delete" and R.get("id", None):
            return utils.render_form_for_delete(request, P, True)

        if R.get("action") == "loadAssets":
            objs = P["model"].objects.get_assets_of_location(request)
            return rp.JsonResponse({"options": list(objs)}, status=200)

        # return form with instance
        elif R.get("id", None):
            asset = utils.get_model_obj(R["id"], request, P)
            cxt = {
                "locationform": P["form"](instance=asset, request=request),
                "msg": "Location Update Requested",
            }
            resp = render(request, P["template_form"], context=cxt)
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        from apps.core.utils_new.http_utils import get_clean_form_data
        data = get_clean_form_data(request)
        try:
            if pk := request.POST.get("pk", None):
                msg, create = "location_view", False
                people = utils.get_model_obj(pk, request, self.P)
                form = self.P["form"](data, request=request, instance=people)
            else:
                form = self.P["form"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.P, cxt)
        except ValidationError as e:
            logger.warning(f"LocationView form validation error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Location form validation failed")
            resp = rp.JsonResponse({"error": "Invalid form data", "details": str(e)}, status=400)
        except ActivityManagementException as e:
            logger.error(f"LocationView activity management error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Location activity management error")
            resp = rp.JsonResponse({"error": "Activity management error", "correlation_id": error_data.get("correlation_id")}, status=422)
        except PermissionDenied as e:
            logger.warning(f"LocationView permission denied: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Location access denied")
            resp = rp.JsonResponse({"error": "Access denied", "correlation_id": error_data.get("correlation_id")}, status=403)
        except (ValueError, TypeError) as e:
            logger.warning(f"LocationView data processing error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Location data processing error")
            resp = rp.JsonResponse({"error": "Invalid data format", "correlation_id": error_data.get("correlation_id")}, status=400)
        except SystemException as e:
            logger.error(f"LocationView system error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Location system error")
            resp = rp.JsonResponse({"error": "System error occurred", "correlation_id": error_data.get("correlation_id")}, status=500)
        return resp

    @staticmethod
    def handle_valid_form(form, request, create):
        logger.info("location form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            location = form.save(commit=False)
            location.gpslocation = form.cleaned_data["gpslocation"]
            location.save()
            location = putils.save_userinfo(
                location, request.user, request.session, create=create
            )
            logger.info("location form saved")
            data = {"pk": location.id}
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return handle_intergrity_error("Location")
