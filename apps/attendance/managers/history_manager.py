"""
History and sync manager for PeopleEventlog.

Handles attendance history queries and punch-in tracking.
"""
from datetime import timedelta
import logging

logger = logging.getLogger("django")


class HistoryManagerMixin:
    """
    Manager mixin for history and sync queries.

    Provides methods for:
    - Attendance history
    - Pending punch-ins
    """

    def get_peopleeventlog_history(
        self, mdtz, people_id, bu_id, client_id, ctzoffset, peventtypeid
    ):
        """Get attendance history for a person"""
        qset = (
            self.filter(
                mdtz__gte=mdtz,
                people_id=people_id,
                bu_id=bu_id,
                client_id=client_id,
                peventtype_id__in=peventtypeid,
            )
            .select_related(
                "people",
                "bu",
                "client",
                "verifiedby",
                "peventtype",
                "geofence",
                "shift",
            )
            .order_by("-datefor")
            .values(
                "uuid",
                "people_id",
                "client_id",
                "bu_id",
                "shift_id",
                "verifiedby_id",
                "geofence_id",
                "id",
                "peventtype_id",
                "punchintime",
                "punchouttime",
                "datefor",
                "distance",
                "duration",
                "expamt",
                "accuracy",
                "deviceid",
                "startlocation",
                "endlocation",
                "ctzoffset",
                "remarks",
                "facerecognitionin",
                "facerecognitionout",
                "otherlocation",
                "reference",
                "mdtz",
            )
        )
        return qset or self.none()

    def get_people_event_log_punch_ins(self, datefor, buid, peopleid):
        """Get pending punch-ins (no punch-out yet)"""
        type = (
            ["MARK", "MARKATTENDANCE"] if peopleid == -1 else ["SELF", "SELFATTENDANCE"]
        )
        given_date = datefor
        previous_date = given_date - timedelta(days=1)
        qset = (
            self.filter(
                datefor__range=(previous_date, given_date),
                punchouttime__isnull=True,
                bu_id=buid,
                peventtype__tacode__in=type,
            )
            .select_related(
                "client", "bu", "shift", "verifiedby", "geofence", "peventtype"
            )
            .values(
                "uuid",
                "people_id",
                "client_id",
                "bu_id",
                "shift_id",
                "verifiedby_id",
                "geofence_id",
                "id",
                "peventtype_id",
                "transportmodes",
                "punchintime",
                "punchouttime",
                "datefor",
                "distance",
                "cuser_id",
                "muser_id",
                "cdtz",
                "mdtz",
                "ctzoffset",
                "duration",
                "expamt",
                "accuracy",
                "deviceid",
                "startlocation",
                "endlocation",
                "remarks",
                "facerecognitionin",
                "facerecognitionout",
                "otherlocation",
                "reference",
                "tenant_id",
            )
            .order_by("punchintime")
        )
        if qset:
            for entry in qset:
                entry["transportmodes"] = "NONE"
        return qset or []
