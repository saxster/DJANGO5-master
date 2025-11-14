"""
Classification and Geofencing Models.

This module contains models for hierarchical classification systems and
geographic boundary management in the facility management system.

Key Features:
- Hierarchical TypeAssist classification system
- Geographic boundary management with geofencing
- Alert and notification management
- Multi-level categorization support
- Spatial operations for location-based services

Security:
- Input validation for geographic data
- Proper constraint enforcement
- Protection against circular references
- Safe handling of spatial data
"""

from django.conf import settings
from django.urls import reverse
from django.contrib.gis.db.models import PolygonField
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from apps.client_onboarding.managers import TypeAssistManager, GeofenceManager


class TypeAssist(BaseModel, TenantAwareModel):
    """
    Hierarchical classification system for categorizing entities.

    Provides a flexible taxonomy system for organizing business units,
    designations, work types, and other categorizable entities within
    the facility management system.

    Features:
    - Self-referential hierarchy support
    - Circular reference prevention
    - Multi-tenant categorization
    - Extensible classification structure
    """

    id = models.BigAutoField(primary_key=True)
    tacode = models.CharField(_("Code"), max_length=50)
    taname = models.CharField(_("Name"), max_length=100)
    tatype = models.ForeignKey(
        "self",
        verbose_name="Parent Type",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="children",
    )
    bu = models.ForeignKey(
        "client_onboarding.Bt",
        verbose_name="Business Unit",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ta_bus",
    )
    client = models.ForeignKey(
        "client_onboarding.Bt",
        verbose_name="Client",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ta_clients",
    )
    enable = models.BooleanField(_("Enable"), default=True)

    objects = TypeAssistManager()

    class Meta(BaseModel.Meta):
        db_table = "typeassist"
        verbose_name = "Type Assist"
        verbose_name_plural = "Type Assists"
        constraints = [
            models.UniqueConstraint(
                fields=["tacode", "tatype", "client"], name="code_unique"
            ),
        ]

    def __str__(self):
        return f"{self.taname} ({self.tacode})"

    def get_absolute_url(self):
        return reverse("onboarding:ta_update", kwargs={"pk": self.pk})

    def get_all_children(self):
        """Recursively get all child TypeAssist objects."""
        if self.pk is None:
            return []

        children = [self]
        try:
            child_list = self.children.all()
        except AttributeError:
            return children

        for child in child_list:
            children.extend(child.get_all_children())
        return children

    def get_all_parents(self):
        """Recursively get all parent TypeAssist objects."""
        parents = [self]
        if self.tatype is not None:
            parent = self.tatype
            parents.extend(parent.get_all_parents())
        return parents

    def get_hierarchy_depth(self):
        """Calculate the depth of this node in the hierarchy."""
        depth = 0
        current = self
        while current.tatype is not None:
            depth += 1
            current = current.tatype
        return depth

    def get_full_path(self, separator=" > "):
        """Get the full hierarchical path as a string."""
        parents = self.get_all_parents()
        parents.reverse()  # Start from root
        return separator.join([parent.taname for parent in parents])

    def is_root(self):
        """Check if this is a root node in the hierarchy."""
        return self.tatype is None

    def is_leaf(self):
        """Check if this is a leaf node (has no children)."""
        return not self.children.exists()

    def clean(self):
        """Validate that circular references don't occur."""
        if self.tatype in self.get_all_children():
            raise ValidationError(
                "A type cannot have itself or one of its children as parent."
            )


class GeofenceMaster(BaseModel):
    """
    Geographic boundary management for location-based operations.

    Manages geofenced areas with alerting capabilities for facility
    monitoring and security. Supports polygon-based geographic boundaries
    with integration to notification systems.

    Features:
    - PostGIS polygon geometry support
    - Alert configuration for boundary violations
    - Integration with people and groups for notifications
    - Business unit and client association
    - Enable/disable functionality for operational control
    """

    gfcode = models.CharField(_("Code"), max_length=100)
    gfname = models.CharField(_("Name"), max_length=100)
    alerttext = models.CharField(_("Alert Text"), max_length=100)
    geofence = PolygonField(
        _("GeoFence"),
        srid=4326,
        geography=True,
        null=True,
        help_text="Polygon defining the geographic boundary"
    )
    alerttogroup = models.ForeignKey(
        "peoples.Pgroup",
        null=True,
        verbose_name=_("Alert to Group"),
        on_delete=models.RESTRICT,
        help_text="Group to receive geofence alerts"
    )
    alerttopeople = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        verbose_name=_("Alert to Person"),
        on_delete=models.RESTRICT,
        help_text="Individual to receive geofence alerts"
    )
    client = models.ForeignKey(
        "client_onboarding.Bt",
        null=True,
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        related_name="onboarding_geofence_clients",
    )
    bu = models.ForeignKey(
        "client_onboarding.Bt",
        null=True,
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        related_name="geofence_sites",
    )
    enable = models.BooleanField(_("Enable"), default=True)

    objects = GeofenceManager()

    class Meta(BaseModel.Meta):
        db_table = "geofencemaster"
        verbose_name = "Geofence"
        verbose_name_plural = "Geofences"
        constraints = [
            models.UniqueConstraint(fields=["gfcode", "bu"], name="gfcode_bu_uk")
        ]
        get_latest_by = ["mdtz"]

    def __str__(self):
        return f"{self.gfname} ({self.gfcode})"

    def get_area_square_meters(self):
        """Calculate geofence area in square meters."""
        if self.geofence:
            return self.geofence.area
        return 0

    def contains_point(self, point):
        """Check if a geographic point is within this geofence."""
        if self.geofence and point:
            return self.geofence.contains(point)
        return False

    def get_alert_recipients(self):
        """Get all alert recipients for this geofence."""
        recipients = []

        if self.alerttopeople:
            recipients.append(self.alerttopeople)

        if self.alerttogroup:
            # Get all people in the group
            group_members = self.alerttogroup.members.all()
            recipients.extend(group_members)

        return list(set(recipients))  # Remove duplicates

    def is_valid_geofence(self):
        """Validate geofence geometry."""
        if not self.geofence:
            return False, "No geofence geometry defined"

        if not self.geofence.valid:
            return False, "Invalid geofence geometry"

        if self.geofence.area == 0:
            return False, "Geofence has zero area"

        return True, "Valid geofence"

    def get_boundary_coordinates(self):
        """Get geofence boundary coordinates for display."""
        if self.geofence:
            return list(self.geofence.boundary.coords)
        return []
