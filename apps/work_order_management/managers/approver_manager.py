from django.db.models import Q, F
from apps.tenants.managers import TenantAwareManager
from django.core.cache import cache
import logging

logger = logging.getLogger("django")


class ApproverManager(TenantAwareManager):
    """
    Custom manager for Approver model with tenant-aware filtering.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_approver_list(self, request, fields, related):
        """Optimized approver list retrieval with caching"""
        R, S = request.GET, request.session

        # Build cache key
        cache_key = f"approver_list_{S['bu_id']}_{S['client_id']}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Simplified query logic
        assignedsites = S.get("assignedsites", [])

        # Build filters step by step for clarity and performance
        site_filter = Q(bu_id=S["bu_id"])
        if assignedsites:
            site_filter |= Q(bu_id__in=assignedsites)

        # Add client-wide filter
        client_filter = Q(forallsites=True, client_id=S["client_id"])

        # Combined query
        qobjs = self.filter(site_filter | client_filter)

        if related:
            qobjs = qobjs.select_related(*related)

        result = list(qobjs.values(*fields))

        # Cache for 5 minutes
        cache.set(cache_key, result, 300)

        return result or []

    def get_approver_options_wp(self, request):
        S = request.session
        assignedsites = S.get("assignedsites", [])

        # Ensure assignedsites is always a list
        if isinstance(assignedsites, (int, str)):
            assignedsites = [assignedsites]
        elif not isinstance(assignedsites, (list, tuple)):
            assignedsites = []

        qset = (
            self.annotate(
                text=F("people__peoplename"),
            )
            .filter(
                (Q(bu_id=S["bu_id"]) | Q(sites__contains=assignedsites))
                | (Q(forallsites=True) & Q(client_id=S["client_id"])),
                approverfor__contains=["WORKPERMIT"],
                identifier="APPROVER",
            )
            .values("id", "text")
        )
        return qset or self.none()

    def get_verifier_options_wp(self, request):
        S = request.session
        assignedsites = S.get("assignedsites", [])
        if not isinstance(assignedsites, (list, tuple)):
            assignedsites = [assignedsites]
        qset = (
            self.annotate(
                text=F("people__peoplename"),
            )
            .filter(
                (Q(bu_id=S["bu_id"]) | Q(sites__contains=assignedsites))
                | (Q(forallsites=True) & Q(client_id=S["client_id"])),
                approverfor__contains=["WORKPERMIT"],  # Ensure this is a list
                identifier="VERIFIER",
            )
            .values("id", "text")
        )
        return qset or self.none()

    def get_approver_options_sla(self, request):
        S = request.session
        qset = (
            self.annotate(
                text=F("people__peoplename"),
            )
            .filter(
                (Q(bu_id=S["bu_id"]) | Q(sites__contains=S["assignedsites"]))
                | (Q(forallsites=True) & Q(client_id=S["client_id"])),
                approverfor__contains=["SLA_TEMPLATE"],
                identifier="APPROVER",
            )
            .values("id", "text")
        )
        return qset or self.none()

    def get_approver_list_for_mobile(self, buid, clientid):
        qset = (
            self.select_related()
            .filter(Q(bu_id=buid) | Q(forallsites=True), client_id=clientid)
            .annotate(
                peoplecode=F("people__peoplecode"), peoplename=F("people__peoplename")
            )
            .values(
                "id",
                "cdtz",
                "mdtz",
                "cuser_id",
                "muser_id",
                "ctzoffset",
                "bu_id",
                "client_id",
                "people_id",
                "peoplename",
                "peoplecode",
                "forallsites",
                "approverfor",
                "sites",
                "identifier",
            )
        )
        if qset:
            for obj in qset:
                obj["approverfor"] = ",".join(obj["approverfor"] or "")
                obj["sites"] = ",".join(obj["sites"] or "")
        logger.info(f"Qset : {qset}")
        return qset or self.none()
