"""
Work Order Management Services
Optimized query patterns and caching strategies for work order operations
"""

from django.core.cache import cache
from django.db.models import Q

class WorkOrderQueryOptimizer:
    """Centralized query optimization for work order operations"""

    CACHE_TTL = 300  # 5 minutes cache

    @staticmethod
    def get_vendor_list_optimized(request, model_class):
        """
        Optimized vendor list retrieval with caching

        Key optimizations:
        1. Removed redundant select_related if no relations are needed
        2. Added caching for vendor lists (typically static data)
        3. Using only() to limit fields if full model not needed
        """
        from apps.core.json_utils import safe_json_parse_params

        R, S = request.GET, request.session
        cache_key = f"vendor_list_{S['client_id']}"

        # Try cache first for vendor lists (relatively static data)
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        if R.get("params"):
            P = safe_json_parse_params(R)

        # Use only() to limit fields loaded from database
        qset = (
            model_class.objects.filter(client_id=S["client_id"], enable=True)
            .only("id", "code", "name", "type", "address", "email", "mobno")
            .order_by("name")
        )

        # Convert to list for caching
        result = list(
            qset.values("id", "code", "name", "type", "address", "email", "mobno")
        )

        # Cache the result
        cache.set(cache_key, result, WorkOrderQueryOptimizer.CACHE_TTL)

        return result

    @staticmethod
    def get_workorder_list_optimized(request, model_class):
        """
        Optimized work order list retrieval

        Key optimizations:
        1. Use select_related only for needed relations
        2. Filter by indexed fields first
        3. Use prefetch_related for many-to-many if needed
        """
        from apps.core.json_utils import safe_json_parse_params
        from .models import Wom

        S = request.session
        P = safe_json_parse_params(request.GET)

        # Start with indexed field filters
        qset = model_class.objects.filter(
            client_id=S["client_id"],
            workpermit=Wom.WorkPermitStatus.NOTNEED,
            cdtz__date__gte=P["from"],
            cdtz__date__lte=P["to"],
        )

        # Add status filter if provided
        if P.get("status"):
            qset = qset.filter(workstatus=P["status"])

        # Select only needed related objects
        qset = qset.select_related("cuser", "bu", "qset", "vendor")

        # Use values() to reduce data transfer
        return list(
            qset.values(
                "id",
                "description",
                "workstatus",
                "priority",
                "cdtz",
                "mdtz",
                "cuser__peoplename",
                "bu__buname",
                "bu__bucode",
                "qset__qsetname",
                "vendor__name",
                "other_data",
                "remarks",
            )
        )

    @staticmethod
    def get_workpermitlist_optimized(request, model_class):
        """
        Optimized work permit list retrieval

        Key optimizations:
        1. Combine role check with main query
        2. Use exists() for permission checks
        3. Reduce redundant queries
        """
        from apps.work_order_management.models import Approver
        from apps.core.json_utils import safe_json_parse_params

        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        people_id = S["people_id"]

        # Single query for approver check
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

        # Exclude work permits not required
        qset = (
            model_class.objects.exclude(workpermit__in=["NOT_REQUIRED", "NOTREQUIRED"])
            .exclude(identifier="SLA")
            .filter(**base_filters)
        )

        # Add approver-specific filter
        if is_approver:
            qset = qset.filter(verifiers_status="APPROVED")

        # Optimize with select_related and values
        qset = qset.select_related("cuser", "bu", "qset", "vendor").order_by(
            "-other_data__wp_seqno"
        )

        return list(
            qset.values(
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

    @staticmethod
    def get_approver_list_optimized(request, model_class):
        """
        Optimized approver list retrieval

        Key optimizations:
        1. Simplify complex Q queries
        2. Use prefetch_related for people relation
        3. Cache approver lists
        """
        R, S = request.GET, request.session

        # Build cache key
        cache_key = f"approver_list_{S['bu_id']}_{S['client_id']}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Simplified query logic
        assignedsites = S.get("assignedsites", [])

        # Build filters step by step for clarity
        site_filter = Q(bu_id=S["bu_id"])
        if assignedsites:
            site_filter |= Q(bu_id__in=assignedsites)

        # Add client-wide filter
        client_filter = Q(forallsites=True, client_id=S["client_id"])

        # Combined query
        qset = (
            model_class.objects.filter(site_filter | client_filter)
            .select_related("people")
            .values(
                "id",
                "approverfor",
                "sites",
                "forallsites",
                "people__peoplename",
                "people__peoplecode",
                "identifier",
                "bu_id",
            )
        )

        result = list(qset)

        # Cache the result
        cache.set(cache_key, result, WorkOrderQueryOptimizer.CACHE_TTL)

        return result

    @staticmethod
    def get_slalist_optimized(request, model_class):
        """
        Optimized SLA list retrieval

        Key optimizations:
        1. Use indexed fields for filtering
        2. Select only required fields
        3. Avoid N+1 queries with select_related
        """
        from apps.core.json_utils import safe_json_parse_params

        R, S = request.GET, request.session
        P = safe_json_parse_params(R)

        # Optimized query with proper field selection
        qset = (
            model_class.objects.filter(
                identifier="SLA",
                client_id=S["client_id"],
                bu_id=S["bu_id"],
                cdtz__date__gte=P["from"],
                cdtz__date__lte=P["to"],
            )
            .select_related("cuser", "bu", "qset", "vendor")
            .order_by("-other_data__wp_seqno")
        )

        # Use annotate for JSON field access if needed
        return list(
            qset.values(
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


class HelpdeskQueryOptimizer:
    """Optimized query patterns for helpdesk operations"""

    @staticmethod
    def get_escalation_list_optimized(request, typeassist_model):
        """
        Optimized escalation list retrieval

        Key optimizations:
        1. Simplified Q queries
        2. Proper use of select_related
        3. Caching for relatively static data
        """
        S = request.session

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
            typeassist_model.objects.filter(
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

        return result

    @staticmethod
    def get_tickets_listview_optimized(request, model_class):
        """
        Optimized ticket list retrieval

        Key optimizations:
        1. Use indexed date fields for filtering
        2. Proper select_related usage
        3. Conditional filtering
        """
        from apps.core.json_utils import safe_json_parse_params

        R, S = request.GET, request.session
        P = safe_json_parse_params(R)

        # Base query with indexed fields first
        qset = model_class.objects.filter(
            cdtz__date__gte=P["from"],
            cdtz__date__lte=P["to"],
            bu_id__in=S["assignedsites"],
            client_id=S["client_id"],
        ).select_related("assignedtopeople", "assignedtogroup", "bu", "ticketcategory")

        # Handle status filtering
        status = P.get("status")
        if status == "SYSTEMGENERATED":
            qset = qset.filter(ticketsource="SYSTEMGENERATED")
        elif status:
            qset = qset.filter(status=status, ticketsource="USERDEFINED")

        # Return optimized values
        return list(
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

    @staticmethod
    def get_posting_order_list_optimized(request, model_class):
        """
        Optimized posting order list retrieval

        Key optimizations:
        1. Simple filtered query
        2. Add necessary fields based on actual usage
        3. Consider pagination for large datasets
        """
        from apps.core.json_utils import safe_json_parse_params

        R, S = request.GET, request.session
        P = safe_json_parse_params(R)

        # Basic optimized query
        qset = model_class.objects.filter(
            bu_id__in=S["assignedsites"],
            client_id=S["client_id"],
            identifier="POSTING_ORDER",
        ).select_related("people", "bu", "pgroup")

        # Add date filtering if provided
        if P.get("from") and P.get("to"):
            qset = qset.filter(
                plandatetime__date__gte=P["from"], plandatetime__date__lte=P["to"]
            )

        # Return optimized values - adjust fields based on actual view needs
        return list(
            qset.values(
                "id",
                "jobdesc",
                "plandatetime",
                "jobstatus",
                "people__peoplename",
                "bu__buname",
                "pgroup__groupname",
                "cdtz",
                "ctzoffset",
            )[:100]
        )  # Limit to prevent memory issues


# Manager method wrappers
def optimize_manager_methods():
    """
    Monkey-patch manager methods with optimized versions
    This should be called in app's ready() method
    """
    from apps.work_order_management.models import Vendor, Wom, Approver
    from apps.y_helpdesk.models import Ticket, EscalationMatrix
    from apps.core_onboarding.models import TypeAssist
    from apps.activity.models.job_model import Jobneed

    # Work Order Management optimizations
    Vendor.objects.__class__.get_vendor_list = lambda self, request, fields, related: WorkOrderQueryOptimizer.get_vendor_list_optimized(
        request, self.model
    )

    Wom.objects.__class__.get_workorder_list = lambda self, request, fields, related: WorkOrderQueryOptimizer.get_workorder_list_optimized(
        request, self.model
    )

    Wom.objects.__class__.get_workpermitlist = (
        lambda self, request: WorkOrderQueryOptimizer.get_workpermitlist_optimized(
            request, self.model
        )
    )

    Approver.objects.__class__.get_approver_list = lambda self, request, fields, related: WorkOrderQueryOptimizer.get_approver_list_optimized(
        request, self.model
    )

    Wom.objects.__class__.get_slalist = (
        lambda self, request: WorkOrderQueryOptimizer.get_slalist_optimized(
            request, self.model
        )
    )

    # Helpdesk optimizations
    EscalationMatrix.objects.__class__.get_escalation_listview = (
        lambda self, request: HelpdeskQueryOptimizer.get_escalation_list_optimized(
            request, TypeAssist
        )
    )

    Ticket.objects.__class__.get_tickets_listview = (
        lambda self, request: HelpdeskQueryOptimizer.get_tickets_listview_optimized(
            request, self.model
        )
    )

    Jobneed.objects.__class__.get_posting_order_listview = (
        lambda self, request: HelpdeskQueryOptimizer.get_posting_order_list_optimized(
            request, self.model
        )
    )
