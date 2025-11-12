"""
List view manager for PeopleEventlog.

Handles attendance list views and conveyance tracking.
"""
from django.db import models
from django.contrib.gis.db.models.functions import AsGeoJSON
from apps.core.json_utils import safe_json_parse_params
import logging

logger = logging.getLogger("django")


class ListViewManagerMixin:
    """
    Manager mixin for list view queries.

    Provides methods for:
    - Attendance list views
    - Conveyance tracking
    - Journey coordinate retrieval
    """

    def get_peopleevents_listview(self, related, fields, request):
        """Get paginated attendance list view"""
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        qset = (
            self.select_related(*related)
            .annotate(sL=AsGeoJSON("startlocation"), eL=AsGeoJSON("endlocation"))
            .filter(
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                datefor__gte=P["from"],
                datefor__lte=P["to"],
                peventtype__tacode__in=[
                    "SELF",
                    "SELFATTENDANCE",
                    "MARK",
                    "MRKATTENDANCE",
                ],
            )
            .exclude(id=1)
            .values(*fields)
            .order_by("-datefor")
        )
        return qset or self.none()

    def get_lastmonth_conveyance(self, request, fields, related):
        """Get last month's conveyance records"""
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)

        # Combine all related fields to avoid redundant select_related calls
        all_related = set(["bu", "people"] + list(related))

        qset = (
            self.select_related(*all_related)
            .annotate(start=AsGeoJSON("startlocation"), end=AsGeoJSON("endlocation"))
            .filter(
                peventtype__tacode="CONVEYANCE",
                punchintime__date__gte=P["from"],
                punchintime__date__lte=P["to"],
                client_id=S["client_id"],
            )
            .exclude(endlocation__isnull=True)
            .values(*fields)
            .order_by("-punchintime")
        )
        return qset or self.none()

    def getjourneycoords(self, id):
        """Get journey path coordinates for a specific record"""
        import json
        from apps.core import utils

        qset = (
            self.annotate(path=AsGeoJSON("journeypath"))
            .filter(id=id)
            .values(
                "path",
                "punchintime",
                "punchouttime",
                "deviceid",
                "expamt",
                "accuracy",
                "people__peoplename",
                "people__peoplecode",
                "distance",
                "duration",
                "transportmodes",
            )
        )
        for obj in qset:
            if obj["path"]:
                geodict = json.loads(obj["path"])
                coords = [
                    {"lat": lat, "lng": lng} for lng, lat in geodict["coordinates"]
                ]
                waypoints = utils.orderedRandom(coords[1:-1], k=25)
                obj["path"] = coords
                obj["waypoints"] = waypoints
                coords, waypoints = [], []
            else:
                return self.none()
        return qset or self.none()
