"""
Dashboard card manager for PeopleEventlog.

Handles dashboard card counts for various event types.
"""
from datetime import datetime
import logging

logger = logging.getLogger("django")


class DashboardManagerMixin:
    """
    Manager mixin for dashboard card counts.

    Provides methods for:
    - SOS count cards
    - Site crisis count cards
    - Face recognition failure counts
    """

    def get_sos_count_forcard(self, request):
        """Get SOS count for dashboard card"""
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        data = self.filter(
            bu_id__in=S["assignedsites"],
            client_id=S["client_id"],
            peventtype__tacode="SOS",
            datefor__gte=pd1,
            datefor__lte=pd2,
        ).count()
        return data

    def get_sitecrisis_count_forcard(self, request):
        """Get site crisis count for dashboard card"""
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        data = self.fetch_sitecrisis_events(pd1, pd2, S).count()
        return data

    def get_frfail_count_forcard(self, request):
        """Get face recognition failure count for dashboard card"""
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        data = (
            self.filter(
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                datefor__gte=pd1,
                datefor__lte=pd2,
                peventtype__tacode__in=[
                    "SELF",
                    "SELFATTENDANCE",
                    "MARKATTENDANCE",
                    "MARK",
                ],
            )
            .exclude(id=1)
            .count()
        )
        return data
