"""
NFC Tag Models for Asset Management (Sprint 4.1)

Provides NFC/RFID tag integration for asset tracking and management:
- NFCTag: NFC/RFID tag bindings to assets
- NFCDevice: NFC reader devices
- NFCScanLog: Audit trail of NFC scans

Enables passive asset tracking, inventory management, and automated workflows.

Author: Development Team
Date: October 2025
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class NFCStatus(models.TextChoices):
    """Status choices for NFC tags."""
    ACTIVE = ("ACTIVE", "Active")
    INACTIVE = ("INACTIVE", "Inactive")
    DAMAGED = ("DAMAGED", "Damaged")
    LOST = ("LOST", "Lost")
    DECOMMISSIONED = ("DECOMMISSIONED", "Decommissioned")


class DeviceStatus(models.TextChoices):
    """Status choices for NFC devices."""
    ONLINE = ("ONLINE", "Online")
    OFFLINE = ("OFFLINE", "Offline")
    MAINTENANCE = ("MAINTENANCE", "Maintenance")
    DECOMMISSIONED = ("DECOMMISSIONED", "Decommissioned")


class ScanType(models.TextChoices):
    """Types of NFC scans."""
    CHECKIN = ("CHECKIN", "Check-In")
    CHECKOUT = ("CHECKOUT", "Check-Out")
    INSPECTION = ("INSPECTION", "Inspection")
    INVENTORY = ("INVENTORY", "Inventory")
    MAINTENANCE = ("MAINTENANCE", "Maintenance")


class NFCTag(BaseModel, TenantAwareModel):
    """
    NFC/RFID Tag Model.

    Represents a physical NFC tag that can be attached to assets for
    automated tracking and identification.
    """

    tag_uid = models.CharField(
        _("Tag UID"),
        max_length=50,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[A-F0-9]{8,32}$',
                message='Tag UID must be 8-32 hexadecimal characters'
            )
        ],
        help_text="Unique identifier of the NFC tag (hexadecimal)"
    )

    asset = models.ForeignKey(
        'activity.Asset',
        verbose_name=_("Asset"),
        on_delete=models.CASCADE,
        related_name='nfc_tags',
        help_text="Asset this tag is bound to"
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=NFCStatus.choices,
        default=NFCStatus.ACTIVE
    )

    last_scan = models.DateTimeField(
        _("Last Scan"),
        null=True,
        blank=True,
        help_text="Timestamp of most recent scan"
    )

    scan_count = models.IntegerField(
        _("Scan Count"),
        default=0,
        help_text="Total number of scans performed"
    )

    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional tag metadata (tag type, manufacturer, etc.)"
    )

    class Meta:
        db_table = 'activity_nfc_tag'
        verbose_name = _("NFC Tag")
        verbose_name_plural = _("NFC Tags")
        indexes = [
            models.Index(fields=['tenant', 'tag_uid']),
            models.Index(fields=['tenant', 'asset']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['last_scan']),
        ]

    def __str__(self):
        return f"NFC Tag {self.tag_uid} -> {self.asset.assetname}"


class NFCDevice(BaseModel, TenantAwareModel):
    """
    NFC Reader Device Model.

    Represents physical NFC reader devices deployed at various locations
    for asset tracking and verification.
    """

    device_id = models.CharField(
        _("Device ID"),
        max_length=100,
        unique=True,
        help_text="Unique identifier for NFC reader device"
    )

    device_name = models.CharField(
        _("Device Name"),
        max_length=200,
        help_text="Human-readable device name"
    )

    location = models.ForeignKey(
        'onboarding.TypeAssist',
        verbose_name=_("Location"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nfc_devices',
        help_text="Physical location of the device"
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.ONLINE
    )

    last_active = models.DateTimeField(
        _("Last Active"),
        auto_now=True,
        help_text="Timestamp of last activity"
    )

    ip_address = models.GenericIPAddressField(
        _("IP Address"),
        null=True,
        blank=True,
        help_text="Network IP address of the device"
    )

    firmware_version = models.CharField(
        _("Firmware Version"),
        max_length=50,
        blank=True,
        default="",
        help_text="Device firmware version"
    )

    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional device metadata (model, serial, etc.)"
    )

    class Meta:
        db_table = 'activity_nfc_device'
        verbose_name = _("NFC Device")
        verbose_name_plural = _("NFC Devices")
        indexes = [
            models.Index(fields=['tenant', 'device_id']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"NFC Device: {self.device_name} ({self.device_id})"


class NFCScanLog(BaseModel, TenantAwareModel):
    """
    NFC Scan Log Model.

    Audit trail of all NFC tag scans for asset tracking and verification.
    """

    tag = models.ForeignKey(
        NFCTag,
        verbose_name=_("NFC Tag"),
        on_delete=models.CASCADE,
        related_name='scan_logs'
    )

    device = models.ForeignKey(
        NFCDevice,
        verbose_name=_("NFC Device"),
        on_delete=models.CASCADE,
        related_name='scan_logs'
    )

    scanned_by = models.ForeignKey(
        'peoples.People',
        verbose_name=_("Scanned By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nfc_scans'
    )

    scan_type = models.CharField(
        _("Scan Type"),
        max_length=20,
        choices=ScanType.choices,
        default=ScanType.INSPECTION
    )

    scan_location = models.ForeignKey(
        'onboarding.TypeAssist',
        verbose_name=_("Scan Location"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Location where scan occurred"
    )

    scan_result = models.CharField(
        _("Scan Result"),
        max_length=20,
        choices=[
            ('SUCCESS', 'Success'),
            ('FAILED', 'Failed'),
            ('INVALID_TAG', 'Invalid Tag')
        ],
        default='SUCCESS'
    )

    response_time_ms = models.IntegerField(
        _("Response Time (ms)"),
        null=True,
        blank=True,
        help_text="Tag response time in milliseconds"
    )

    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional scan metadata (RSSI, read quality, etc.)"
    )

    class Meta:
        db_table = 'activity_nfc_scan_log'
        verbose_name = _("NFC Scan Log")
        verbose_name_plural = _("NFC Scan Logs")
        indexes = [
            models.Index(fields=['tenant', 'tag', 'cdtz']),
            models.Index(fields=['tenant', 'device', 'cdtz']),
            models.Index(fields=['tenant', 'scanned_by', 'cdtz']),
            models.Index(fields=['scan_type']),
            models.Index(fields=['cdtz']),
        ]
        ordering = ['-cdtz']

    def __str__(self):
        return f"NFC Scan: {self.tag.tag_uid} at {self.cdtz}"
