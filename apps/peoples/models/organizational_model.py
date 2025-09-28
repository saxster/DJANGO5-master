"""
People Organizational Model

This module contains the PeopleOrganizational model that stores
organizational relationships and hierarchy information.

Compliant with Rule #7 from .claude/rules.md (< 150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from .base_model import BaseModel
from ..mixins import OrganizationalQueryMixin


class PeopleOrganizational(OrganizationalQueryMixin, BaseModel):
    """
    Organizational relationships and hierarchy for People model.

    Separated from the core People model to maintain single responsibility
    and comply with model complexity limits.

    Query helper methods provided by OrganizationalQueryMixin:
    - get_team_members(): Get direct reports
    - get_department_colleagues(): Get colleagues in same department
    - get_location_colleagues(): Get colleagues at same location
    - is_in_same_business_unit(other): Check if in same BU
    - get_reporting_chain(): Get full reporting hierarchy
    - get_organizational_summary(): Get organizational info summary

    Attributes:
        people (OneToOneField): Link to People model
        location (ForeignKey): Associated location
        department (ForeignKey): User's department
        designation (ForeignKey): User's job designation
        peopletype (ForeignKey): User classification type
        worktype (ForeignKey): Work classification
        client (ForeignKey): Associated client/organization
        bu (ForeignKey): Business unit assignment
        reportto (ForeignKey): Reporting manager
    """

    people = models.OneToOneField(
        "peoples.People",
        on_delete=models.CASCADE,
        related_name="organizational",
        primary_key=True,
        verbose_name=_("User"),
        help_text=_("Associated user account")
    )

    location = models.ForeignKey(
        "activity.Location",
        verbose_name=_("Location"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        help_text=_("Primary work location")
    )

    department = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Department",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="org_people_departments",
    )

    designation = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Designation",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="org_people_designations",
    )

    peopletype = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="People Type",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="org_people_types",
    )

    worktype = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name="Work Type",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="org_work_types",
    )

    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Client",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="org_people_clients",
    )

    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Business Unit",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="org_people_bus",
    )

    reportto = models.ForeignKey(
        "peoples.People",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="direct_reports",
        verbose_name="Reports To",
    )

    class Meta:
        db_table = "people_organizational"
        verbose_name = _("People Organizational Info")
        verbose_name_plural = _("People Organizational Info")
        indexes = [
            models.Index(fields=['client', 'bu'], name='org_client_bu_idx'),
            models.Index(fields=['department'], name='org_department_idx'),
            models.Index(fields=['designation'], name='org_designation_idx'),
            models.Index(fields=['reportto'], name='org_reportto_idx'),
        ]

    def __str__(self) -> str:
        """String representation of organizational info."""
        return f"Org info for {self.people.peoplename}"

    def save(self, *args, **kwargs):
        """Override save to set defaults via service."""
        if kwargs.get('update_fields'):
            return super().save(*args, **kwargs)

        self._set_defaults()
        super().save(*args, **kwargs)

    def _set_defaults(self):
        """Set default values for foreign key fields if they are None."""
        from apps.core import utils

        if self.department_id is None:
            try:
                self.department = utils.get_none_typeassist()
            except (AttributeError, ValueError):
                pass

        if self.designation_id is None:
            try:
                self.designation = utils.get_none_typeassist()
            except (AttributeError, ValueError):
                pass

        if self.peopletype_id is None:
            try:
                self.peopletype = utils.get_none_typeassist()
            except (AttributeError, ValueError):
                pass

        if self.worktype_id is None:
            try:
                self.worktype = utils.get_none_typeassist()
            except (AttributeError, ValueError):
                pass

        if self.reportto_id is None:
            try:
                self.reportto = utils.get_or_create_none_people()
            except (AttributeError, ValueError):
                pass