from django.db import models
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from django.db.models import (
    Q,
    When,
    Case,
    F,
    CharField,
    Count,
    IntegerField,
    Value as V,
)
from django.db.models.functions import Cast
from apps.onboarding.models import TypeAssist
from apps.peoples.models import Pgbelonging
from apps.tenants.managers import TenantAwareManager
import logging

log = logging.getLogger("django")

# Import centralized JSON utility
from apps.core.json_utils import safe_json_parse_params

# Import optimized query methods
from .managers.optimized_managers import OptimizedTicketManagerMixin


class TicketManager(OptimizedTicketManagerMixin, TenantAwareManager):
    """
    Enhanced TicketManager with performance optimizations and tenant awareness.

    Combines original functionality with optimized query methods
    that eliminate N+1 queries and provide significant performance improvements.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    - Inherited from TenantAwareManager (apps/tenants/managers.py)
    """
    use_in_migrations = True

    def send_ticket_mail(self, ticketid):
        from apps.core.queries import QueryRepository
        
        # Use new Django ORM implementation
        ticketmail = QueryRepository.ticketmail(ticketid)
        return ticketmail or self.none()

    def get_tickets_listview(self, request):
        """Optimized ticket list retrieval"""
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)

        # Base query with indexed fields first for better performance
        qset = self.filter(
            cdtz__date__gte=P["from"],
            cdtz__date__lte=P["to"],
            bu_id__in=S["assignedsites"],
            client_id=S["client_id"],
        ).select_related(
            "assignedtopeople", "assignedtogroup", "bu", "ticketcategory", "cuser"
        )

        # Handle status filtering more efficiently
        status = P.get("status")
        if status == "SYSTEMGENERATED":
            qset = qset.filter(ticketsource="SYSTEMGENERATED")
        elif status:
            qset = qset.filter(status=status, ticketsource="USERDEFINED")

        # Return optimized values
        return (
            list(
                qset.values(
                    "id",
                    "ticketno",
                    "cdtz",
                    "bu__buname",
                    "status",
                    "bu__bucode",
                    "isescalated",
                    "cuser__peoplename",
                    "cuser__peoplecode",
                    "ticketdesc",
                    "ctzoffset",
                    "ticketsource",
                    "ticketcategory__taname",
                )
            )
            or []
        )

    def get_tickets_for_mob(self, peopleid, buid, clientid, mdtz, ctzoffset):

        if not isinstance(mdtz, datetime):
            mdtz = datetime.strptime(mdtz, "%Y-%m-%d %H:%M:%S") - timedelta(
                minutes=ctzoffset
            )

        group_ids = list(
            Pgbelonging.objects.filter(~Q(pgroup_id=1), people_id=peopleid).values_list(
                "pgroup_id", flat=True
            )
        )
        qset = (
            self.select_related(
                "assignedtopeople",
                "assignedtogroup",
                "bu",
                "client",
                "ticketcategory",
                "location",
                "performedby",
            )
            .filter(
                (
                    Q(assignedtopeople_id=peopleid)
                    | Q(cuser_id=peopleid)
                    | Q(muser_id=peopleid)
                    | Q(assignedtogroup_id__in=group_ids)
                ),
                mdtz__gte=mdtz,
                bu_id=buid,
                client_id=clientid,
            )
            .values(
                "id",
                "ticketno",
                "uuid",
                "ticketdesc",
                "assignedtopeople_id",
                "assignedtogroup_id",
                "comments",
                "bu_id",
                "client_id",
                "priority",
                "events",
                "isescalated",
                "ticketsource",
                "cuser_id",
                "muser_id",
                "cdtz",
                "mdtz",
                "ctzoffset",
                "attachmentcount",
                "ticketcategory_id",
                "location_id",
                "asset_id",
                "modifieddatetime",
                "level",
                "status",
                "identifier",
                "qset_id",
            )
        )
        return qset or self.none()

    def get_ticketlist_for_escalation(self):
        from apps.core.queries import QueryRepository

        return QueryRepository.get_ticketlist_for_escalation() or self.none()

    def get_ticket_stats_for_dashboard(self, request):
        # sourcery skip: avoid-builtin-shadow
        S, R = request.session, request.GET
        qset = self.filter(
            bu_id__in=S["assignedsites"],
            cdtz__date__gte=R["from"],
            cdtz__date__lte=R["upto"],
            client_id=S["client_id"],
        )
        user_generated = qset.filter(ticketsource="USERDEFINED")
        sys_generated = qset.filter(ticketsource="SYSTEMGENERATED")
        aggregate_user_generated_data = user_generated.aggregate(
            new=Count(Case(When(status="NEW", then=1), output_field=IntegerField())),
            open=Count(Case(When(status="OPEN", then=1), output_field=IntegerField())),
            cancelled=Count(
                Case(When(status="CANCELLED", then=1), output_field=IntegerField())
            ),
            resolved=Count(
                Case(When(status="RESOLVED", then=1), output_field=IntegerField())
            ),
            closed=Count(
                Case(When(status="CLOSED", then=1), output_field=IntegerField())
            ),
            onhold=Count(
                Case(When(status="ONHOLD", then=1), output_field=IntegerField())
            ),
        )
        autoclosed = sys_generated.count()
        stats = [
            aggregate_user_generated_data["new"],
            aggregate_user_generated_data["resolved"],
            aggregate_user_generated_data["open"],
            aggregate_user_generated_data["cancelled"],
            aggregate_user_generated_data["closed"],
            aggregate_user_generated_data["onhold"],
            autoclosed,
        ]
        return stats, sum(stats)

    def get_events_for_calendar(self, request):
        S, R = request.session, request.GET
        start_date = datetime.strptime(R["start"], "%Y-%m-%dT%H:%M:%S%z").date()
        end_date = datetime.strptime(R["end"], "%Y-%m-%dT%H:%M:%S%z").date()

        qset = (
            self.annotate(
                start=Cast(F("cdtz"), output_field=CharField()),
                end=Cast(F("modifieddatetime"), output_field=CharField()),
                title=F("ticketdesc"),
                color=Case(
                    When(status__exact=self.model.Status.CANCEL, then=V("#727272")),
                    When(status__exact=self.model.Status.ONHOLD, then=V("#b87707")),
                    When(status__exact=self.model.Status.CLOSED, then=V("#13780e")),
                    When(status__exact=self.model.Status.RESOLVED, then=V("#0d96ab")),
                    When(status__exact=self.model.Status.NEW, then=V("#a14020")),
                    When(status__exact=self.model.Status.OPEN, then=V("#004679")),
                    output_field=CharField(),
                ),
            )
            .select_related()
            .filter(
                cdtz__date__gte=start_date,
                cdtz__date__lte=end_date,
                bu_id=S["bu_id"],
                client_id=S["client_id"],
            )
        )
        qset = qset.values("id", "start", "end", "title", "color")
        return qset or self.none()


class ESCManager(TenantAwareManager):
    """
    Custom manager for EscalationMatrix model with tenant-aware filtering.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_reminder_config_forppm(self, job_id, fields):
        qset = self.filter(escalationtemplate__tacode="JOB", job_id=job_id).values(
            *fields
        )
        return qset or self.none()

    def handle_reminder_config_postdata(self, request):
        try:
            P, S = request.POST, request.session
            cdtz = timezone.now()
            mdtz = timezone.now()
            ppmjob = TypeAssist.objects.get(
                tatype__tacode="ESCALATIONTEMPLATE", tacode="JOB"
            )
            PostData = {
                "cdtz": cdtz,
                "mdtz": mdtz,
                "cuser": request.user,
                "muser": request.user,
                "level": 1,
                "job_id": P["jobid"],
                "frequency": P["frequency"],
                "frequencyvalue": P["frequencyvalue"],
                "notify": P["notify"],
                "assignedperson_id": P["peopleid"],
                "assignedgroup_id": P["groupid"],
                "bu_id": S["bu_id"],
                "escalationtemplate": ppmjob,
                "client_id": S["client_id"],
                "ctzoffset": P["ctzoffset"],
            }
            if P["action"] == "create":
                if self.filter(
                    job_id=P["jobid"],
                    frequency=PostData["frequency"],
                    frequencyvalue=PostData["frequencyvalue"],
                ).exists():
                    return {
                        "data": list(self.none()),
                        "error": "Warning: Record already added!",
                    }
                ID = self.create(**PostData).id

            elif P["action"] == "edit":
                PostData.pop("cdtz")
                PostData.pop("cuser")
                if updated := self.filter(pk=P["pk"]).update(**PostData):
                    ID = P["pk"]
            else:
                self.filter(pk=P["pk"]).delete()
                return {
                    "data": list(self.none()),
                }
            qset = self.filter(pk=ID).values(
                "notify", "frequency", "frequencyvalue", "id"
            )
            return {"data": list(qset)}
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            log.critical("Unexpected error", exc_info=True)
            if "frequencyvalue_gte_0_ck" in str(e):
                return {
                    "data": [],
                    "error": "Invalid Reminder Before. It must be greater than or equal to 0.",
                }
            if "valid_notify_format" in str(e):
                return {
                    "data": [],
                    "error": "Invalid Email ID format. Please enter a valid email address.",
                }
            return {"data": [], "error": "Something went wrong!"}

    def get_escalation_listview(self, request):
        """Optimized escalation list retrieval with caching"""
        from django.core.cache import cache
        from apps.onboarding.models import TypeAssist

        R, S = request.GET, request.session

        # Build cache key
        cache_key = (
            f"escalation_list_{S['client_id']}_{str(sorted(S['assignedsites']))}"
        )

        # Check cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Optimized query
        qset = (
            TypeAssist.objects.filter(
                Q(bu_id__in=S["assignedsites"] + [1])
                | Q(cuser_id=1)
                | Q(cuser__is_superuser=True),
                Q(client_id=S["client_id"]) | Q(client_id=1),
                tatype__tacode__in=["TICKETCATEGORY", "TICKET_CATEGORY"],
            )
            .select_related("tatype", "bu")
            .values("taname", "cdtz", "id", "ctzoffset", "bu__buname", "bu__bucode")
        )

        result = list(qset)

        # Cache for 10 minutes (escalation templates don't change often)
        cache.set(cache_key, result, 600)

        return result or []

    def handle_esclevel_form_postdata(self, request):
        try:
            P, S = request.POST, request.session
            cdtz = timezone.now()
            mdtz = timezone.now()
            PostData = {
                "cdtz": cdtz,
                "mdtz": mdtz,
                "cuser": request.user,
                "muser": request.user,
                "level": P["level"],
                "job_id": 1,
                "frequency": P["frequency"],
                "frequencyvalue": P["frequencyvalue"],
                "notify": "",
                "assignedperson_id": P["assignedperson"],
                "assignedgroup_id": P["assignedgroup"],
                "assignedfor": P["assignedfor"],
                "bu_id": S["bu_id"],
                "escalationtemplate_id": P["escalationtemplate_id"],
                "client_id": S["client_id"],
                "ctzoffset": P["ctzoffset"],
            }

            if P["action"] == "create":
                if self.filter(
                    (
                        Q(assignedgroup_id=P["assignedgroup"])
                        & Q(assignedperson_id=P["assignedperson"])
                    ),
                    escalationtemplate_id=P["escalationtemplate_id"],
                ).exists():
                    return {
                        "data": list(self.none()),
                        "error": "Warning: Record with this escalation template and people is already added!",
                    }
                ID = self.create(**PostData).id

            elif P["action"] == "edit":
                PostData.pop("cdtz")
                PostData.pop("cuser")
                if updated := self.filter(pk=P["pk"]).update(**PostData):
                    ID = P["pk"]
            else:
                self.filter(pk=P["pk"]).delete()
                return {
                    "data": list(self.none()),
                }
            qset = self.filter(pk=ID).values(
                "assignedfor",
                "assignedperson__peoplename",
                "assignedperson__peoplecode",
                "assignedgroup__groupname",
                "frequency",
                "frequencyvalue",
                "id",
                "level",
                "assignedperson_id",
                "assignedgroup_id",
            )
            return {"data": list(qset)}
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            log.critical("Unexpected error", exc_info=True)
            if "frequencyvalue_gte_0_ck" in str(e):
                return {
                    "data": [],
                    "error": "Invalid Value. It must be greater than or equal to 0.",
                }
            return {"data": [], "error": "Something went wrong!"}
