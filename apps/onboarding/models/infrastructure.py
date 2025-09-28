"""
Infrastructure Management Models.

This module contains models for managing physical and virtual infrastructure
components including devices, subscriptions, and operational tracking.

Key Features:
- Device lifecycle management with communication tracking
- Subscription management with status tracking
- Downtime history for operational monitoring
- Integration with business units and clients
- Status-based filtering and reporting

Security:
- IMEI validation and uniqueness constraints
- Proper foreign key relationships
- Status-based access controls
- Audit trail for all infrastructure changes
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
from ..managers import DeviceManager, SubscriptionManger


class Device(BaseModel, TenantAwareModel):
    """
    Physical device management for facility operations.

    Tracks mobile devices, tablets, and other hardware used in facility
    management operations with communication monitoring and user assignment.

    Features:
    - IMEI-based device identification
    - Last communication tracking
    - User assignment history
    - Phone number management
    - Device status monitoring
    """

    handsetname = models.CharField(_("Handset Name"), max_length=100)
    modelname = models.CharField(_("Model"), max_length=50)
    dateregistered = models.DateField(_("Date Registered"), default=timezone.now)
    lastcommunication = models.DateTimeField(
        _("Last Communication"),
        auto_now=False,
        auto_now_add=False,
        help_text="Last successful communication with device"
    )
    imeino = models.CharField(
        _("IMEI No"),
        max_length=15,
        null=True,
        blank=True,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{15}$',
                message='IMEI must be exactly 15 digits',
                code='invalid_imei'
            )
        ],
        help_text="International Mobile Equipment Identity number"
    )
    lastloggedinuser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Last Logged In User"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    phoneno = models.CharField(
        _("Phone No"),
        max_length=15,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message='Phone number must be 9-15 digits',
                code='invalid_phone'
            )
        ]
    )
    isdeviceon = models.BooleanField(_("Is Device On"), default=True)
    client = models.ForeignKey(
        "Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )

    objects = DeviceManager()

    class Meta(BaseModel.Meta):
        db_table = "device"
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return self.handsetname

    def is_online(self, threshold_minutes=30):
        """Check if device is considered online based on last communication."""
        if not self.lastcommunication:
            return False

        threshold = timezone.now() - timezone.timedelta(minutes=threshold_minutes)
        return self.lastcommunication >= threshold

    def get_offline_duration(self):
        """Get duration since device went offline."""
        if not self.lastcommunication:
            return None

        return timezone.now() - self.lastcommunication

    def update_communication(self, user=None):
        """Update last communication timestamp and user."""
        self.lastcommunication = timezone.now()
        if user:
            self.lastloggedinuser = user
        self.save()

    def get_status_display(self):
        """Get human-readable device status."""
        if not self.isdeviceon:
            return "Disabled"
        elif self.is_online():
            return "Online"
        else:
            return "Offline"


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


class DownTimeHistory(BaseModel):
    """
    System downtime tracking for operational monitoring.

    Records periods when systems or services are unavailable,
    supporting operational analytics and SLA reporting.

    Features:
    - Time-based downtime tracking
    - Reason classification
    - Client-specific downtime records
    - Duration calculation support
    - Historical trend analysis
    """

    reason = models.TextField(_("Downtime Reason"))
    starttime = models.DateTimeField(_("Start"), default=timezone.now)
    endtime = models.DateTimeField(_("End"), default=timezone.now)
    client = models.ForeignKey(
        "Bt",
        null=True,
        verbose_name=_("Client"),
        on_delete=models.RESTRICT
    )

    class Meta(BaseModel.Meta):
        db_table = "downtime_history"
        verbose_name = "Downtime History"
        verbose_name_plural = "Downtime Histories"
        get_latest_by = ["mdtz"]

    def __str__(self):
        return f"Downtime: {self.reason}"

    def get_duration(self):
        """Calculate downtime duration."""
        return self.endtime - self.starttime

    def get_duration_hours(self):
        """Get downtime duration in hours."""
        duration = self.get_duration()
        return duration.total_seconds() / 3600

    def is_ongoing(self):
        """Check if downtime is still ongoing."""
        return self.endtime <= self.starttime or self.endtime <= timezone.now()

    def end_downtime(self, reason_update=None):
        """Mark downtime as ended."""
        self.endtime = timezone.now()
        if reason_update:
            self.reason = f"{self.reason} - Resolution: {reason_update}"
        self.save()

    def get_impact_level(self):
        """Classify downtime impact based on duration."""
        hours = self.get_duration_hours()
        if hours < 1:
            return "Low"
        elif hours < 4:
            return "Medium"
        elif hours < 24:
            return "High"
        else:
            return "Critical"