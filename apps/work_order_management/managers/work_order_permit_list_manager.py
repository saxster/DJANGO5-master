from django.db.models import Q
from apps.tenants.managers import TenantAwareManager
from apps.core.json_utils import safe_json_parse_params
from datetime import datetime
import logging

logger = logging.getLogger("django")


class WorkOrderPermitListManager(TenantAwareManager):
    """
    Custom manager for Work Permit list queries and counts.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_workpermitlist(self, request):
        """Optimized work permit list retrieval"""
        from apps.work_order_management.models import Approver

        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        people_id = S["people_id"]

        # Single query for approver check using exists()
        is_approver = Approver.objects.filter(
            people_id=people_id,
            approverfor__contains=["WORKPERMIT"],
            identifier="APPROVER",
        ).exists()

        # Base queryset with common filters
        base_filters = {
            "parent_id": 1,
            "client_id": S["client_id"],
            "bu_id": S["bu_id"],
            "cdtz__date__gte": P["from"],
            "cdtz__date__lte": P["to"],
        }

        # Build queryset with optimized exclude patterns
        qobjs = (
            self.exclude(workpermit__in=["NOT_REQUIRED", "NOTREQUIRED"])
            .exclude(identifier="SLA")
            .filter(**base_filters)
        )

        # Add approver-specific filter
        if is_approver:
            qobjs = qobjs.filter(verifiers_status="APPROVED")

        # Optimize with select_related and values
        qobjs = qobjs.select_related("cuser", "bu", "qset", "vendor").order_by(
            "-other_data__wp_seqno"
        )

        return (
            list(
                qobjs.values(
                    "cdtz",
                    "other_data__wp_seqno",
                    "qset__qsetname",
                    "workpermit",
                    "ctzoffset",
                    "workstatus",
                    "id",
                    "cuser__peoplename",
                    "bu__buname",
                    "bu__bucode",
                    "identifier",
                    "verifiers_status",
                    "vendor__name",
                    "remarks",
                )
            )
            or []
        )

    def get_slalist(self, request):
        """Optimized SLA list retrieval"""
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)

        # Optimized query with proper field selection
        qobjs = (
            self.filter(
                identifier="SLA",
                client_id=S["client_id"],
                bu_id=S["bu_id"],
                cdtz__date__gte=P["from"],
                cdtz__date__lte=P["to"],
            )
            .select_related("cuser", "bu", "qset", "vendor")
            .order_by("-other_data__wp_seqno")
        )

        # Use values to reduce data transfer
        return (
            list(
                qobjs.values(
                    "cdtz",
                    "other_data__wp_seqno",
                    "qset__qsetname",
                    "workpermit",
                    "ctzoffset",
                    "workstatus",
                    "id",
                    "cuser__peoplename",
                    "bu__buname",
                    "bu__bucode",
                    "vendor__name",
                    "other_data__overall_score",
                    "other_data__uptime_score",
                    "other_data__remarks",
                )
            )
            or []
        )

    def get_workpermit_count(self, request):
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        qobjs = (
            self.select_related("cuser", "bu", "qset", "vendor")
            .filter(
                ~Q(workpermit__in=["NOT_REQUIRED", "NOTREQUIRED"]),
                ~Q(identifier="SLA"),
                parent_id=1,
                client_id=S["client_id"],
                bu_id=S["bu_id"],
                cdtz__date__gte=pd1,
                cdtz__date__lte=pd2,
            )
            .count()
        )
        return qobjs
