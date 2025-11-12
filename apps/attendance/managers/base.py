"""
Base manager for PeopleEventlog (Attendance) with tenant-aware filtering.

Provides the foundation manager class and common utilities.
"""
from datetime import timedelta, datetime, date
from django.db import models
from apps.tenants.managers import TenantAwareManager
import logging

logger = logging.getLogger("django")


class PELManager(TenantAwareManager):
    """
    Custom manager for PeopleEventlog (Attendance) model with tenant-aware filtering.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    - Inherited from TenantAwareManager (apps/tenants/managers.py)

    This base manager is extended by specialized managers in this module.
    Import from managers/__init__.py to get the full manager with all methods.
    """
    use_in_migrations = True

    def get_current_month_sitevisitorlog(self, peopleid):
        """Get site visitor logs for the past 7 days"""
        qset = self.select_related("bu", "peventtype").filter(
            ~models.Q(people_id=-1),
            peventtype__tacode="AUDIT",
            people_id=peopleid,
            datefor__gte=datetime.date() - timedelta(days=7),
        )
        return qset or self.none()

    def get_sitevisited_log(self, clientid, peopleid, ctzoffset):
        """Get site visit log for the past 7 days"""
        seven_days_ago = (datetime.now() + timedelta(minutes=ctzoffset)) - timedelta(
            days=7
        )
        return (
            self.get_queryset()
            .filter(
                people_id=peopleid,
                client_id=clientid,
                punchouttime__lte=seven_days_ago,
                peventtype__tacode="SITEVISIT",
            )
            .select_related("peventtype", "bu")
            .annotate(buname=models.F("bu__buname"), bucode=models.F("bu__bucode"))
            .values(
                "id",
                "bu_id",
                "punchintime",
                "punchouttime",
                "ctzoffset",
                "buname",
                "bucode",
                "otherlocation",
            )
            or self.none()
        )
