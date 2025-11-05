"""
Geofence Tracking view for monitoring employee location tracking.
"""

from .base import (
    LoginRequiredMixin,
    IntegrityError,
    DatabaseError,
    transaction,
    rp,
    QueryDict,
    render,
    View,
    ObjectDoesNotExist,
    ValidationError,
    atf,
    atdm,
    am,
    AttendanceFilter,
    putils,
    save_linestring_and_update_pelrecord,
    get_current_db_name,
    AttendanceError,
    AttendanceValidationError,
    AttendanceProcessingError,
    AttendanceDataCorruptionError,
    handle_attendance_exception,
    map_django_exception,
    logging,
    json,
    utils,
    logger,
)


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
