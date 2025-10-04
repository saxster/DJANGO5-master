"""
Business Unit Model (Bt) - Core facility management entity.

This module contains the primary business unit model that represents
hierarchical organizational structures in the facility management system.
Refactored from monolithic models.py for improved maintainability.

Key Features:
- Hierarchical business unit structure
- GPS location and geofencing support
- Conversational onboarding integration
- Comprehensive caching strategy for performance
- Enhanced audit trail and permissions

Security:
- Input validation and sanitization
- SQL injection protection via ORM
- Proper constraint enforcement
"""

from django.conf import settings
from django.urls import reverse
from django.contrib.gis.db.models import PointField
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
import uuid

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
from ..managers import BtManager


def bu_defaults():
    """Default preferences for business units with comprehensive settings."""
    return {
        "mobilecapability": [],
        "validimei": "",
        "webcapability": [],
        "portletcapability": [],
        "validip": "",
        "reliveronpeoplecount": 0,
        "reportcapability": [],
        "usereliver": False,
        "pvideolength": 10,
        "guardstrenth": 0,
        "malestrength": 0,
        "femalestrength": 0,
        "siteclosetime": "",
        "tag": "",
        "siteopentime": "",
        "nearbyemergencycontacts": [],
        "maxadmins": 5,
        "address": "",
        "address2": None,
        "permissibledistance": 0,
        "controlroom": [],
        "ispermitneeded": False,
        "no_of_devices_allowed": 0,
        "no_of_users_allowed_mob": 0,
        "no_of_users_allowed_web": 0,
        "no_of_users_allowed_both": 0,
        "devices_currently_added": 0,
        "startdate": "",
        "enddate": "",
        "onstop": "",
        "onstopmessage": "",
        "clienttimezone": "",
        "billingtype": "",
        "total_people_count": 0,
        "contract_designcount": {},
        "posted_people": [],
    }


class Bt(BaseModel, TenantAwareModel):
    """
    Business Unit model representing hierarchical organizational structures.

    Supports multi-tenant facility management with advanced features:
    - Hierarchical relationships with parent/child business units
    - GPS coordinates and geofencing capabilities
    - Conversational onboarding AI integration
    - Comprehensive preference management
    - Performance-optimized caching strategy
    """

    uuid = models.UUIDField(default=uuid.uuid4, null=True)
    bucode = models.CharField(_("Code"), max_length=30)
    solid = models.CharField(
        max_length=30, null=True, blank=True, verbose_name="Sol ID"
    )
    siteincharge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Site Incharge",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="siteincharge",
    )
    bupreferences = models.JSONField(
        _("bupreferences"),
        null=True,
        default=bu_defaults,
        encoder=DjangoJSONEncoder,
        blank=True,
    )
    identifier = models.ForeignKey(
        "TypeAssist",
        verbose_name="Identifier",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="bu_idfs",
    )
    buname = models.CharField(_("Name"), max_length=200)
    butree = models.CharField(
        _("Bu Path"), null=True, blank=True, max_length=300, default=""
    )
    butype = models.ForeignKey(
        "TypeAssist",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="bu_butypes",
        verbose_name="Type",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="children",
        verbose_name="Belongs To",
    )
    enable = models.BooleanField(_("Enable"), default=True)
    iswarehouse = models.BooleanField(_("Warehouse"), default=False)
    gpsenable = models.BooleanField(_("GPS Enable"), default=False)
    enablesleepingguard = models.BooleanField(_("Enable SleepingGuard"), default=False)
    skipsiteaudit = models.BooleanField(_("Skip SiteAudit"), default=False)
    siincludes = ArrayField(
        models.CharField(max_length=50, blank=True),
        verbose_name=_("Site Inclides"),
        null=True,
        blank=True,
    )
    deviceevent = models.BooleanField(_("Device Event"), default=False)
    pdist = models.FloatField(
        _("Permissible Distance"), default=0.0, blank=True, null=True
    )
    gpslocation = PointField(
        _("GPS Location"), null=True, blank=True, geography=True, srid=4326
    )
    isvendor = models.BooleanField(_("Vendor"), default=False)
    isserviceprovider = models.BooleanField(_("ServiceProvider"), default=False)

    # NOC Module: City/State for geographic aggregation
    city = models.ForeignKey(
        "TypeAssist",
        verbose_name="City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bt_cities",
        help_text="City location for NOC geographic drill-down"
    )
    state = models.ForeignKey(
        "TypeAssist",
        verbose_name="State",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bt_states",
        help_text="State location for NOC geographic aggregation"
    )

    # Conversational Onboarding Fields (Phase 1 MVP)
    onboarding_context = models.JSONField(
        _("Onboarding Context"),
        default=dict,
        blank=True,
        help_text="Context data for conversational onboarding process"
    )
    setup_confidence_score = models.FloatField(
        _("Setup Confidence Score"),
        null=True,
        blank=True,
        help_text="AI confidence score for the setup recommendations"
    )

    objects = BtManager()

    class Meta(BaseModel.Meta):
        db_table = "bt"
        verbose_name = "Business Unit"
        verbose_name_plural = "Business Units"
        constraints = [
            models.UniqueConstraint(
                fields=["bucode", "parent", "identifier"],
                name="bu_bucode_parent_identifier_uk",
            )
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        return f"{self.buname} ({self.bucode})"

    def get_absolute_wizard_url(self):
        return reverse("onboarding:wiz_bu_update", kwargs={"pk": self.pk})

    def get_client_parent(self):
        """
        Get the top-level CLIENT for this business unit.

        This method traverses up the hierarchy to find the root CLIENT,
        which is essential for NOC aggregation and RBAC filtering.

        Returns:
            Bt: The CLIENT business unit, or None if not found

        Examples:
            >>> site = Bt.objects.get(identifier__tacode='SITE', pk=123)
            >>> client = site.get_client_parent()
            >>> assert client.identifier.tacode == 'CLIENT'
        """
        if self.identifier and self.identifier.tacode == 'CLIENT':
            return self
        if self.parent:
            return self.parent.get_client_parent()
        return None

    def save(self, *args, **kwargs):
        """Enhanced save with cache management and validation."""
        is_new = self.pk is None
        old_parent_id = None

        if not is_new:
            try:
                old_instance = Bt.objects.get(pk=self.pk)
                old_parent_id = old_instance.parent_id
            except Bt.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Set default relationships if needed
        from apps.core import utils
        if self.siteincharge is None:
            self.siteincharge = utils.get_or_create_none_people()
        if self.butype is None:
            self.butype = utils.get_none_typeassist()

        # Clear cache after save
        self._clear_bu_cache(old_parent_id)

    def delete(self, *args, **kwargs):
        """Enhanced delete with cache cleanup."""
        parent_id = self.parent_id
        super().delete(*args, **kwargs)
        self._clear_bu_cache(parent_id)

    def _clear_bu_cache(self, old_parent_id=None):
        """Clear BU tree cache for affected clients."""
        from django.core.cache import cache
        import logging

        logger = logging.getLogger(__name__)

        if self.parent_id:
            self._clear_cache_for_bu_tree(self.parent_id)

        if old_parent_id and old_parent_id != self.parent_id:
            self._clear_cache_for_bu_tree(old_parent_id)

        self._clear_cache_for_bu_tree(self.id)
        logger.info(f"Cache cleared for BU {self.bucode} (ID: {self.id})")

    def _clear_cache_for_bu_tree(self, bu_id):
        """Clear all cache keys related to a BU tree."""
        from django.core.cache import cache

        cache_patterns = [
            f"bulist_{bu_id}_True_True_array",
            f"bulist_{bu_id}_True_True_text",
            f"bulist_{bu_id}_True_True_jsonb",
            f"bulist_{bu_id}_True_False_array",
            f"bulist_{bu_id}_True_False_text",
            f"bulist_{bu_id}_True_False_jsonb",
            f"bulist_{bu_id}_False_True_array",
            f"bulist_{bu_id}_False_True_text",
            f"bulist_{bu_id}_False_True_jsonb",
            f"bulist_{bu_id}_False_False_array",
            f"bulist_{bu_id}_False_False_text",
            f"bulist_{bu_id}_False_False_jsonb",
            f"bulist_idnf_{bu_id}_True_True",
            f"bulist_idnf_{bu_id}_True_False",
            f"bulist_idnf_{bu_id}_False_True",
            f"bulist_idnf_{bu_id}_False_False",
        ]

        for pattern in cache_patterns:
            cache.delete(pattern)