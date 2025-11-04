"""
Approved Location Model

Defines secure locations for biometric enrollment operations.
Part of Sprint 1: Voice Enrollment Security implementation.

Security Zones:
- Corporate offices (high trust)
- Client sites (medium trust)
- Approved remote locations (low trust, requires additional verification)

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes

Created: 2025-10-11
"""

import logging
from typing import Dict, Any, Optional
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.client_onboarding.models import Bt

logger = logging.getLogger(__name__)


class ApprovedLocation(TenantAwareModel):
    """
    Approved locations for sensitive biometric operations.

    Defines geographical zones where voice enrollment is permitted,
    with varying trust levels based on location type.
    """

    LOCATION_TYPES = [
        ('CORPORATE_OFFICE', 'Corporate Office'),
        ('CLIENT_SITE', 'Client Site'),
        ('BRANCH_OFFICE', 'Branch Office'),
        ('REMOTE_APPROVED', 'Approved Remote Location'),
        ('TRAINING_CENTER', 'Training Center'),
    ]

    TRUST_LEVELS = [
        ('HIGH', 'High Trust'),
        ('MEDIUM', 'Medium Trust'),
        ('LOW', 'Low Trust'),
    ]

    # Primary identification
    location_id = models.AutoField(
        primary_key=True,
        help_text="Unique location identifier"
    )

    location_name = models.CharField(
        max_length=255,
        help_text="Location name (e.g., 'Mumbai Corporate Office')"
    )

    location_type = models.CharField(
        max_length=50,
        choices=LOCATION_TYPES,
        help_text="Type of location"
    )

    # Geographic data
    site = models.ForeignKey(
        Bt,
        on_delete=models.CASCADE,
        related_name='approved_locations',
        null=True,
        blank=True,
        help_text="Associated business unit/site"
    )

    address = models.TextField(
        help_text="Physical address"
    )

    city = models.CharField(
        max_length=100,
        help_text="City"
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="State/Province"
    )

    country = models.CharField(
        max_length=100,
        help_text="Country"
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal/ZIP code"
    )

    # Network security
    ip_ranges = models.JSONField(
        default=list,
        help_text="Approved IP address ranges (CIDR notation)"
    )

    requires_vpn = models.BooleanField(
        default=False,
        help_text="VPN connection required"
    )

    # Geographic boundaries (for GPS validation)
    geofence_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="GeoJSON polygon for geofencing"
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude (for radius-based geofencing)"
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude (for radius-based geofencing)"
    )

    radius_meters = models.IntegerField(
        null=True,
        blank=True,
        help_text="Geofence radius in meters (if using lat/long)"
    )

    # Security configuration
    trust_level = models.CharField(
        max_length=20,
        choices=TRUST_LEVELS,
        default='MEDIUM',
        help_text="Trust level for enrollment operations"
    )

    requires_additional_verification = models.BooleanField(
        default=False,
        help_text="Require additional security checks"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Location is active and approved"
    )

    approved_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_locations',
        help_text="User who approved this location"
    )

    approved_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When location was approved"
    )

    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When location was deactivated"
    )

    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or requirements"
    )

    class Meta:
        db_table = 'approved_location'
        indexes = [
            models.Index(fields=['location_type', 'is_active']),
            models.Index(fields=['site', 'is_active']),
            models.Index(fields=['trust_level']),
            models.Index(fields=['country', 'city']),
        ]
        verbose_name = "Approved Location"
        verbose_name_plural = "Approved Locations"
        ordering = ['location_name']

    def __str__(self):
        return f"{self.location_name} ({self.get_location_type_display()})"

    def clean(self):
        """Validate location data."""
        super().clean()

        # Validate IP ranges format
        if self.ip_ranges:
            import ipaddress
            for ip_range in self.ip_ranges:
                try:
                    ipaddress.ip_network(ip_range)
                except ValueError as e:
                    raise ValidationError({
                        'ip_ranges': f"Invalid IP range '{ip_range}': {str(e)}"
                    })

        # Validate geofence data
        if self.latitude and self.longitude and not self.radius_meters:
            raise ValidationError({
                'radius_meters': "Radius required when using lat/long geofencing"
            })

    def is_ip_approved(self, ip_address: str) -> bool:
        """Check if IP address is within approved ranges."""
        if not self.ip_ranges:
            return True  # No IP restrictions

        import ipaddress
        try:
            ip = ipaddress.ip_address(ip_address)
            for ip_range in self.ip_ranges:
                network = ipaddress.ip_network(ip_range)
                if ip in network:
                    return True
            return False
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid IP address {ip_address}: {str(e)}")
            return False

    def is_within_geofence(self, latitude: float, longitude: float) -> bool:
        """Check if coordinates are within geofence."""
        if not self.latitude or not self.longitude or not self.radius_meters:
            return True  # No geofence configured

        from math import radians, cos, sin, asin, sqrt

        # Haversine formula for distance calculation
        lat1, lon1 = radians(float(self.latitude)), radians(float(self.longitude))
        lat2, lon2 = radians(latitude), radians(longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Earth's radius in meters
        distance_meters = 6371000 * c

        return distance_meters <= self.radius_meters

    def deactivate(self):
        """Deactivate this location."""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save()
