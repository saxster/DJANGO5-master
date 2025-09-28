"""
Capability model for the peoples app.

This module contains the Capability model which defines hierarchical
capabilities that can be assigned to users for different platform types.

Compliant with Rule #7 from .claude/rules.md (< 80 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from .base_model import BaseModel
from ..managers import CapabilityManager


class Capability(BaseModel, TenantAwareModel):
    """
    Hierarchical capability model for defining user permissions and access rights.

    Capabilities are organized in a tree structure where each capability can have
    a parent and multiple children, allowing for flexible permission hierarchies
    across different platform types (web, mobile, etc.).

    Attributes:
        capscode (CharField): Unique code identifying the capability
        capsname (CharField): Human-readable name of the capability
        parent (ForeignKey): Parent capability in the hierarchy
        cfor (CharField): Platform type this capability applies to
        client (ForeignKey): Client organization this capability belongs to
        enable (BooleanField): Whether the capability is active
    """

    class Cfor(models.TextChoices):
        """Platform types for capabilities."""
        WEB = ("WEB", "WEB")
        PORTLET = ("PORTLET", "PORTLET")
        REPORT = ("REPORT", "REPORT")
        MOB = ("MOB", "MOB")
        NOC = ("NOC", "NOC")

    capscode = models.CharField(
        _("Capability Code"),
        max_length=50,
        help_text=_("Unique code identifying this capability")
    )

    capsname = models.CharField(
        _("Capability Name"),
        max_length=1000,
        null=True,
        blank=True,
        help_text=_("Human-readable name of the capability")
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent Capability"),
        help_text=_("Parent capability in the hierarchy")
    )

    cfor = models.CharField(
        _("Platform Type"),
        max_length=10,
        default="WEB",
        choices=Cfor.choices,
        help_text=_("Platform type this capability applies to")
    )

    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        help_text=_("Client organization this capability belongs to")
    )

    enable = models.BooleanField(
        _("Enabled"),
        default=True,
        help_text=_("Whether this capability is active")
    )

    objects = CapabilityManager()

    class Meta(BaseModel.Meta):
        db_table = "capability"
        verbose_name = _("Capability")
        verbose_name_plural = _("Capabilities")
        constraints = [
            models.UniqueConstraint(
                fields=["capscode", "cfor", "client"],
                name="capability_capscode_cfor_client_uk"
            ),
        ]
        indexes = [
            models.Index(fields=['capscode'], name='capability_capscode_idx'),
            models.Index(fields=['cfor'], name='capability_cfor_idx'),
            models.Index(fields=['enable'], name='capability_enable_idx'),
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        """String representation of the capability."""
        return self.capscode

    def get_absolute_url(self):
        """Get URL for capability update view."""
        return f"/people/capabilities/update/{self.pk}/"