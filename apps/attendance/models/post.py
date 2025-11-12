"""
Post Model - Explicit Duty Station Management

Represents specific duty stations within a site where guards are posted.
Replaces implicit post tracking with explicit, auditable post assignments.

Industry Standard: Each site has multiple posts (e.g., Main Gate, Lobby, Parking)
with specific requirements (certifications, shift coverage, post orders).

Author: Claude Code
Created: 2025-11-03
Phase: 2 - Post Assignment Model
"""

from django.db import models
from django.db.models import Q
from django.contrib.gis.db.models import PointField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.models import BaseModel, TenantAwareModel
from apps.tenants.managers import TenantAwareManager

import logging

logger = logging.getLogger(__name__)


class Post(BaseModel, TenantAwareModel):
    """
    Represents a specific duty station within a site.

    A post is a physical location where a guard is stationed during their shift.
    Examples: "Main Gate", "Lobby Reception", "Parking Level 2", "Control Room"

    Industry Context:
    - Large sites may have 10-20+ posts
    - Each post has specific requirements (armed/unarmed, certifications)
    - Posts have digital post orders that guards must acknowledge
    - Posts are mapped to shifts (different guards cover same post on different shifts)

    Relationships:
    - Site (Bt): Which site this post belongs to
    - Zone (OnboardingZone): Optional link to site zone definition
    - Shift (Shift): Which shift operates this post
    - Geofence (Geofence): Geographic boundary for GPS validation
    """

    class PostType(models.TextChoices):
        """Post types aligned with OnboardingZone.ZoneTypeChoices"""
        GATE = 'GATE', _('Gate')
        PERIMETER = 'PERIMETER', _('Perimeter')
        ENTRY_EXIT = 'ENTRY_EXIT', _('Entry/Exit Point')
        VAULT = 'VAULT', _('Vault')
        ATM = 'ATM', _('ATM')
        CONTROL_ROOM = 'CONTROL_ROOM', _('Control Room')
        PARKING = 'PARKING', _('Parking Area')
        LOADING_DOCK = 'LOADING_DOCK', _('Loading Dock')
        EMERGENCY_EXIT = 'EMERGENCY_EXIT', _('Emergency Exit')
        ASSET_STORAGE = 'ASSET_STORAGE', _('Asset Storage')
        CASH_COUNTER = 'CASH_COUNTER', _('Cash Counter')
        SERVER_ROOM = 'SERVER_ROOM', _('Server Room')
        RECEPTION = 'RECEPTION', _('Reception')
        LOBBY = 'LOBBY', _('Lobby')
        ROOFTOP = 'ROOFTOP', _('Rooftop')
        OTHER = 'OTHER', _('Other')

    class RiskLevel(models.TextChoices):
        """Risk level for security prioritization"""
        CRITICAL = 'CRITICAL', _('Critical')
        HIGH = 'HIGH', _('High')
        MEDIUM = 'MEDIUM', _('Medium')
        LOW = 'LOW', _('Low')
        MINIMAL = 'MINIMAL', _('Minimal')

    # ========== Core Identification ==========

    post_code = models.CharField(
        max_length=20,
        db_index=True,
        help_text=_("Unique post code (e.g., 'POST-001', 'GATE-A')")
    )

    post_name = models.CharField(
        max_length=100,
        help_text=_("Descriptive post name (e.g., 'Main Gate - Morning Shift')")
    )

    post_type = models.CharField(
        max_length=20,
        choices=PostType.choices,
        default=PostType.OTHER,
        db_index=True,
        help_text=_("Type of duty station")
    )

    # ========== Relationships ==========

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='posts',
        db_index=True,
        help_text=_("Site where this post is located")
    )

    zone = models.ForeignKey(
        'site_onboarding.OnboardingZone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        help_text=_("Optional link to site zone definition")
    )

    shift = models.ForeignKey(
        'client_onboarding.Shift',
        on_delete=models.CASCADE,
        related_name='posts',
        db_index=True,
        help_text=_("Shift that operates this post")
    )

    geofence = models.ForeignKey(
        'attendance.Geofence',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        help_text=_("Geographic boundary for GPS validation at this post")
    )

    # ========== Staffing Requirements ==========

    required_guard_count = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text=_("Number of guards required at this post simultaneously")
    )

    armed_required = models.BooleanField(
        default=False,
        help_text=_("Whether guards at this post must be armed")
    )

    required_certifications = models.ManyToManyField(
        'core_onboarding.TypeAssist',
        blank=True,
        related_name='required_for_posts',
        limit_choices_to={'tatype__tacode': 'CERTIFICATION'},
        help_text=_("Certifications required to work this post")
    )

    # ========== Location & Geofencing ==========

    gps_coordinates = PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text=_("GPS coordinates of post location (center point)")
    )

    geofence_radius = models.IntegerField(
        default=50,
        validators=[MinValueValidator(10), MaxValueValidator(500)],
        help_text=_("Radius in meters for circular geofence (if no explicit geofence)")
    )

    floor_level = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("Floor level (e.g., 'Ground Floor', 'Level 2', 'Basement')")
    )

    building_section = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Building section (e.g., 'Tower A', 'North Wing')")
    )

    # ========== Post Orders & Instructions ==========

    post_orders = models.TextField(
        blank=True,
        help_text=_("Digital post orders - detailed instructions for guards at this post")
    )

    post_orders_version = models.IntegerField(
        default=1,
        help_text=_("Version number for post orders tracking")
    )

    post_orders_last_updated = models.DateTimeField(
        auto_now=True,
        help_text=_("When post orders were last modified")
    )

    duties_summary = models.TextField(
        blank=True,
        help_text=_("Brief summary of duties (bullet points)")
    )

    emergency_procedures = models.TextField(
        blank=True,
        help_text=_("Emergency procedures for this post")
    )

    reporting_instructions = models.TextField(
        blank=True,
        help_text=_("How and when to report from this post")
    )

    # ========== Risk & Security ==========

    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.MEDIUM,
        db_index=True,
        help_text=_("Security risk level for this post")
    )

    high_value_assets = models.BooleanField(
        default=False,
        help_text=_("Whether this post protects high-value assets")
    )

    public_access = models.BooleanField(
        default=False,
        help_text=_("Whether this post has public access")
    )

    # ========== Operational Status ==========

    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this post is currently active")
    )

    coverage_required = models.BooleanField(
        default=True,
        help_text=_("Whether this post must be covered at all times")
    )

    temporary = models.BooleanField(
        default=False,
        help_text=_("Whether this is a temporary post (event-based)")
    )

    temporary_start_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("Start date for temporary posts")
    )

    temporary_end_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("End date for temporary posts")
    )

    # ========== Metadata & Extensibility ==========

    post_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Extensible metadata for post-specific data "
            "(equipment, access codes, special instructions)"
        )
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Additional notes about this post")
    )

    # ========== Audit Fields ==========

    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts_created',
        help_text=_("User who created this post")
    )

    modified_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts_modified',
        help_text=_("User who last modified this post")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_post'
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')
        unique_together = [
            ('site', 'post_code', 'tenant'),
            ('site', 'shift', 'post_name', 'tenant'),
        ]
        indexes = [
            # Query optimization indexes
            models.Index(fields=['tenant', 'site', 'shift', 'active'], name='post_active_lookup_idx'),
            models.Index(fields=['tenant', 'site', 'post_type'], name='post_type_idx'),
            models.Index(fields=['tenant', 'active', 'coverage_required'], name='post_coverage_idx'),
            models.Index(fields=['tenant', 'risk_level'], name='post_risk_idx'),
        ]
        ordering = ['site', 'shift', 'post_code']

    def __str__(self):
        return f"{self.post_code} - {self.post_name} ({self.site.buname})"

    def save(self, *args, **kwargs):
        """Override save to auto-increment post_orders_version on content change"""
        if self.pk:
            # Check if post_orders changed
            old_instance = Post.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.post_orders != self.post_orders:
                self.post_orders_version += 1
        super().save(*args, **kwargs)

    def get_required_certifications_list(self):
        """Get list of required certification names"""
        return list(self.required_certifications.values_list('taname', flat=True))

    def is_guard_qualified(self, guard):
        """
        Check if a guard meets all requirements for this post

        Args:
            guard: People instance

        Returns:
            tuple: (qualified: bool, missing_requirements: list)
        """
        from apps.peoples.models import People
        from apps.core_onboarding.models import TypeAssist

        def _normalize_collection(raw_value):
            ids, codes = set(), set()
            if not raw_value:
                return ids, codes

            iterable = raw_value
            if isinstance(raw_value, str):
                iterable = [entry.strip() for entry in raw_value.split(',') if entry.strip()]
            elif isinstance(raw_value, dict):
                # When stored as {"code": "..."} or {"items": [...]}
                possible = []
                if 'items' in raw_value and isinstance(raw_value['items'], (list, tuple, set)):
                    possible = raw_value['items']
                else:
                    possible = raw_value.values()
                iterable = possible

            if isinstance(iterable, (list, tuple, set)):
                for entry in iterable:
                    candidate = entry
                    if isinstance(entry, dict):
                        candidate = entry.get('code') or entry.get('tacode') or entry.get('id')

                    if candidate is None:
                        continue

                    if isinstance(candidate, int):
                        ids.add(candidate)
                        continue

                    candidate_str = str(candidate).strip()
                    if not candidate_str:
                        continue
                    try:
                        ids.add(int(candidate_str))
                        continue
                    except (TypeError, ValueError):
                        codes.add(candidate_str)
            return ids, codes

        def _extract_certifications_from_metadata(metadata_source):
            cert_ids, cert_codes = set(), set()
            if not isinstance(metadata_source, dict):
                return cert_ids, cert_codes

            metadata_keys = (
                'certifications',
                'certifications_completed',
                'certification_codes',
                'certifications_codes',
            )

            for key in metadata_keys:
                ids, codes = _normalize_collection(metadata_source.get(key))
                cert_ids.update(ids)
                cert_codes.update(codes)
            return cert_ids, cert_codes

        def _has_armed_authorization(person):
            # Prefer explicit metadata flags
            flag_keys = ('armed_guard_certified', 'armed_guard_ready', 'armed_training_complete')
            for source in (person.people_extras or {}, person.capabilities or {}):
                if not isinstance(source, dict):
                    continue
                if any(source.get(flag) for flag in flag_keys):
                    return True

            # Fall back to certified skills mentioning armed capability
            return person.skills.filter(
                certified=True,
                category__tatype__tacode='CERTIFICATION'
            ).filter(
                Q(category__taname__icontains='armed') | Q(category__tacode__icontains='ARMED')
            ).exists()

        missing_requirements: list[str] = []

        if guard is None:
            return (False, ['Guard not provided'])

        guard_instance = guard
        if not isinstance(guard_instance, People):
            guard_instance = People.objects.filter(pk=guard).first()
            if guard_instance is None:
                return (False, ['Guard not found'])

        required_certifications = list(self.required_certifications.all())

        guard_cert_ids = set(
            guard_instance.skills.filter(
                certified=True,
                category__tatype__tacode='CERTIFICATION'
            ).values_list('category_id', flat=True)
        )

        # Include IDs/codes stored in people_extras or capabilities JSON blobs
        extra_ids = set()
        extra_codes = set()
        metadata_sources = (guard_instance.people_extras or {}, guard_instance.capabilities or {})
        for metadata in metadata_sources:
            ids, codes = _extract_certifications_from_metadata(metadata)
            extra_ids.update(ids)
            extra_codes.update(codes)

        guard_cert_ids.update(extra_ids)
        if extra_codes:
            extra_lookup_ids = TypeAssist.objects.filter(
                tatype__tacode='CERTIFICATION',
                tacode__in=list(extra_codes)
            ).values_list('id', flat=True)
            guard_cert_ids.update(extra_lookup_ids)

        for cert in required_certifications:
            if cert.id not in guard_cert_ids:
                missing_requirements.append(cert.taname or cert.tacode or f"Certification {cert.id}")

        if self.armed_required and not _has_armed_authorization(guard_instance):
            missing_requirements.append(str(_('Armed guard certification')))

        return (len(missing_requirements) == 0, missing_requirements)

    def get_current_assignments(self, date=None):
        """
        Get current post assignments for this post

        Args:
            date: Date to check (defaults to today)

        Returns:
            QuerySet of PostAssignment
        """
        from datetime import date as date_module
        from apps.attendance.models.post_assignment import PostAssignment

        if date is None:
            date = date_module.today()

        return PostAssignment.objects.filter(
            post=self,
            assignment_date=date,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).select_related('worker', 'shift')

    def is_coverage_met(self, date=None):
        """
        Check if coverage requirement is met for this post

        Args:
            date: Date to check (defaults to today)

        Returns:
            tuple: (is_met: bool, assigned_count: int, required_count: int)
        """
        if not self.coverage_required:
            return (True, 0, 0)

        current_assignments = self.get_current_assignments(date)
        assigned_count = current_assignments.count()

        return (
            assigned_count >= self.required_guard_count,
            assigned_count,
            self.required_guard_count
        )

    def get_post_orders_dict(self):
        """Get structured post orders as dictionary"""
        return {
            'post_code': self.post_code,
            'post_name': self.post_name,
            'version': self.post_orders_version,
            'last_updated': self.post_orders_last_updated.isoformat() if self.post_orders_last_updated else None,
            'orders': self.post_orders,
            'duties': self.duties_summary,
            'emergency_procedures': self.emergency_procedures,
            'reporting_instructions': self.reporting_instructions,
        }
    objects = TenantAwareManager()
