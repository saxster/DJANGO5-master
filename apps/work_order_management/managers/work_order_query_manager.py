from django.db.models import Q, F, Count, Case, When, IntegerField, Value as V, CharField
from django.db.models.functions import Cast, Concat
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.conf import settings
from apps.tenants.managers import TenantAwareManager
from apps.core.json_utils import safe_json_parse_params
from datetime import datetime
import logging

logger = logging.getLogger("django")


class WorkOrderQueryManager(TenantAwareManager):
    """
    Custom manager for Work Order list queries, filtering, and calendar operations.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_workorder_list(self, request, fields, related):
        """Optimized work order list retrieval"""
        from apps.work_order_management.models import Wom

        S = request.session
        P = safe_json_parse_params(request.GET)

        # Start with indexed field filters for better performance
        qset = self.filter(
            client_id=S["client_id"],
            workpermit=Wom.WorkPermitStatus.NOTNEED,
            cdtz__date__gte=P["from"],
            cdtz__date__lte=P["to"],
        )

        # Add status filter if provided
        if P.get("status"):
            qset = qset.filter(workstatus=P["status"])

        # Only use select_related for needed relations
        if related:
            qset = qset.select_related(*related)

        # Use values() to reduce data transfer
        return list(qset.values(*fields)) or []

    def get_wom_status_chart(self, request):
        S, R = request.session, request.GET
        qset = self.filter(
            bu_id__in=S["assignedsites"],
            client_id=S["client_id"],
            cdtz__date__gte=R["from"],
            cdtz__date__lte=R["upto"],
            workpermit="NOT_REQUIRED",
        )

        aggregate_data = qset.aggregate(
            assigned=Count(
                Case(When(workstatus="ASSIGNED", then=1), output_field=IntegerField())
            ),
            re_assigned=Count(
                Case(
                    When(workstatus="RE_ASSIGNED", then=1), output_field=IntegerField()
                )
            ),
            completed=Count(
                Case(When(workstatus="COMPLETED", then=1), output_field=IntegerField())
            ),
            inprogress=Count(
                Case(When(workstatus="INPROGRESS", then=1), output_field=IntegerField())
            ),
            closed=Count(
                Case(When(workstatus="CLOSED", then=1), output_field=IntegerField())
            ),
            cancelled=Count(
                Case(When(workstatus="CANCELLED", then=1), output_field=IntegerField())
            ),
        )

        stats = [
            aggregate_data["assigned"],
            aggregate_data["re_assigned"],
            aggregate_data["completed"],
            aggregate_data["cancelled"],
            aggregate_data["inprogress"],
            aggregate_data["closed"],
        ]

        data = stats, sum(stats)
        return data

    def get_events_for_calendar(self, request):
        from apps.work_order_management.models import Wom

        S, R = request.session, request.GET

        start_date = datetime.strptime(R["start"], "%Y-%m-%dT%H:%M:%S%z").date()
        end_date = datetime.strptime(R["end"], "%Y-%m-%dT%H:%M:%S%z").date()

        qset = self.annotate(
            start=Cast(F("plandatetime"), output_field=CharField()),
            end=Cast(F("expirydatetime"), output_field=CharField()),
            title=Case(
                When(workpermit="NOT_REQUIRED", then=F("description")),
                default=F("qset__qsetname"),
                output_field=CharField(),
            ),
            color=Case(
                When(workstatus__exact=Wom.Workstatus.CANCELLED, then=V("#727272")),
                When(workstatus__exact=Wom.Workstatus.REASSIGNED, then=V("#004679")),
                When(workstatus__exact=Wom.Workstatus.INPROGRESS, then=V("#b87707")),
                When(workstatus__exact=Wom.Workstatus.CLOSED, then=V("#13780e")),
                When(workstatus__exact=Wom.Workstatus.COMPLETED, then=V("#0d96ab")),
                When(workstatus__exact=Wom.Workstatus.ASSIGNED, then=V("#a14020")),
                output_field=CharField(),
            ),
        ).filter(
            cdtz__date__gte=start_date,
            cdtz__date__lte=end_date,
            bu_id=S["bu_id"],
            client_id=S["client_id"],
        )

        if R["eventType"] == "Work Orders":
            qset = qset.filter(workpermit=Wom.WorkPermitStatus.NOTNEED)
        else:
            qset = qset.filter(~Q(workpermit=Wom.WorkPermitStatus.NOTNEED))
        qset = qset.values("id", "start", "end", "title", "color")
        return qset or self.none()

    def get_attachments(self, id):
        if qset := self.filter(id=id).values("uuid"):
            if atts := self.get_atts(qset[0]["uuid"]):
                return atts or self.none()
        return self.none()

    def get_atts(self, uuid):
        from apps.activity.models.attachment_model import Attachment
        from django.db import models

        if (
            atts := Attachment.objects.annotate(
                file=Concat(
                    V(settings.MEDIA_URL, output_field=models.CharField()),
                    F("filepath"),
                    V("/"),
                    Cast("filename", output_field=models.CharField()),
                ),
                location=AsGeoJSON("gpslocation"),
            )
            .filter(owner=uuid)
            .values(
                "filepath",
                "filename",
                "attachmenttype",
                "datetime",
                "location",
                "id",
                "file",
            )
        ):
            return atts
        return self.none()
