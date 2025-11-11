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
    """
    Switch active site in user session.

    Security: Validates that the user is assigned to the requested site
    before allowing the switch, preventing IDOR/horizontal privilege escalation.
    """

    def _validate_site_id(self, req_buid, user_id):
        """Validate and convert site ID to integer."""
        try:
            return int(req_buid)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid site ID format in switch request: user_id=%s, buid=%s",
                user_id, req_buid
            )
            return None

    def _validate_user_authorization(self, user_id, site_id):
        """Validate user has access to requested site."""
        assigned_sites = Pgbelonging.objects.get_assigned_sites_to_people(user_id)

        if not assigned_sites:
            logger.warning(
                "Site switch attempted by user with no assigned sites: user_id=%s", user_id
            )
            return False, "No sites assigned to user"

        if site_id not in assigned_sites:
            logger.warning(
                "Unauthorized site switch attempt: user_id=%s, requested_site=%s",
                user_id, site_id
            )
            return False, "Unauthorized site access"

        return True, None

    def _get_site_details(self, site_id):
        """Lookup site details from database."""
        return Bt.objects.filter(id=site_id).values("id", "bucode", "buname", "enable")[:1]

    def _update_session(self, request, site):
        """Update session with new site information."""
        request.session["bu_id"] = site["id"]
        request.session["sitecode"] = site["bucode"]
        request.session["sitename"] = site["buname"]
        log.info("Successfully switched to site: user_id=%s, site_id=%s", request.user.id, site["id"])

    def _process_site_switch(self, request, site_id):
        """Process site switch after authorization checks."""
        sites = self._get_site_details(site_id)

        if not sites:
            log.info("Site not found: site_id=%s", site_id)
            return {"rc": 1, "errMsg": "unable to find site."}

        if not sites[0]["enable"]:
            log.info("Inactive Site requested: site_id=%s", site_id)
            return {"rc": 1, "errMsg": "Inactive Site"}

        self._update_session(request, sites[0])
        return {"rc": 0, "message": "successfully switched to site."}

    def post(self, request):
        req_buid = request.POST["buid"]

        if req_buid == " ":
            log.info("Empty site ID provided")
            return rp.JsonResponse({"rc": 1, "errMsg": "unable to find site."}, status=200)

        try:
            req_buid_int = self._validate_site_id(req_buid, request.user.id)
            if req_buid_int is None:
                return rp.JsonResponse({"rc": 1, "errMsg": "Invalid site ID format"}, status=400)

            authorized, error_msg = self._validate_user_authorization(request.user.id, req_buid_int)
            if not authorized:
                return rp.JsonResponse({"rc": 1, "errMsg": error_msg}, status=403)

            resp = self._process_site_switch(request, req_buid_int)
            return rp.JsonResponse(resp, status=200)

        except (DatabaseError, IntegrityError) as e:
            logger.error("Error in site switch: user_id=%s, error=%s", request.user.id, e)
            return rp.JsonResponse({"rc": 1, "errMsg": "Error processing site switch"}, status=500)
