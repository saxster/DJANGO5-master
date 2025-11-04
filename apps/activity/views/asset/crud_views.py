"""
Asset CRUD (Create, Read, Update, Delete) views.

This module contains views for basic asset operations.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.http import response as rp
from django.shortcuts import render
from django.views.generic.base import View
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import ActivityManagementException, DatabaseException, SystemException

from apps.activity.forms.asset_form import AssetForm, AssetExtrasForm
from apps.activity.models.asset_model import Asset
from apps.core import utils
from apps.activity.utils import get_asset_jsonform
import apps.activity.utils as av_utils
from apps.client_onboarding import forms as client_forms
import apps.peoples.utils as putils
from apps.core.constants import ResponseConstants

logger = logging.getLogger(__name__)


@method_decorator(csrf_protect, name='post')
class AssetView(LoginRequiredMixin, View):
    """Main view for asset CRUD operations."""

    P = {
        "template_form": "activity/asset_form.html",
        "template_list": "activity/asset_list.html",
        "model": Asset,
        "form": AssetForm,
        "jsonform": AssetExtrasForm,
        "related": ["parent", "location", "bu"],
        "fields": [
            "assetcode",
            "assetname",
            "id",
            "parent__assetname",
            "bu__bucode",
            "runningstatus",
            "enable",
            "gps",
            "identifier",
            "location__locname",
            "bu__buname",
        ],
    }

    def get(self, request, *args, **kwargs):
        """Handle GET requests for asset operations."""
        R, P = request.GET, self.P

        # Handle type=QUESTIONSET redirect
        if R.get("type") == "QUESTIONSET":
            # Redirect to QuestionSet view
            from django.shortcuts import redirect
            from django.urls import reverse
            # Preserve query parameters
            query_string = request.META.get('QUERY_STRING', '')
            return redirect(f"{reverse('assets:checklists_list')}?{query_string}")

        # first load the template
        if R.get("template"):
            return render(request, P["template_list"])

        # return qset_list data
        if R.get("action", None) == "list":
            objs = P["model"].objects.get_assetlistview(
                P["related"], P["fields"], request
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if (
            R.get("action", None) == "qrdownload"
            and R.get("code", None)
            and R.get("name", None)
        ):
            return utils.download_qrcode(
                R["code"], R["name"], "ASSETQR", request.session, request
            )

        # return questionset_form empty
        if R.get("action", None) == "form":
            cxt = {
                "assetform": P["form"](request=request),
                "assetextrasform": P["jsonform"](request=request),
                "ta_form": obf.TypeAssistForm(auto_id=False, request=request),
                "msg": "create asset requested",
            }
            resp = render(request, P["template_form"], cxt)

        if R.get("action", None) == "delete" and R.get("id", None):
            return utils.render_form_for_delete(request, P, True)

        if R.get("fetchStatus") not in ["", None]:
            period = Asset.objects.get_period_of_assetstatus(R["id"], R["fetchStatus"])
            return rp.JsonResponse({"period": period}, status=200)

        # return form with instance
        elif R.get("id", None):
            asset = utils.get_model_obj(R["id"], request, P)
            cxt = {
                "assetform": P["form"](instance=asset, request=request),
                "assetextrasform": get_asset_jsonform(asset, request),
                "ta_form": obf.TypeAssistForm(auto_id=False, request=request),
                "msg": "Asset Update Requested",
            }
            resp = render(request, P["template_form"], context=cxt)
        return resp

    def post(self, request, *args, **kwargs):
        """Handle POST requests for asset creation/update."""
        resp, create = None, True
        from apps.core.utils_new.http_utils import get_clean_form_data
        data = get_clean_form_data(request)
        try:
            if pk := request.POST.get("pk", None):
                msg, create = "asset_view", False
                people = utils.get_model_obj(pk, request, self.P)
                form = self.P["form"](data, request=request, instance=people)
            else:
                form = self.P["form"](data, request=request)
            jsonform = self.P["jsonform"](data, request=request)
            if form.is_valid() and jsonform.is_valid():
                resp = self.handle_valid_form(form, jsonform, request, create)
            else:
                cxt = {"errors": form.errors}
                if jsonform.errors:
                    cxt.update({"errors": jsonform.errors})
                resp = utils.handle_invalid_form(request, self.P, cxt)
        except ValidationError as e:
            logger.warning(f"AssetView form validation error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Asset form validation failed")
            resp = rp.JsonResponse({"error": "Invalid form data", "details": str(e)}, status=400)
        except ActivityManagementException as e:
            logger.error(f"AssetView activity management error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Asset activity management error")
            resp = rp.JsonResponse({"error": "Activity management error", "correlation_id": error_data.get("correlation_id")}, status=422)
        except PermissionDenied as e:
            logger.warning(f"AssetView permission denied: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Asset access denied")
            resp = rp.JsonResponse({"error": "Access denied", "correlation_id": error_data.get("correlation_id")}, status=403)
        except (ValueError, TypeError) as e:
            logger.warning(f"AssetView data processing error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Asset data processing error")
            resp = rp.JsonResponse({"error": "Invalid data format", "correlation_id": error_data.get("correlation_id")}, status=400)
        except SystemException as e:
            logger.error(f"AssetView system error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, "Asset system error")
            resp = rp.JsonResponse({"error": "System error occurred", "correlation_id": error_data.get("correlation_id")}, status=500)
        return resp

    @staticmethod
    def handle_valid_form(form, jsonform, request, create):
        """Handle valid form submission for asset creation/update."""
        from apps.core.utils import handle_intergrity_error
        try:
            asset = form.save(commit=False)
            asset.gpslocation = form.cleaned_data["gpslocation"]
            asset.save()
            if av_utils.save_assetjsonform(jsonform, asset):
                asset = putils.save_userinfo(
                    asset, request.user, request.session, create=create
                )

                # AI Integration: Trigger quality assessment for asset
                AssetView._trigger_quality_assessment(asset, is_new=create)

            data = {"pk": asset.id}
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return handle_intergrity_error("Asset")

    @staticmethod
    def _trigger_quality_assessment(asset, is_new=False):
        """Trigger quality assessment for asset asynchronously"""
        try:
            from apps.quality_assurance.tasks import assess_entity_quality

            # Trigger asynchronous quality assessment
            assess_entity_quality.delay(
                entity_type='ASSET',
                entity_id=asset.id,
                force_reassessment=not is_new
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            # Log error but don't fail asset creation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to trigger quality assessment for asset {asset.id}: {e}")


@method_decorator(csrf_protect, name='post')
class AssetDeleteView(LoginRequiredMixin, View):
    """View for asset deletion."""

    def post(self, request, pk):
        """Delete an asset."""
        try:
            asset = Asset.objects.optimized_get_with_relations(pk)
            asset_code = asset.assetcode
            asset.delete()

            logger.info(f"Asset deleted successfully: {asset_code}")
            return rp.JsonResponse({
                "success": ResponseConstants.Success.DELETED
            }, status=200)

        except Asset.DoesNotExist:
            logger.error(f"Asset with id {pk} not found for deletion")
            return rp.JsonResponse(
                {"errors": ResponseConstants.Error.NOT_FOUND},
                status=404
            )
        except IntegrityError as e:
            logger.error(f"Cannot delete asset due to dependencies: {e}")
            return rp.JsonResponse(
                {"errors": "Cannot delete asset - it is referenced by other records"},
                status=422
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.critical(f"Unexpected error deleting asset: {e}", exc_info=True)
            return rp.JsonResponse(
                {"errors": ResponseConstants.Error.OPERATION_FAILED},
                status=500
            )