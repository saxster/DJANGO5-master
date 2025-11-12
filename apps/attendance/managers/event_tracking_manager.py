"""
Event tracking manager for SOS and site crisis events.

Handles emergency events and special event tracking.
"""
from datetime import datetime
from django.db import models
from django.contrib.gis.db.models.functions import AsGeoJSON
from apps.core.json_utils import safe_json_parse_params
from apps.activity.models.attachment_model import Attachment
import logging

logger = logging.getLogger("django")


class EventTrackingManagerMixin:
    """
    Manager mixin for event tracking operations.

    Provides methods for:
    - SOS event tracking
    - Site crisis monitoring
    - Diversion tracking
    - Attachment merging utilities
    """

    def fetch_sos_events(self, start_date, end_date, session):
        """Fetch SOS events for date range"""
        return (
            self.filter(
                bu_id__in=session["assignedsites"],
                client_id=session["client_id"],
                peventtype__tacode="SOS",
                datefor__gte=start_date,
                datefor__lte=end_date,
            )
            .select_related("peventtype")
            .values(
                "id",
                "ctzoffset",
                "people__peoplename",
                "cdtz",
                "uuid",
                "people__peoplecode",
                "people__mobno",
                "people__email",
                "bu__buname",
            )
        )

    def fetch_attachments(self, uuids):
        """Fetch attachments for list of UUIDs"""
        attachments = Attachment.objects.get_attforuuids(uuids).values(
            "owner", "filepath", "filename"
        )
        return {att["owner"]: att for att in attachments}

    def merge_with_attachments(self, events, attachments):
        """Merge event records with their attachments"""
        for event in events:
            attachment = attachments.get(
                str(event["uuid"]), {"filepath": None, "filename": None}
            )
            yield {**event, **attachment}

    def get_sos_listview(self, request):
        """Get SOS events list with attachments"""
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        from_date, to_date = P["from"], P["to"]
        events = self.fetch_sos_events(from_date, to_date, request.session)
        uuids = [event["uuid"] for event in events]
        attachments = self.fetch_attachments(uuids)
        merged_events = list(self.merge_with_attachments(events, attachments))
        return merged_events or self.none()

    def get_sitecrisis_types(self):
        """Get all site crisis event types"""
        from apps.core_onboarding.models import TypeAssist

        qset = (
            TypeAssist.objects.filter(tatype__tacode="SITECRISIS")
            .select_related("tatype")
            .values_list("tacode", flat=True)
        )
        return qset or []

    def fetch_sitecrisis_events(self, start_date, end_date, session):
        """Fetch site crisis events for date range"""
        return (
            self.filter(
                models.Q(startlocation__isnull=False),
                datefor__gte=start_date,
                datefor__lte=end_date,
                bu_id__in=session["assignedsites"],
                peventtype__tacode__in=self.get_sitecrisis_types(),
            )
            .select_related("peventtype")
            .annotate(gps=AsGeoJSON("startlocation"))
            .values(
                "people__peoplename",
                "people__peoplecode",
                "gps",
                "reference",
                "cdtz",
                "bu__buname",
                "bu__bucode",
                "ctzoffset",
                "people__mobno",
                "people__email",
                "uuid",
                "id",
            )
        )

    def get_sitecrisis_countorlist(self, request, count=False):
        """Get site crisis events or count"""
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        fromdate, upto = P["from"], P["to"]
        events = self.fetch_sitecrisis_events(fromdate, upto, S)
        uuids = [event["uuid"] for event in events]
        attachments = self.fetch_attachments(uuids)
        merged_events = list(self.merge_with_attachments(events, attachments))
        if count:
            return len(merged_events)
        return merged_events or self.none()

    def get_diversion_countorlist(self, request, count=False):
        """Get diversion events list"""
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        fields = [
            "people__peoplename",
            "start_gps",
            "end_gps",
            "reference",
            "datefor",
            "punchintime",
            "punchouttime",
            "ctzoffset",
            "id",
        ]
        qset = (
            self.select_related("people")
            .filter(
                models.Q(startlocation__isnull=False),
                peventtype__tacode="DIVERSION",
                datefor__gte=pd1,
                datefor__lte=pd2,
                bu_id__in=S["assignedsites"],
            )
            .annotate(
                start_gps=AsGeoJSON("startlocation"), end_gps=AsGeoJSON("endlocation")
            )
            .values(*fields)
        )
        data = list(qset) or []
        return data
