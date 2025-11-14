"""
Scheduling Models - Shift management for facility operations.

This module contains models for managing work shifts, schedules, and timing
configurations in the facility management system. Supports complex scheduling
requirements with flexible configurations and workforce management.

Key Features:
- Flexible shift configurations with start/end times
- People count management per shift and designation
- Night shift support and special timing handling
- JSON-based shift data for extensible configurations
- Integration with business units and designations

Security:
- Input validation for time fields
- Constraint enforcement for data integrity
- Proper foreign key relationships with cascade protection
"""

from django.db import models
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from ..managers import ShiftManager


def shiftdata_json():
    """Default JSON structure for shift configuration data."""
    return {}


class Shift(BaseModel, TenantAwareModel):
    """
    Work shift model for scheduling personnel and operations.

    Manages shift timing, personnel allocation, and designation-specific
    configurations across different business units and locations.

    Features:
    - Flexible start/end time configuration
    - People count management per designation
    - Night shift handling with special rules
    - Captcha frequency settings for security
    - JSON-based extensible shift data
    """

    bu = models.ForeignKey(
        "Bt",
        verbose_name="Business Unit",
        null=True,
        on_delete=models.RESTRICT,
        related_name="shift_bu",
    )
    client = models.ForeignKey(
        "Bt",
        verbose_name="Client",
        null=True,
        on_delete=models.RESTRICT,
        related_name="shift_client",
    )
    shiftname = models.CharField(max_length=50, verbose_name="Name")
    shiftduration = models.IntegerField(null=True, verbose_name="Shift Duration")
    designation = models.ForeignKey(
        "core_onboarding.TypeAssist",
        verbose_name="Designation",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    peoplecount = models.IntegerField(
        null=True, blank=True, verbose_name="People Count"
    )
    starttime = models.TimeField(verbose_name="Start time")
    endtime = models.TimeField(verbose_name="End time")
    nightshiftappicable = models.BooleanField(
        default=True, verbose_name="Night Shift Applicable"
    )
    captchafreq = models.IntegerField(default=10, null=True)
    enable = models.BooleanField(verbose_name="Enable", default=True)
    shift_data = models.JSONField(
        encoder=DjangoJSONEncoder,
        blank=True,
        null=True,
        default=shiftdata_json,
        help_text="Extended shift configuration and metadata"
    )

    objects = ShiftManager()

    class Meta(BaseModel.Meta):
        db_table = "shift"
        verbose_name = "Shift"
        verbose_name_plural = "Shifts"
        constraints = [
            models.UniqueConstraint(
                fields=["shiftname", "bu", "designation", "client"],
                name="shiftname_bu_desgn_client_uk",
            )
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return f"{self.shiftname} ({self.starttime} - {self.endtime})"

    def get_absolute_wizard_url(self):
        return reverse("onboarding:wiz_shift_update", kwargs={"pk": self.pk})

    def is_overnight_shift(self):
        """Check if shift spans midnight."""
        return self.endtime < self.starttime if self.starttime and self.endtime else False

    def get_designation_name(self):
        """Get designation name if assigned."""
        return self.designation.taname if self.designation else "Unassigned"
