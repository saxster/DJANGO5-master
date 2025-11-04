from django.db import models
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from django.contrib.gis.db.models import PointField
from django.utils.translation import gettext_lazy as _
import uuid
from django.core.serializers.json import DjangoJSONEncoder
from apps.activity.managers.asset_manager import AssetManager, AssetLogManager
from django.conf import settings
from apps.ontology import ontology


def asset_json():
    return {
        "service": "",
        "ismeter": False,
        "meter": "",
        "bill_val": 0.0,
        "supplier": "",
        "msn": "",
        "bill_date": "",
        "purchase_date": "",
        "model": "",
        "inst_date": "",  # installation date
        "sfdate": "",
        "stdate": "",
        "yom": "",  # year of Mfg
        "tempcode": "",
        "po_number": "",
        "invoice_no": "",
        "invoice_date": "",
        "far_asset_id": "",
        "multifactor": 1,
        "is_nonengg_asset": False,
    }


@ontology(
    domain="operations",
    concept="Asset Management & Tracking",
    purpose=(
        "Core asset entity for facility management, tracking physical assets (equipment, machinery, "
        "checkpoints) across multi-tenant sites with lifecycle management, maintenance tracking, and "
        "parent-child hierarchy. Supports GPS-based location tracking, criticality classification, "
        "and running status state machine (WORKING, MAINTENANCE, STANDBY, SCRAPPED)."
    ),
    criticality="high",
    lifecycle_states=[
        "WORKING - Asset operational and in use",
        "MAINTENANCE - Under repair or scheduled maintenance",
        "STANDBY - Available but not actively used",
        "SCRAPPED - End of life, decommissioned"
    ],
    business_rules=[
        "Asset codes must be unique per tenant/client/site combination",
        "Parent-child hierarchy: parent=NULL for standalone assets, parent=Asset for sub-components",
        "Critical assets (iscritical=True) require priority maintenance workflows",
        "GPS location tracking via PostGIS Point field (WGS84 SRID 4326)",
        "Asset type hierarchy: type → category → subcategory → brand",
        "JSONField asset_json stores extended metadata (meter readings, invoices, purchase data)",
        "Soft delete via enable=False (preserves history for auditing)",
        "Multi-factor support for meter readings (multifactor in asset_json)",
    ],
    relationships=[
        "parent: Self-referential FK for asset hierarchy (e.g., building → floors → rooms)",
        "type/category/subcategory/brand: FK to onboarding.TypeAssist (taxonomy)",
        "client: FK to onboarding.Bt (business tenant - contract holder)",
        "bu: FK to onboarding.Bt (site/business unit - physical location)",
        "location: FK to activity.Location (geofence/zone within site)",
        "servprov: FK to onboarding.Bt (service provider for maintenance)",
        "Related: AssetLog (audit trail), Job (maintenance schedules), Wom (work orders)",
        "Tenant isolation: All queries filtered by TenantAwareModel.tenant field"
    ],
    depends_on=[
        "apps.peoples.models.BaseModel (audit fields: cdby, cdon, mdby, mdon)",
        "apps.tenants.models.TenantAwareModel (multi-tenant isolation)",
        "apps.activity.managers.asset_manager.AssetManager (optimized queries)",
        "apps.core_onboarding.models.TypeAssist (asset taxonomy)",
        "apps.client_onboarding.models.Bt (clients, sites, service providers)",
        "apps.activity.models.Location (zone/location within site)",
        "django.contrib.gis.db.models.PointField (GPS tracking)",
    ],
    used_by=[
        "apps.activity.services.asset_service.AssetManagementService (CRUD operations)",
        "apps.activity.views.asset (Django admin and web CRUD)",
        "apps.scheduler.models.Job (PPM schedules tied to assets)",
        "apps.work_order_management.models.Wom (work orders for asset maintenance)",
        "apps.inventory.models (spare parts linked to assets)",
        "Mobile apps: Asset QR code scanning, meter reading submission",
        "Reports: Asset utilization, maintenance history, depreciation",
    ],
    tags=["asset-management", "gis", "multi-tenant", "lifecycle", "maintenance", "hierarchy", "critical-path"],
    security_notes=(
        "Multi-tenant security:\n"
        "1. TenantAwareModel ensures all queries filtered by tenant field\n"
        "2. Unique constraint includes tenant to prevent cross-tenant conflicts\n"
        "3. Client/BU FKs provide secondary access control layer\n"
        "4. GPS data (PointField) requires spatial query permissions\n"
        "5. Admin visibility controlled via user's assigned sites (bu field)\n"
        "\nData integrity:\n"
        "6. RESTRICT on_delete prevents orphaned references\n"
        "7. JSONField asset_json validated before save (no raw SQL injection)\n"
        "8. Parent self-referential FK prevents deletion of assets with children\n"
        "9. Critical assets require explicit acknowledgment before status changes"
    ),
    performance_notes=(
        "Database optimizations:\n"
        "- Composite indexes: (tenant, cdtz), (tenant, identifier), (tenant, enable)\n"
        "- AssetManager provides select_related/prefetch_related helpers\n"
        "- PostGIS spatial index on gpslocation for proximity queries\n"
        "- UUID field indexed for mobile sync operations\n"
        "\nQuery patterns:\n"
        "- Asset.objects.with_full_details() → select_related(type, category, client, bu, location, parent)\n"
        "- Asset.objects.critical_assets() → filter(iscritical=True, enable=True)\n"
        "- Geospatial: Asset.objects.filter(gpslocation__dwithin=(point, Distance(km=5)))\n"
        "\nScaling:\n"
        "- Large sites (10k+ assets): Use pagination, avoid nested queries\n"
        "- JSON field reads cached at application layer (Redis)\n"
        "- Parent hierarchy limited to 3 levels (validated in AssetManager)"
    ),
    architecture_notes=(
        "Design patterns:\n"
        "- Polymorphism via 'identifier' field: ASSET, CHECKPOINT, NEA (Non-Engineering Asset)\n"
        "- State machine via 'runningstatus': Valid transitions enforced in AssetManagementService\n"
        "- Audit trail: AssetLog model captures all status changes with GPS, user, timestamp\n"
        "- Hierarchical data: Parent-child via self-referential FK (closure table alternative considered)\n"
        "\nMigration history:\n"
        "- Originally monolithic Asset model (2019)\n"
        "- Refactored to separate AssetLog for audit trail (2023)\n"
        "- Added PostGIS gpslocation field (2024)\n"
        "- Migrated metadata from CharField to JSONField asset_json (2024)\n"
        "\nFuture considerations:\n"
        "- Asset depreciation calculations (add depreciation_rate, salvage_value)\n"
        "- Integration with IoT sensors (MQTT asset telemetry)\n"
        "- Predictive maintenance ML models (failure prediction based on AssetLog patterns)"
    ),
    examples=[
        {
            "description": "Create critical HVAC asset with GPS location",
            "code": """
asset = Asset.objects.create(
    assetcode='HVAC-001',
    assetname='Main Chiller Unit',
    identifier=Asset.Identifier.ASSET,
    iscritical=True,
    runningstatus=Asset.RunningStatus.WORKING,
    gpslocation=Point(77.5946, 12.9716, srid=4326),  # Bangalore coords
    type=TypeAssist.objects.get(taname='HVAC'),
    category=TypeAssist.objects.get(taname='Cooling'),
    capacity=500.0,  # 500 TR
    client=client_bt,
    bu=site_bt,
    location=location_obj,
    tenant=tenant_obj,
    asset_json={
        'model': 'Carrier 30XA-0504',
        'yom': '2020',
        'purchase_date': '2020-06-15',
        'supplier': 'Carrier India',
        'invoice_no': 'INV-2020-001',
        'multifactor': 1,
        'is_nonengg_asset': False
    }
)
"""
        },
        {
            "description": "Query critical assets needing maintenance",
            "code": """
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone

# Critical assets in MAINTENANCE or overdue for maintenance
critical_maintenance = Asset.objects.filter(
    iscritical=True,
    enable=True
).filter(
    Q(runningstatus=Asset.RunningStatus.MAINTENANCE) |
    Q(
        jobs__jobneed__expdt__lt=timezone.now() - timedelta(days=7),
        jobs__jobneed__jobstatus='PENDING'
    )
).select_related('type', 'category', 'client', 'bu').distinct()
"""
        },
        {
            "description": "Hierarchy: Building with floor checkpoints",
            "code": """
# Parent building asset
building = Asset.objects.create(
    assetcode='BLD-A',
    assetname='Building A',
    identifier=Asset.Identifier.ASSET,
    parent=None,
    tenant=tenant,
    client=client,
    bu=site
)

# Child floor checkpoints
for floor in ['1', '2', '3']:
    Asset.objects.create(
        assetcode=f'BLD-A-F{floor}',
        assetname=f'Building A Floor {floor} Checkpoint',
        identifier=Asset.Identifier.CHECKPOINT,
        parent=building,
        tenant=tenant,
        client=client,
        bu=site
    )
"""
        }
    ]
)
class Asset(BaseModel, TenantAwareModel):
    class Identifier(models.TextChoices):
        NONE = ("NONE", "None")
        ASSET = ("ASSET", "Asset")
        CHECKPOINT = ("CHECKPOINT", "Checkpoint")
        NEA = ("NEA", "Non Engineering Asset")

    class RunningStatus(models.TextChoices):
        MAINTENANCE = ("MAINTENANCE", "Maintenance")
        STANDBY = ("STANDBY", "Standby")
        WORKING = ("WORKING", "Working")
        SCRAPPED = ("SCRAPPED", "Scrapped")

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    assetcode = models.CharField(_("Asset Code"), max_length=50)
    assetname = models.CharField(_("Asset Name"), max_length=250)
    enable = models.BooleanField(_("Enable"), default=True)
    iscritical = models.BooleanField(_("Critical"))
    gpslocation = PointField(
        _("GPS Location"), null=True, geography=True, srid=4326, blank=True
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Belongs to"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    identifier = models.CharField(
        _("Asset Identifier"),
        choices=Identifier.choices,
        max_length=55,
        default=Identifier.NONE.value,
    )
    runningstatus = models.CharField(
        _("Running Status"), choices=RunningStatus.choices, max_length=55, null=True
    )
    type = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Type"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="asset_types",
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="asset_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="asset_bus",
    )
    category = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Category"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="asset_categories",
    )
    subcategory = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Sub Category"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="asset_subcategories",
    )
    brand = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Brand"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="asset_brands",
    )
    unit = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Unit"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="asset_units",
    )
    capacity = models.DecimalField(
        _("Capacity"), default=0.0, max_digits=18, decimal_places=2
    )
    servprov = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        related_name="asset_serv_providers",
    )
    location = models.ForeignKey(
        "activity.Location",
        verbose_name=_("Location"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    asset_json = models.JSONField(
        encoder=DjangoJSONEncoder, blank=True, null=True, default=asset_json
    )

    objects = AssetManager()

    class Meta(BaseModel.Meta):
        db_table = "asset"
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "assetcode", "bu", "client"], name="tenant_assetcode_client_uk"
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'cdtz'], name='asset_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'identifier'], name='asset_tenant_identifier_idx'),
            models.Index(fields=['tenant', 'enable'], name='asset_tenant_enable_idx'),
        ]

    def __str__(self):
        return f"{self.assetname} ({self.assetcode})"


class AssetLog(BaseModel, TenantAwareModel):
    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    oldstatus = models.CharField(_("Old Status"), max_length=50, null=True)
    newstatus = models.CharField(_("New Status"), max_length=50)
    asset = models.ForeignKey(
        "activity.Asset", verbose_name=_("Asset"), on_delete=models.RESTRICT
    )
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("People"),
        on_delete=models.RESTRICT,
        null=True,
    )
    bu = models.ForeignKey(
        "onboarding.Bt", verbose_name=_("Bu"), on_delete=models.RESTRICT, null=True
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.CASCADE,
        related_name="assetlog_client",
        null=True,
    )
    cdtz = models.DateTimeField(_("Created On"), null=True)
    gpslocation = PointField(
        _("GPS Location"), null=True, geography=True, srid=4326, blank=True
    )
    ctzoffset = models.IntegerField(_("TimeZone"), default=-1)

    objects = AssetLogManager()

    class Meta(BaseModel.Meta):
        db_table = "assetlog"
        verbose_name = "Asset Log"
        verbose_name_plural = "Asset Logs"
        indexes = [
            models.Index(fields=['tenant', 'asset'], name='assetlog_tenant_asset_idx'),
            models.Index(fields=['tenant', 'cdtz'], name='assetlog_tenant_cdtz_idx'),
        ]

    def __str__(self):
        return f"{self.oldstatus} - {self.newstatus}"
