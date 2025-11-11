"""
Work Order Management Services
Optimized query patterns and caching strategies for work order operations
"""

from typing import Any

from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.db.models import Max, Q


def _require_session_value(session, key: str, allow_empty: bool = False) -> Any:
    """
    Fetch a session value and raise a descriptive error if it is missing.
    """
    if key not in session:
        raise SuspiciousOperation(f"Missing session key '{key}' required for work order queries.")

    value = session.get(key)

    if value is None:
        raise SuspiciousOperation(f"Session key '{key}' cannot be None.")

    if isinstance(value, str) and not value.strip():
        raise SuspiciousOperation(f"Session key '{key}' cannot be blank.")

    if isinstance(value, (list, tuple, set)):
        if not value and not allow_empty:
            raise SuspiciousOperation(f"Session key '{key}' requires at least one entry.")
    return value

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
        4. Cache key includes filter parameters to prevent incorrect data return

        Cache key strategy:
        - Includes client_id for tenant isolation
        - Includes MD5 hash of sorted filter params (type, site_id, etc.)
        - Different filter combinations get separate cache entries
        """
        import hashlib
        import json
        from apps.core.json_utils import safe_json_parse_params

        R, S = request.GET, request.session
        client_id = _require_session_value(S, "client_id")

        # Parse filter parameters
        params = {}
        if R.get("params"):
            params = safe_json_parse_params(R)

        # Build cache key with params hash to ensure unique cache per filter combo
        params_hash = hashlib.md5(
            json.dumps(params, sort_keys=True).encode()
        ).hexdigest()[:8]
        cache_key = cls._build_vendor_cache_key(model_class, client_id, params_hash)

        # Try cache first for vendor lists (relatively static data)
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Base query with tenant and enabled filters
        qset = model_class.objects.filter(client_id=client_id, enable=True)

        # Apply filter parameters if provided
        if params.get("type"):
            qset = qset.filter(type=params["type"])
        if params.get("site_id"):
            qset = qset.filter(site_id=params["site_id"])

        # Use only() to limit fields loaded from database
        qset = qset.only("id", "code", "name", "type", "address", "email", "mobno").order_by("name")

        # Convert to list for caching
        result = list(
            qset.values("id", "code", "name", "type", "address", "email", "mobno")
        )

        # Cache the result
        cache.set(cache_key, result, WorkOrderQueryOptimizer.CACHE_TTL)

        return result

    @staticmethod
    def _build_vendor_cache_key(model_class, client_id: Any, params_hash: str) -> str:
        """
        Include the latest vendor update timestamp in the cache key to avoid stale reads.
        """
        latest_update = model_class.objects.filter(client_id=client_id).aggregate(
            latest=Max('mdtz')
        )['latest']
        update_marker = latest_update.isoformat() if latest_update else 'no_updates'
        return f"vendor_list_{client_id}_{params_hash}_{update_marker}"

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
        client_id = _require_session_value(S, "client_id")
        P = safe_json_parse_params(request.GET)

        # Start with indexed field filters
        qset = model_class.objects.filter(
            client_id=client_id,
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
        client_id = _require_session_value(S, "client_id")
        bu_id = _require_session_value(S, "bu_id")
        people_id = _require_session_value(S, "people_id")
        P = safe_json_parse_params(R)

        # Single query for approver check
        is_approver = Approver.objects.filter(
            people_id=people_id,
            approverfor__contains=["WORKPERMIT"],
            identifier="APPROVER",
        ).exists()

        # Base queryset with common filters
        base_filters = {
            "parent_id": 1,
            "client_id": client_id,
            "bu_id": bu_id,
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
        bu_id = _require_session_value(S, "bu_id")
        client_id = _require_session_value(S, "client_id")
        assigned_sites = _require_session_value(S, "assignedsites", allow_empty=True)
        if not isinstance(assigned_sites, list):
            assigned_sites = list(assigned_sites)

        # Build cache key
        cache_key = f"approver_list_{bu_id}_{client_id}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Simplified query logic
        # Build filters step by step for clarity
        site_filter = Q(bu_id=bu_id)
        if assigned_sites:
            site_filter |= Q(bu_id__in=assigned_sites)

        # Add client-wide filter
        client_filter = Q(forallsites=True, client_id=client_id)

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
                client_id=client_id,
                bu_id=bu_id,
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
        client_id = _require_session_value(S, "client_id")
        assigned_sites = _require_session_value(S, "assignedsites", allow_empty=True)
        if not isinstance(assigned_sites, list):
            assigned_sites = list(assigned_sites)

        # Build cache key
        cache_key = (
            f"escalation_list_{client_id}_{str(sorted(assigned_sites))}"
        )

        # Check cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Optimized query
        qset = (
            typeassist_model.objects.filter(
                Q(bu_id__in=assigned_sites + [1])
                | Q(cuser_id=1)
                | Q(cuser__is_superuser=True),
                Q(client_id=client_id) | Q(client_id=1),
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
        assigned_sites = _require_session_value(S, "assignedsites", allow_empty=True)
        if not isinstance(assigned_sites, list):
            assigned_sites = list(assigned_sites)
        client_id = _require_session_value(S, "client_id")

        # Base query with indexed fields first
        qset = model_class.objects.filter(
            cdtz__date__gte=P["from"],
            cdtz__date__lte=P["to"],
            bu_id__in=assigned_sites,
            client_id=client_id,
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
        assigned_sites = _require_session_value(S, "assignedsites", allow_empty=True)
        if not isinstance(assigned_sites, list):
            assigned_sites = list(assigned_sites)
        client_id = _require_session_value(S, "client_id")

        # Basic optimized query
        qset = model_class.objects.filter(
            bu_id__in=assigned_sites,
            client_id=client_id,
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
