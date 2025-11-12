"""
Device Model - Physical device management for facility operations.

Tracks mobile devices, tablets, and other hardware used in facility
management operations with communication monitoring and user assignment.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
from ..managers import DeviceManager


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
