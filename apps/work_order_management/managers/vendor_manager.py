from django.db.models import Q
from apps.tenants.managers import TenantAwareManager
from apps.core.json_utils import safe_json_parse_params
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils.timezone import make_aware
from django.core.cache import cache
import logging

logger = logging.getLogger("django")


class VendorManager(TenantAwareManager):
    """
    Custom manager for Vendor model with tenant-aware filtering.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_vendor_list(self, request, fields, related):
        """Optimized vendor list retrieval with caching"""
        R, S = request.GET, request.session
        if R.get("params"):
            P = safe_json_parse_params(R)

        # Check cache first for vendor lists (relatively static data)
        cache_key = f"vendor_list_{S['client_id']}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Only use select_related if related fields are provided
        qobjs = self.filter(client_id=S["client_id"], enable=True)

        if related:
            qobjs = qobjs.select_related(*related)

        result = list(qobjs.values(*fields).order_by("name"))

        # Cache for 5 minutes
        cache.set(cache_key, result, 300)

        return result or []

    def get_vendors_for_mobile(self, request, clientid, mdtz, buid, ctzoffset):
        if not isinstance(mdtz, datetime):
            mdtz = datetime.strptime(mdtz, "%Y-%m-%d %H:%M:%S")
        mdtz = make_aware(mdtz, timezone=dt_timezone.utc)

        mdtz = mdtz - timedelta(minutes=ctzoffset)

        qset = self.filter(
            Q(bu_id=buid) | Q(show_to_all_sites=True),
            mdtz__gte=mdtz,
            client_id=clientid,
        ).values()

        return qset or self.none()
