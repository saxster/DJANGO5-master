"""
Subscription Model - Subscription lifecycle management for services and licenses.

Manages client subscriptions with status tracking, device assignment,
and termination handling for operational and billing purposes.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from ..managers import SubscriptionManger
from .device import Device


class Subscription(BaseModel, TenantAwareModel):
    """
    Subscription lifecycle management for services and licenses.

    Manages client subscriptions with status tracking, device assignment,
    and termination handling for operational and billing purposes.

    Features:
    - Date-based subscription periods
    - Status management (Active/Inactive)
    - Device assignment tracking
    - Termination reason tracking
    - Temporary subscription support
    """

    class StatusChoices(models.TextChoices):
        A = ("Active", "Active")
        IA = ("In Active", "In Active")

    startdate = models.DateField(_("Start Date"), auto_now=False, auto_now_add=False)
    enddate = models.DateField(_("End Date"), auto_now=False, auto_now_add=False)
    terminateddate = models.DateField(
        _("Terminated Date"), auto_now=False, null=True, auto_now_add=False
    )
    reason = models.TextField(_("Reason"), null=True, blank=True)
    status = models.CharField(
        _("Status"),
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.A.value,
    )
    assignedhandset = models.ForeignKey(
        Device,
        verbose_name=_("Assigned Handset"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    client = models.ForeignKey(
        "Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    istemporary = models.BooleanField(_("Is Temporary"), default=False)

    objects = SubscriptionManger()

    class Meta(BaseModel.Meta):
        db_table = "subscription"
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        constraints = [
            models.UniqueConstraint(
                fields=["startdate", "enddate", "client"],
                name="startdate_enddate_client_uk",
            )
        ]

    def __str__(self):
        return f"Subscription {self.id} - {self.client}"

    def is_active(self):
        """Check if subscription is currently active."""
        today = timezone.now().date()
        return (
            self.status == self.StatusChoices.A and
            self.startdate <= today <= self.enddate and
            not self.terminateddate
        )

    def days_remaining(self):
        """Calculate days remaining in subscription."""
        if not self.is_active():
            return 0

        today = timezone.now().date()
        if self.enddate > today:
            return (self.enddate - today).days
        return 0

    def is_expiring_soon(self, days_threshold=30):
        """Check if subscription is expiring within threshold."""
        return 0 < self.days_remaining() <= days_threshold

    def terminate(self, reason=None):
        """Terminate subscription with reason."""
        self.status = self.StatusChoices.IA
        self.terminateddate = timezone.now().date()
        if reason:
            self.reason = reason
        self.save()

    def extend_subscription(self, new_enddate):
        """Extend subscription to new end date."""
        if new_enddate > self.enddate:
            self.enddate = new_enddate
            if self.status == self.StatusChoices.IA:
                self.status = self.StatusChoices.A
                self.terminateddate = None
            self.save()

    def get_duration_days(self):
        """Get total subscription duration in days."""
        return (self.enddate - self.startdate).days
