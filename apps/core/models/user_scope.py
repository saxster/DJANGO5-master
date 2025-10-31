"""
User Scope Model
================
Stores user's current scope selection (tenant, client, sites, time range, shift)
for persistent navigation context across sessions.

Follows .claude/rules.md:
- Rule #3: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #18: DateTimeField standards
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timezone as dt_timezone

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class UserScope(BaseModel, TenantAwareModel):
    """
    User's persistent scope selection.

    Enables managers to:
    - Select multiple sites for portfolio view
    - Set time range (today, 7d, 30d, custom)
    - Filter by shift
    - Resume where they left off on next login
    """

    class TimeRange(models.TextChoices):
        TODAY = "TODAY", _("Today")
        LAST_24H = "24H", _("Last 24 Hours")
        LAST_7D = "7D", _("Last 7 Days")
        LAST_30D = "30D", _("Last 30 Days")
        CUSTOM = "CUSTOM", _("Custom Range")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scope",
        verbose_name=_("User"),
        help_text=_("User this scope belongs to")
    )

    # Multi-site selection
    selected_clients = models.JSONField(
        _("Selected Clients"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Array of client IDs for portfolio view")
    )

    selected_sites = models.JSONField(
        _("Selected Sites"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Array of site/BU IDs for filtering")
    )

    # Time context
    time_range = models.CharField(
        _("Time Range"),
        max_length=20,
        choices=TimeRange.choices,
        default=TimeRange.TODAY
    )

    date_from = models.DateField(
        _("Custom Date From"),
        null=True,
        blank=True,
        help_text=_("Start date for custom range")
    )

    date_to = models.DateField(
        _("Custom Date To"),
        null=True,
        blank=True,
        help_text=_("End date for custom range")
    )

    # Shift context
    shift = models.ForeignKey(
        "onboarding.Shift",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_scopes",
        verbose_name=_("Selected Shift"),
        help_text=_("Filter data by shift (null = all shifts)")
    )

    # Recently viewed entities (for quick access)
    recently_viewed = models.JSONField(
        _("Recently Viewed"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Recently accessed pages/entities")
    )

    # Last active view
    last_view_url = models.CharField(
        _("Last View URL"),
        max_length=500,
        blank=True,
        default="",
        help_text=_("Last page user was viewing")
    )

    class Meta(BaseModel.Meta):
        db_table = "user_scope"
        verbose_name = "User Scope"
        verbose_name_plural = "User Scopes"
        indexes = [
            models.Index(fields=["user"], name="user_scope_user_idx"),
            models.Index(fields=["tenant"], name="user_scope_tenant_idx"),
        ]

    def __str__(self):
        return f"{self.user.username}'s scope"

    def get_scope_dict(self) -> dict:
        """
        Returns scope as dictionary for API responses.
        """
        return {
            "tenant_id": self.tenant_id,
            "client_ids": self.selected_clients or [],
            "bu_ids": self.selected_sites or [],
            "time_range": self.time_range,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "shift_id": self.shift_id,
        }

    def update_from_dict(self, scope_data: dict) -> None:
        """
        Update scope from dictionary (from API request).

        Args:
            scope_data: Dictionary with scope fields
        """
        if "client_ids" in scope_data:
            self.selected_clients = scope_data["client_ids"]

        if "bu_ids" in scope_data:
            self.selected_sites = scope_data["bu_ids"]

        if "time_range" in scope_data:
            self.time_range = scope_data["time_range"]

        if "date_from" in scope_data and scope_data["date_from"]:
            if isinstance(scope_data["date_from"], str):
                self.date_from = datetime.fromisoformat(scope_data["date_from"]).date()
            else:
                self.date_from = scope_data["date_from"]

        if "date_to" in scope_data and scope_data["date_to"]:
            if isinstance(scope_data["date_to"], str):
                self.date_to = datetime.fromisoformat(scope_data["date_to"]).date()
            else:
                self.date_to = scope_data["date_to"]

        if "shift_id" in scope_data:
            self.shift_id = scope_data["shift_id"]

        self.save()


__all__ = ["UserScope"]
