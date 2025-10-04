"""
Site Onboarding Models for Voice-First Security Audits.

This module provides models for multimodal (voice + photo + GPS) site security
auditing with zone-centric architecture, compliance validation, and SOP generation.

Key Features:
- Zone-as-backbone architecture for all observations
- Multimodal data capture (voice, photo, GPS, OCR)
- Compliance-driven with RBI/ASIS/ISO validation
- Multilingual support with English-centric reasoning
- Coverage planning and SOP generation
- Full integration with knowledge base

Following .claude/rules.md:
- Rule #6: Model classes < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization with strategic indexes
"""

import uuid
from decimal import Decimal
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


class OnboardingSite(BaseModel, TenantAwareModel):
    """
    Master container for site security audit sessions.

    Links business unit with conversational session to manage
    complete site onboarding lifecycle.
    """

    class SiteTypeChoices(models.TextChoices):
        BANK_BRANCH = "bank_branch", _("Bank Branch")
        ATM = "atm", _("ATM")
        RETAIL_STORE = "retail_store", _("Retail Store")
        WAREHOUSE = "warehouse", _("Warehouse")
        OFFICE = "office", _("Office")
        INDUSTRIAL = "industrial", _("Industrial Facility")
        MIXED_USE = "mixed_use", _("Mixed Use")

    site_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_unit = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="onboarding_sites",
        verbose_name=_("Business Unit")
    )
    conversation_session = models.OneToOneField(
        "ConversationSession",
        on_delete=models.CASCADE,
        related_name="onboarding_site",
        verbose_name=_("Conversation Session")
    )
    site_type = models.CharField(
        _("Site Type"),
        max_length=50,
        choices=SiteTypeChoices.choices,
        default=SiteTypeChoices.OFFICE
    )
    language = models.CharField(
        _("Audit Language"),
        max_length=10,
        default="en",
        help_text=_("Primary language for audit (ISO 639-1 code)")
    )
    operating_hours_start = models.TimeField(
        _("Operating Hours Start"),
        null=True,
        blank=True
    )
    operating_hours_end = models.TimeField(
        _("Operating Hours End"),
        null=True,
        blank=True
    )
    primary_gps = PointField(
        _("Primary GPS Location"),
        null=True,
        blank=True,
        geography=True,
        help_text="Primary site coordinates"
    )
    risk_profile = models.JSONField(
        _("Risk Profile"),
        default=dict,
        blank=True,
        help_text="Risk assessment: {overall_score, critical_zones, threat_vectors}"
    )
    audit_completed_at = models.DateTimeField(
        _("Audit Completed At"),
        null=True,
        blank=True
    )
    report_generated_at = models.DateTimeField(
        _("Report Generated At"),
        null=True,
        blank=True
    )
    knowledge_base_id = models.UUIDField(
        _("Knowledge Base Document ID"),
        null=True,
        blank=True,
        help_text="Reference to ingested KB document"
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_site"
        verbose_name = "Onboarding Site"
        verbose_name_plural = "Onboarding Sites"
        indexes = [
            models.Index(fields=['business_unit', 'cdtz'], name='site_bu_created_idx'),
            models.Index(fields=['site_type', 'cdtz'], name='site_type_created_idx'),
        ]

    def __str__(self):
        return f"Site Audit: {self.business_unit.buname} ({self.site_type})"

    def get_critical_zones(self):
        """Get all zones with critical or high importance level."""
        return self.zones.filter(
            importance_level__in=['critical', 'high']
        ).select_related('site')

    def calculate_coverage_score(self) -> Decimal:
        """Calculate audit coverage completion score (0.0 to 1.0)."""
        total_zones = self.zones.count()
        if total_zones == 0:
            return Decimal('0.0')

        completed_zones = self.zones.filter(
            observations__isnull=False
        ).distinct().count()

        return Decimal(completed_zones) / Decimal(total_zones)


class OnboardingZone(BaseModel, TenantAwareModel):
    """
    Zone-centric model for site security auditing.

    Everything anchors to zones: observations, photos, assets, checkpoints.
    """

    class ZoneTypeChoices(models.TextChoices):
        GATE = "gate", _("Gate / Main Entrance")
        PERIMETER = "perimeter", _("Perimeter / Boundary")
        ENTRY_EXIT = "entry_exit", _("Entry/Exit Point")
        VAULT = "vault", _("Vault / Strong Room")
        ATM = "atm", _("ATM Location")
        CONTROL_ROOM = "control_room", _("Control Room / Security Office")
        PARKING = "parking", _("Parking Area")
        LOADING_DOCK = "loading_dock", _("Loading Dock")
        EMERGENCY_EXIT = "emergency_exit", _("Emergency Exit")
        ASSET_STORAGE = "asset_storage", _("Asset Storage Area")
        CASH_COUNTER = "cash_counter", _("Cash Counter")
        SERVER_ROOM = "server_room", _("Server Room")
        RECEPTION = "reception", _("Reception Area")
        OTHER = "other", _("Other")

    class ImportanceLevelChoices(models.TextChoices):
        CRITICAL = "critical", _("Critical")
        HIGH = "high", _("High")
        MEDIUM = "medium", _("Medium")
        LOW = "low", _("Low")

    class RiskLevelChoices(models.TextChoices):
        SEVERE = "severe", _("Severe")
        HIGH = "high", _("High")
        MODERATE = "moderate", _("Moderate")
        LOW = "low", _("Low")
        MINIMAL = "minimal", _("Minimal")

    zone_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        OnboardingSite,
        on_delete=models.CASCADE,
        related_name="zones",
        verbose_name=_("Site")
    )
    zone_type = models.CharField(
        _("Zone Type"),
        max_length=50,
        choices=ZoneTypeChoices.choices
    )
    zone_name = models.CharField(
        _("Zone Name"),
        max_length=200,
        help_text="Descriptive name for the zone"
    )
    importance_level = models.CharField(
        _("Importance Level"),
        max_length=20,
        choices=ImportanceLevelChoices.choices,
        default=ImportanceLevelChoices.MEDIUM
    )
    risk_level = models.CharField(
        _("Risk Level"),
        max_length=20,
        choices=RiskLevelChoices.choices,
        default=RiskLevelChoices.MODERATE
    )
    gps_coordinates = PointField(
        _("GPS Coordinates"),
        null=True,
        blank=True,
        geography=True
    )
    coverage_required = models.BooleanField(
        _("Coverage Required"),
        default=True,
        help_text="Whether this zone requires guard coverage"
    )
    compliance_notes = models.TextField(
        _("Compliance Notes"),
        blank=True,
        help_text="RBI/ASIS/ISO compliance requirements"
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_zone"
        verbose_name = "Onboarding Zone"
        verbose_name_plural = "Onboarding Zones"
        indexes = [
            models.Index(fields=['site', 'zone_type'], name='zone_site_type_idx'),
            models.Index(fields=['importance_level'], name='zone_importance_idx'),
            models.Index(fields=['risk_level'], name='zone_risk_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'zone_name'],
                name='unique_zone_name_per_site'
            )
        ]

    def __str__(self):
        return f"{self.zone_name} ({self.zone_type})"


class Observation(BaseModel, TenantAwareModel):
    """
    Multimodal observation capturing voice + photo + GPS.

    Stores original native language transcript, English translation,
    and enhanced structured data from domain expertise.
    """

    class SeverityChoices(models.TextChoices):
        CRITICAL = "critical", _("Critical Issue")
        HIGH = "high", _("High Priority")
        MEDIUM = "medium", _("Medium Priority")
        LOW = "low", _("Low Priority")
        INFO = "info", _("Informational")

    observation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        OnboardingSite,
        on_delete=models.CASCADE,
        related_name="observations",
        verbose_name=_("Site")
    )
    zone = models.ForeignKey(
        OnboardingZone,
        on_delete=models.CASCADE,
        related_name="observations",
        verbose_name=_("Zone"),
        null=True,
        blank=True
    )
    audio_file = models.FileField(
        _("Audio File"),
        upload_to="onboarding/audio/%Y/%m/%d/",
        null=True,
        blank=True
    )
    transcript_original = models.TextField(
        _("Original Transcript"),
        blank=True,
        help_text="Transcript in operator's native language"
    )
    transcript_english = models.TextField(
        _("English Transcript"),
        blank=True,
        help_text="Translated English version for LLM processing"
    )
    enhanced_observation = models.JSONField(
        _("Enhanced Observation"),
        default=dict,
        blank=True,
        help_text="Structured data from domain expertise: {entities, risks, actions}"
    )
    entities = models.JSONField(
        _("Detected Entities"),
        default=list,
        blank=True,
        help_text="NER entities: [{'type': 'asset', 'name': 'CCTV Camera', ...}]"
    )
    severity = models.CharField(
        _("Severity"),
        max_length=20,
        choices=SeverityChoices.choices,
        default=SeverityChoices.INFO
    )
    confidence_score = models.DecimalField(
        _("Confidence Score"),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.0'),
        help_text=_("AI confidence (0.00 to 1.00)")
    )
    gps_at_capture = PointField(
        _("GPS at Capture"),
        null=True,
        blank=True,
        geography=True
    )
    media_links = ArrayField(
        models.URLField(),
        verbose_name=_("Media Links"),
        default=list,
        blank=True,
        help_text="URLs to associated photos/audio"
    )
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="site_observations",
        verbose_name=_("Captured By")
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_observation"
        verbose_name = "Observation"
        verbose_name_plural = "Observations"
        indexes = [
            models.Index(fields=['site', 'zone', 'cdtz'], name='obs_site_zone_time_idx'),
            models.Index(fields=['severity', 'cdtz'], name='obs_severity_time_idx'),
            models.Index(fields=['confidence_score'], name='obs_confidence_idx'),
        ]

    def __str__(self):
        zone_name = self.zone.zone_name if self.zone else "Unassigned"
        return f"Observation at {zone_name} - {self.severity}"


class SitePhoto(BaseModel, TenantAwareModel):
    """
    Photo documentation with Vision API analysis.

    Stores images with AI-powered object detection, hazard identification,
    and OCR text extraction.
    """

    photo_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        OnboardingSite,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name=_("Site")
    )
    zone = models.ForeignKey(
        OnboardingZone,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name=_("Zone")
    )
    image = models.ImageField(
        _("Image"),
        upload_to="onboarding/photos/%Y/%m/%d/"
    )
    thumbnail = models.ImageField(
        _("Thumbnail"),
        upload_to="onboarding/thumbnails/%Y/%m/%d/",
        null=True,
        blank=True
    )
    gps_coordinates = PointField(
        _("GPS Coordinates"),
        null=True,
        blank=True,
        geography=True
    )
    compass_direction = models.DecimalField(
        _("Compass Direction"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Direction in degrees (0-360)")
    )
    vision_analysis = models.JSONField(
        _("Vision Analysis"),
        default=dict,
        blank=True,
        help_text="Google Vision API results"
    )
    detected_objects = ArrayField(
        models.CharField(max_length=100),
        verbose_name=_("Detected Objects"),
        default=list,
        blank=True
    )
    safety_concerns = ArrayField(
        models.CharField(max_length=200),
        verbose_name=_("Safety Concerns"),
        default=list,
        blank=True
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="site_photos",
        verbose_name=_("Uploaded By")
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_site_photo"
        verbose_name = "Site Photo"
        verbose_name_plural = "Site Photos"
        indexes = [
            models.Index(fields=['zone', 'cdtz'], name='photo_zone_time_idx'),
            models.Index(fields=['site', 'cdtz'], name='photo_site_time_idx'),
        ]

    def __str__(self):
        return f"Photo at {self.zone.zone_name}"


class Asset(BaseModel, TenantAwareModel):
    """
    Security and operational assets within zones.

    Tracks cameras, sensors, access control, alarms, and other equipment.
    """

    class AssetTypeChoices(models.TextChoices):
        CAMERA = "camera", _("CCTV Camera")
        DVR_NVR = "dvr_nvr", _("DVR/NVR")
        LIGHTING = "lighting", _("Security Lighting")
        METAL_DETECTOR = "metal_detector", _("Metal Detector")
        XRAY_MACHINE = "xray_machine", _("X-Ray Machine")
        ALARM_SYSTEM = "alarm_system", _("Alarm System")
        ACCESS_READER = "access_reader", _("Access Control Reader")
        BIOMETRIC = "biometric", _("Biometric Device")
        INTERCOM = "intercom", _("Intercom System")
        BARRIER_GATE = "barrier_gate", _("Barrier Gate")
        SAFE_VAULT = "safe_vault", _("Safe/Vault")
        FIRE_EXTINGUISHER = "fire_extinguisher", _("Fire Extinguisher")
        FIRE_ALARM = "fire_alarm", _("Fire Alarm")
        EMERGENCY_LIGHT = "emergency_light", _("Emergency Lighting")
        OTHER = "other", _("Other Asset")

    class StatusChoices(models.TextChoices):
        OPERATIONAL = "operational", _("Operational")
        NEEDS_REPAIR = "needs_repair", _("Needs Repair")
        NOT_INSTALLED = "not_installed", _("Not Installed")
        PLANNED = "planned", _("Planned")
        DECOMMISSIONED = "decommissioned", _("Decommissioned")

    asset_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        OnboardingZone,
        on_delete=models.CASCADE,
        related_name="assets",
        verbose_name=_("Zone")
    )
    asset_type = models.CharField(
        _("Asset Type"),
        max_length=50,
        choices=AssetTypeChoices.choices
    )
    asset_name = models.CharField(
        _("Asset Name"),
        max_length=200
    )
    status = models.CharField(
        _("Status"),
        max_length=30,
        choices=StatusChoices.choices,
        default=StatusChoices.OPERATIONAL
    )
    specifications = models.JSONField(
        _("Specifications"),
        default=dict,
        blank=True,
        help_text="Technical specs: {model, serial, resolution, coverage_area}"
    )
    linked_photos = ArrayField(
        models.UUIDField(),
        verbose_name=_("Linked Photos"),
        default=list,
        blank=True,
        help_text="Photo IDs documenting this asset"
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_asset"
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        indexes = [
            models.Index(fields=['zone', 'asset_type'], name='asset_zone_type_idx'),
            models.Index(fields=['status'], name='asset_status_idx'),
        ]

    def __str__(self):
        return f"{self.asset_name} ({self.asset_type})"


class Checkpoint(BaseModel, TenantAwareModel):
    """
    Verification checkpoints for patrol and compliance validation.
    """

    checkpoint_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        OnboardingZone,
        on_delete=models.CASCADE,
        related_name="checkpoints",
        verbose_name=_("Zone")
    )
    checkpoint_name = models.CharField(
        _("Checkpoint Name"),
        max_length=200
    )
    questions = models.JSONField(
        _("Questions"),
        default=list,
        help_text="Checklist questions: [{question, required, type}]"
    )
    frequency = models.CharField(
        _("Check Frequency"),
        max_length=50,
        help_text="hourly/shift/daily/weekly"
    )
    severity = models.CharField(
        _("Severity if Missed"),
        max_length=20,
        default="medium"
    )
    template_id = models.UUIDField(
        _("Template ID"),
        null=True,
        blank=True,
        help_text="Link to compliance template"
    )
    completed = models.BooleanField(
        _("Completed"),
        default=False
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_checkpoint"
        verbose_name = "Checkpoint"
        verbose_name_plural = "Checkpoints"
        indexes = [
            models.Index(fields=['zone', 'completed'], name='checkpoint_zone_complete_idx'),
        ]

    def __str__(self):
        return f"Checkpoint: {self.checkpoint_name}"


class MeterPoint(BaseModel, TenantAwareModel):
    """
    Meter and register reading points requiring OCR extraction.
    """

    class MeterTypeChoices(models.TextChoices):
        ELECTRICITY = "electricity", _("Electricity Meter")
        WATER = "water", _("Water Meter")
        DIESEL = "diesel", _("Diesel/Fuel Meter")
        FIRE_PRESSURE = "fire_pressure", _("Fire Hydrant Pressure")
        LOGBOOK = "logbook", _("Manual Logbook")
        TEMPERATURE = "temperature", _("Temperature Gauge")
        GENERATOR_HOURS = "generator_hours", _("Generator Hour Meter")
        UPS_STATUS = "ups_status", _("UPS Status Panel")
        OTHER = "other", _("Other Meter")

    meter_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        OnboardingZone,
        on_delete=models.CASCADE,
        related_name="meter_points",
        verbose_name=_("Zone")
    )
    meter_type = models.CharField(
        _("Meter Type"),
        max_length=50,
        choices=MeterTypeChoices.choices
    )
    meter_name = models.CharField(
        _("Meter Name"),
        max_length=200
    )
    reading_frequency = models.CharField(
        _("Reading Frequency"),
        max_length=50,
        help_text="daily/weekly/monthly"
    )
    reading_template = models.JSONField(
        _("Reading Template"),
        default=dict,
        help_text="Expected format: {unit, range, validation_rules}"
    )
    requires_photo_ocr = models.BooleanField(
        _("Requires Photo OCR"),
        default=True
    )
    photo_example = models.ImageField(
        _("Example Photo"),
        upload_to="onboarding/meter_examples/",
        null=True,
        blank=True
    )
    sop_instructions = models.TextField(
        _("SOP Instructions"),
        blank=True,
        help_text="How to read and record this meter"
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_meter_point"
        verbose_name = "Meter Point"
        verbose_name_plural = "Meter Points"
        indexes = [
            models.Index(fields=['zone', 'meter_type'], name='meter_zone_type_idx'),
        ]

    def __str__(self):
        return f"{self.meter_name} ({self.meter_type})"


class SOP(BaseModel, TenantAwareModel):
    """
    Standard Operating Procedure with multilingual support.

    Generated from observations and domain expertise, with compliance citations.
    """

    sop_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        OnboardingSite,
        on_delete=models.CASCADE,
        related_name="sops",
        verbose_name=_("Site")
    )
    zone = models.ForeignKey(
        OnboardingZone,
        on_delete=models.CASCADE,
        related_name="sops",
        verbose_name=_("Zone"),
        null=True,
        blank=True
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="sops",
        verbose_name=_("Asset"),
        null=True,
        blank=True,
        help_text="Asset-specific SOP"
    )
    sop_title = models.CharField(
        _("SOP Title"),
        max_length=300
    )
    purpose = models.TextField(
        _("Purpose"),
        help_text="Why this SOP is needed"
    )
    steps = models.JSONField(
        _("Steps"),
        default=list,
        help_text="Ordered steps: [{step_number, description, responsible_role}]"
    )
    staffing_required = models.JSONField(
        _("Staffing Required"),
        default=dict,
        help_text="Non-cost staffing: {roles, count, schedule} - no pricing"
    )
    compliance_references = ArrayField(
        models.CharField(max_length=200),
        verbose_name=_("Compliance References"),
        default=list,
        blank=True,
        help_text="RBI/ASIS/ISO citations: ['RBI Master Direction 2021', ...]"
    )
    frequency = models.CharField(
        _("Frequency"),
        max_length=50,
        help_text="hourly/shift/daily/weekly/monthly/as_needed"
    )
    translated_texts = models.JSONField(
        _("Translated Texts"),
        default=dict,
        blank=True,
        help_text="Translations: {lang_code: {title, purpose, steps}}"
    )
    escalation_triggers = models.JSONField(
        _("Escalation Triggers"),
        default=list,
        blank=True,
        help_text="Conditions requiring escalation"
    )
    llm_generated = models.BooleanField(
        _("LLM Generated"),
        default=True,
        help_text="Whether this SOP was AI-generated"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_sops",
        verbose_name=_("Reviewed By")
    )
    approved_at = models.DateTimeField(
        _("Approved At"),
        null=True,
        blank=True
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_sop"
        verbose_name = "Standard Operating Procedure"
        verbose_name_plural = "Standard Operating Procedures"
        indexes = [
            models.Index(fields=['site', 'zone'], name='sop_site_zone_idx'),
            models.Index(fields=['asset'], name='sop_asset_idx'),
            models.Index(fields=['llm_generated', 'approved_at'], name='sop_gen_approved_idx'),
        ]

    def __str__(self):
        return self.sop_title


class CoveragePlan(BaseModel, TenantAwareModel):
    """
    Guard coverage and shift assignment plan.

    Generated from zone requirements and risk windows - no cost calculations.
    """

    plan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.OneToOneField(
        OnboardingSite,
        on_delete=models.CASCADE,
        related_name="coverage_plan",
        verbose_name=_("Site")
    )
    guard_posts = models.JSONField(
        _("Guard Posts"),
        default=list,
        help_text="Posts: [{post_id, zone, position, duties, risk_level}]"
    )
    shift_assignments = models.JSONField(
        _("Shift Assignments"),
        default=list,
        help_text="Shifts: [{shift_name, start_time, end_time, posts_covered, staffing}]"
    )
    patrol_routes = models.JSONField(
        _("Patrol Routes"),
        default=list,
        blank=True,
        help_text="Routes: [{route_id, zones, frequency, checkpoints}]"
    )
    risk_windows = models.JSONField(
        _("Risk Windows"),
        default=list,
        blank=True,
        help_text="High-risk time periods: [{start, end, zones, mitigation}]"
    )
    compliance_notes = models.TextField(
        _("Compliance Notes"),
        blank=True,
        help_text="Regulatory compliance considerations"
    )
    generated_by = models.CharField(
        _("Generated By"),
        max_length=50,
        default="ai",
        help_text="ai/manual/hybrid"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_coverage_plans",
        verbose_name=_("Approved By")
    )
    approved_at = models.DateTimeField(
        _("Approved At"),
        null=True,
        blank=True
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_coverage_plan"
        verbose_name = "Coverage Plan"
        verbose_name_plural = "Coverage Plans"
        indexes = [
            models.Index(fields=['site', 'approved_at'], name='coverage_site_approved_idx'),
        ]

    def __str__(self):
        return f"Coverage Plan for {self.site.business_unit.buname}"