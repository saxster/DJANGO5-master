"""
Work Order Management - Vendor Model

Vendor/contractor management for work order assignment and coordination.
"""
import uuid
from django.db import models
from django.contrib.gis.db.models import PointField
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from ..managers import VendorManager


class Vendor(BaseModel, TenantAwareModel):
    """
    Vendor/contractor company model for work order assignment.

    Manages vendor information including contact details, GPS location,
    and site-specific or global availability.
    """
    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    code = models.CharField(_("Code"), max_length=50, null=True, blank=False)
    name = models.CharField(_("Name"), max_length=255, null=True, blank=False)
    type = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Type"),
        null=True,
        on_delete=models.CASCADE,
    )
    address = models.TextField(
        max_length=500, verbose_name="Address", blank=True, null=True
    )
    gpslocation = PointField(
        _("GPS Location"), null=True, blank=True, geography=True, srid=4326
    )
    enable = models.BooleanField(_("Enable"), default=True)
    mobno = models.CharField(_("Mob No"), max_length=15)
    email = models.CharField(_("Email"), max_length=100)
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="vendor_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="vendor_bus",
    )
    show_to_all_sites = models.BooleanField(_("Applicable to all sites"), default=False)
    description = models.TextField(
        _("Description"), max_length=500, null=True, blank=True
    )

    objects = VendorManager()

    class Meta(BaseModel.Meta):
        db_table = "vendor"
        verbose_name = "vendor company"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code", "client"],
                name="tenant_code_client"
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'cdtz'], name='vendor_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'enable'], name='vendor_tenant_enable_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.code}{" - " + self.type.taname + ")" if self.type else ")"}'
