import logging
from django.http import response as rp
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from ..models import Subscription

logger = logging.getLogger("django")


class LicenseSubscriptionView(LoginRequiredMixin, View):
    """License subscription management (restored from initial commit)."""
    P = {"model": Subscription}

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.P
        if R.get("action") == "getLicenseList":
            try:
                qset = P["model"].objects.get_license_list(R["client_id"])
                return rp.JsonResponse({"data": list(qset)}, status=200)
            except (AttributeError, TypeError, ValueError, KeyError) as e:
                logger.error(f"LicenseSubscriptionView error: {e}")
                return rp.JsonResponse({"error": "Invalid request"}, status=400)
        return rp.JsonResponse({"error": "Action parameter required"}, status=400)
