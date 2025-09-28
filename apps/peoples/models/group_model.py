"""
Group and permission models for the peoples app.

This module contains group management models including permission groups
and people groups with their associated business logic.

Compliant with Rule #7 from .claude/rules.md (< 100 lines).
"""

from django.contrib.auth.models import Group
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from .base_model import BaseModel
from ..managers import PgroupManager


class PermissionGroup(Group):
    """
    Extended permission group model with custom database table.

    Extends Django's built-in Group model to use a custom database table
    name while maintaining all the functionality of the base Group model.
    """

    class Meta:
        db_table = "permissiongroup"
        verbose_name = _("Permission Group")
        verbose_name_plural = _("Permission Groups")


class Pgroup(BaseModel, TenantAwareModel):
    """
    People group model for organizing users within business contexts.

    Represents logical groupings of people for various organizational
    purposes like site assignments, project teams, or functional groups.

    Attributes:
        groupname (CharField): Name of the group
        grouplead (ForeignKey): User who leads this group
        enable (BooleanField): Whether the group is active
        identifier (ForeignKey): Type/category identifier for the group
        bu (ForeignKey): Business unit association
        client (ForeignKey): Client/organization association
    """

    groupname = models.CharField(
        _("Group Name"),
        max_length=250,
        help_text=_("Name of the people group")
    )

    grouplead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_groupleads",
        verbose_name=_("Group Leader"),
        help_text=_("User who leads this group")
    )

    enable = models.BooleanField(
        _("Enabled"),
        default=True,
        help_text=_("Whether this group is active")
    )

    identifier = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Group Type"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_identifiers",
        help_text=_("Type/category identifier for the group")
    )

    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Business Unit"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_bus",
        help_text=_("Associated business unit")
    )

    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgroup_clients",
        help_text=_("Associated client organization")
    )

    objects = PgroupManager()

    class Meta(BaseModel.Meta):
        db_table = "pgroup"
        verbose_name = _("People Group")
        verbose_name_plural = _("People Groups")
        constraints = [
            models.UniqueConstraint(
                fields=["groupname", "identifier", "client"],
                name="pgroup_groupname_identifier_client_uk",
            ),
        ]
        indexes = [
            models.Index(fields=['groupname'], name='pgroup_groupname_idx'),
            models.Index(fields=['enable'], name='pgroup_enable_idx'),
            models.Index(fields=['client', 'bu'], name='pgroup_org_idx'),
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        """String representation of the group."""
        return self.groupname

    def get_absolute_wizard_url(self):
        """Get URL for wizard update view."""
        return f"/people/groups/wizard/update/{self.pk}/"

    def get_active_members(self):
        """
        Get all active members of this group.

        Returns:
            QuerySet: Active Pgbelonging records for this group
        """
        return self.pgbelongs_grps.select_related('people').filter(
            people__enable=True,
            people__isverified=True
        )

    def get_group_leaders(self):
        """
        Get all group leaders.

        Returns:
            QuerySet: People who are leaders of this group
        """
        return self.pgbelongs_grps.select_related('people').filter(
            isgrouplead=True,
            people__enable=True
        )

    @property
    def member_count(self):
        """Get the count of active members in this group."""
        return self.get_active_members().count()

    @property
    def is_site_group(self):
        """Check if this is a site group based on identifier."""
        return self.identifier and self.identifier.tacode == "SITEGROUP"

    @property
    def is_people_group(self):
        """Check if this is a people group based on identifier."""
        return self.identifier and self.identifier.tacode == "PEOPLEGROUP"