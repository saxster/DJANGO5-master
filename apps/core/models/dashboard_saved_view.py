"""
Dashboard Saved View Model
===========================
Allows users to save dashboard configurations (scope, filters, panels)
for quick access and sharing with team members.

Follows .claude/rules.md:
- Rule #3: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #18: DateTimeField standards
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class DashboardSavedView(BaseModel, TenantAwareModel):
    """
    User-created saved views for quick dashboard access.

    Features:
    - Save current scope (tenant/clients/sites/time/shift)
    - Save visible panels and filters
    - Share views with team members (RBAC-controlled)
    - Set as personal default view
    - Schedule automated reports from saved view
    """

    class ViewType(models.TextChoices):
        PORTFOLIO = "PORTFOLIO", _("Portfolio Overview")
        SITE = "SITE", _("Site Operations")
        ATTENDANCE = "ATTENDANCE", _("Attendance")
        TOURS = "TOURS", _("Tours")
        TASKS = "TASKS", _("Tasks")
        TICKETS = "TICKETS", _("Tickets")
        WORK_ORDERS = "WORK_ORDERS", _("Work Orders")
        REPORTS = "REPORTS", _("Reports")
        NOC = "NOC", _("NOC Dashboard")
        CUSTOM = "CUSTOM", _("Custom")

    class SharingLevel(models.TextChoices):
        PRIVATE = "PRIVATE", _("Private (Only me)")
        TEAM = "TEAM", _("Share with my team")
        SITE = "SITE", _("Share with site users")
        CLIENT = "CLIENT", _("Share with client users")
        PUBLIC = "PUBLIC", _("Public (All users)")

    name = models.CharField(
        _("View Name"),
        max_length=200,
        help_text=_("Descriptive name for this saved view")
    )

    description = models.TextField(
        _("Description"),
        blank=True,
        default="",
        help_text=_("Optional description of what this view shows")
    )

    view_type = models.CharField(
        _("View Type"),
        max_length=20,
        choices=ViewType.choices,
        default=ViewType.CUSTOM,
        db_index=True
    )

    # Scope configuration (stored as JSON)
    scope_config = models.JSONField(
        _("Scope Configuration"),
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text=_("Tenant, clients, sites, time range, shift selections")
    )

    # Filters and display settings
    filters = models.JSONField(
        _("Filters"),
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text=_("Domain-specific filters (status, priority, etc.)")
    )

    visible_panels = models.JSONField(
        _("Visible Panels"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Array of panel IDs to display")
    )

    sort_order = models.JSONField(
        _("Sort Order"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("Column sort configuration")
    )

    # Sharing and permissions
    sharing_level = models.CharField(
        _("Sharing Level"),
        max_length=20,
        choices=SharingLevel.choices,
        default=SharingLevel.PRIVATE,
        db_index=True
    )

    shared_with_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="shared_views_received",
        blank=True,
        verbose_name=_("Shared With Users"),
        help_text=_("Specific users who can access this view")
    )

    shared_with_groups = models.ManyToManyField(
        "peoples.Pgroup",
        related_name="shared_dashboard_views",
        blank=True,
        verbose_name=_("Shared With Groups"),
        help_text=_("Groups who can access this view")
    )

    # Usage tracking
    is_default = models.BooleanField(
        _("Is Default View"),
        default=False,
        help_text=_("Load this view by default for the user")
    )

    view_count = models.PositiveIntegerField(
        _("View Count"),
        default=0,
        help_text=_("Number of times this view was accessed")
    )

    last_accessed_at = models.DateTimeField(
        _("Last Accessed At"),
        null=True,
        blank=True,
        help_text=_("Last time this view was loaded")
    )

    # Page context
    page_url = models.CharField(
        _("Page URL"),
        max_length=500,
        help_text=_("URL path where this view applies")
    )

    # Email subscription (new enhancement)
    class EmailFrequency(models.TextChoices):
        NONE = "NONE", _("No Email")
        DAILY = "DAILY", _("Daily Summary")
        WEEKLY = "WEEKLY", _("Weekly Summary")
        MONTHLY = "MONTHLY", _("Monthly Summary")

    email_frequency = models.CharField(
        _("Email Frequency"),
        max_length=20,
        choices=EmailFrequency.choices,
        default=EmailFrequency.NONE,
        help_text=_("How often to email this view's data")
    )

    email_recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="subscribed_views",
        blank=True,
        verbose_name=_("Email Recipients"),
        help_text=_("Who receives scheduled emails")
    )

    last_email_sent_at = models.DateTimeField(
        _("Last Email Sent At"),
        null=True,
        blank=True,
        help_text=_("When the last scheduled email was sent")
    )

    # Export configuration (new enhancement)
    class ExportFormat(models.TextChoices):
        NONE = "NONE", _("No Export")
        CSV = "CSV", _("CSV File")
        EXCEL = "EXCEL", _("Excel Spreadsheet")
        PDF = "PDF", _("PDF Report")

    export_format = models.CharField(
        _("Export Format"),
        max_length=20,
        choices=ExportFormat.choices,
        default=ExportFormat.NONE,
        help_text=_("Format for automated exports")
    )

    export_schedule = models.CharField(
        _("Export Schedule"),
        max_length=100,
        blank=True,
        default="",
        help_text=_("Cron expression for export schedule (e.g., '0 8 * * 1' for Mondays at 8am)")
    )

    last_export_at = models.DateTimeField(
        _("Last Export At"),
        null=True,
        blank=True,
        help_text=_("When the last export was generated")
    )

    class Meta(BaseModel.Meta):
        db_table = "dashboard_saved_view"
        verbose_name = "Dashboard Saved View"
        verbose_name_plural = "Dashboard Saved Views"
        ordering = ["-last_accessed_at", "-cdtz"]
        indexes = [
            models.Index(fields=["cuser", "view_type"], name="saved_view_user_type_idx"),
            models.Index(fields=["sharing_level"], name="saved_view_sharing_idx"),
            models.Index(fields=["is_default"], name="saved_view_default_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["cuser", "name"],
                name="unique_view_name_per_user",
                violation_error_message=_("You already have a saved view with this name")
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.cuser.username})"

    def can_user_access(self, user) -> bool:
        """
        Check if a user can access this saved view.

        Args:
            user: User instance to check

        Returns:
            True if user can access, False otherwise
        """
        # Owner can always access
        if self.cuser_id == user.id:
            return True

        # Check sharing level
        if self.sharing_level == self.SharingLevel.PUBLIC:
            return True

        if self.sharing_level == self.SharingLevel.PRIVATE:
            return False

        # Check specific user sharing
        if self.shared_with_users.filter(id=user.id).exists():
            return True

        # Check group sharing
        if self.shared_with_groups.filter(people=user).exists():
            return True

        # Check tenant/client/site level sharing
        if self.sharing_level == self.SharingLevel.CLIENT:
            return user.client_id == self.cuser.client_id

        if self.sharing_level == self.SharingLevel.SITE:
            return user.bu_id == self.cuser.bu_id

        return False


__all__ = ["DashboardSavedView"]
