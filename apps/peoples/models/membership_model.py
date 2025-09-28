"""
Group membership model for the peoples app.

This module contains the Pgbelonging model which manages the many-to-many
relationships between people and groups with additional assignment information.

Compliant with Rule #7 from .claude/rules.md (< 80 lines).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from .base_model import BaseModel
from ..managers import PgblngManager


class Pgbelonging(BaseModel, TenantAwareModel):
    """
    Group membership model linking people to groups with site assignments.

    Manages the relationship between people and groups, including leadership
    roles and site-specific assignments within the organizational structure.

    Attributes:
        pgroup (ForeignKey): The group this membership belongs to
        people (ForeignKey): The person who is a member
        isgrouplead (BooleanField): Whether this person leads the group
        assignsites (ForeignKey): Sites assigned to this person through this group
        bu (ForeignKey): Business unit association
        client (ForeignKey): Client organization association
    """

    pgroup = models.ForeignKey(
        "Pgroup",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelongs_grps",
        verbose_name=_("Group"),
        help_text=_("The group this membership belongs to")
    )

    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelongs_peoples",
        verbose_name=_("Person"),
        help_text=_("The person who is a member of this group")
    )

    isgrouplead = models.BooleanField(
        _("Group Leader"),
        default=False,
        help_text=_("Whether this person is a leader of the group")
    )

    assignsites = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelongs_assignsites",
        verbose_name=_("Assigned Sites"),
        help_text=_("Sites assigned to this person through this group membership")
    )

    bu = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelonging_sites",
        verbose_name=_("Business Unit"),
        help_text=_("Business unit for this membership")
    )

    client = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="pgbelonging_clients",
        verbose_name=_("Client"),
        help_text=_("Client organization for this membership")
    )

    objects = PgblngManager()

    class Meta(BaseModel.Meta):
        db_table = "pgbelonging"
        verbose_name = _("Group Membership")
        verbose_name_plural = _("Group Memberships")
        constraints = [
            models.UniqueConstraint(
                fields=["pgroup", "people", "assignsites", "client"],
                name="pgbelonging_pgroup_people_assignsites_client_uk",
            )
        ]
        indexes = [
            models.Index(fields=['pgroup', 'people'], name='pgbelonging_group_person_idx'),
            models.Index(fields=['isgrouplead'], name='pgbelonging_leader_idx'),
            models.Index(fields=['assignsites'], name='pgbelonging_sites_idx'),
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        """String representation of the membership."""
        group_name = self.pgroup.groupname if self.pgroup else "Unknown Group"
        person_name = self.people.peoplename if self.people else "Unknown Person"
        return f"{person_name} in {group_name}"

    @property
    def is_active_membership(self):
        """Check if this is an active membership (both group and person are active)."""
        return (
            self.pgroup and self.pgroup.enable and
            self.people and self.people.enable and self.people.isverified
        )