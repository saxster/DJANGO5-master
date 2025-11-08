import logging
from django.http import response as rp
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError

from ..models import Bt
from apps.peoples.models import Pgbelonging

logger = logging.getLogger("django")
log = logger


class GetAllSites(LoginRequiredMixin, View):
    """Get all sites for a client."""
    def get(self, request):
        try:
            qset = Bt.objects.get_all_sites_of_client(request.session["client_id"])
            sites = qset.values("id", "bucode", "buname")
            return rp.JsonResponse(list(sites), status=200)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error("get_allsites() exception: %s", e)
        return rp.JsonResponse({"error": "Invalid Request"}, status=404)


class GetAssignedSites(LoginRequiredMixin, View):
    """Get sites assigned to a specific user."""
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
    """Switch active site in user session."""
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
