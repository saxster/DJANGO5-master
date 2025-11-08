"""
Group and Group Belonging admin interfaces.

Provides:
    - GroupAdmin: Manage people groups and site groups
    - PgbelongingAdmin: Manage group memberships
    - Import/Export support for bulk operations
"""

from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from apps.peoples import models as pm
from .import_export_resources import (
    GroupResource,
    GroupBelongingResource,
)


@admin.register(pm.Pgroup)
class GroupAdmin(ImportExportModelAdmin):
    """
    Admin interface for Pgroup model.

    Features:
        - Import/Export support
        - Client and site filtering
        - Group type identification (People/Site groups)
        - Optimized querysets
    """

    resource_class = GroupResource

    fields = ["groupname", "enable", "identifier", "client", "bu"]

    list_display = [
        "id",
        "groupname",
        "enable",
        "identifier",
        "client",
        "bu",
    ]

    list_display_links = ["groupname", "enable", "identifier"]

    list_select_related = ("identifier", "client", "bu", "cuser", "muser")

    search_fields = [
        "groupname",
        "identifier__tacode",
        "client__bucode",
        "bu__bucode",
    ]

    list_filter = [
        "enable",
        "identifier",
        "client",
        "bu",
    ]

    list_per_page = 50

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pass request context to resource."""
        return {"request": request}


@admin.register(pm.Pgbelonging)
class PgbelongingAdmin(ImportExportModelAdmin):
    """
    Admin interface for Pgbelonging (Group Membership) model.

    Features:
        - Import/Export support
        - Manage people and site assignments to groups
        - Group lead designation
        - Optimized querysets
    """

    resource_class = GroupBelongingResource

    fields = [
        "id",
        "pgroup",
        "people",
        "isgrouplead",
        "assignsites",
        "bu",
        "client",
    ]

    list_display = [
        "id",
        "pgroup",
        "people",
        "isgrouplead",
        "assignsites",
        "bu",
    ]

    list_display_links = ["pgroup", "people"]

    list_select_related = (
        "pgroup",
        "people",
        "assignsites",
        "bu",
        "client",
        "cuser",
        "muser",
    )

    search_fields = [
        "pgroup__groupname",
        "people__peoplename",
        "people__peoplecode",
        "assignsites__bucode",
    ]

    list_filter = [
        "isgrouplead",
        "pgroup",
        "client",
        "bu",
    ]

    list_per_page = 50

    def get_resource_kwargs(self, request, *args, **kwargs):
        """Pass request context to resource."""
        return {"request": request}
