"""
Geofence Tracking view for monitoring employee location tracking.
"""

from .base import *


class GeofenceTracking(LoginRequiredMixin, View):
    """
    Geofence tracking view for monitoring employee locations within defined geographic boundaries.
    """

    params = {
        "template_list": "attendance/geofencetracking.html",
        "model": atdm.PeopleEventlog,
        "related": ["geofence", "peventtype", "people"],
        "fields": [
            "datefor",
            "geofence__gfname",
            "startlocation",
            "endlocation",
            "people__peoplename",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        # first load the template
        if R.get("template"):
            return render(request, self.params["template_list"])

        # then load the table with objects for table_view
        if R.get("action", None) == "list" or R.get("search_term"):
            total, filtered, objs = self.params["model"].objects.get_geofencetracking(
                request
            )
            return rp.JsonResponse(
                data={
                    "draw": R["draw"],
                    "data": list(objs),
                    "recordsFiltered": filtered,
                    "recordsTotal": total,
                },
                safe=False,
            )


__all__ = ['GeofenceTracking']
