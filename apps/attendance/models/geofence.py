"""
Geofence model - Geographic boundary definitions for attendance validation.

Uses PostGIS to store and validate polygon/circle geofences.
"""
from apps.core.models import BaseModel
from django.db import models
from django.contrib.gis.db.models import PointField, PolygonField
from django.utils.translation import gettext_lazy as _


class Geofence(BaseModel):
    """
    Geographic boundary definition for attendance validation.

    Uses PostGIS to store and validate polygon/circle geofences.
    """

    class GeofenceType(models.TextChoices):
        POLYGON = 'polygon', _('Polygon')
        CIRCLE = 'circle', _('Circle')

    name = models.CharField(max_length=255, help_text='Geofence name')
    geofence_type = models.CharField(
        max_length=20,
        choices=GeofenceType.choices,
        default=GeofenceType.POLYGON
    )
    boundary = PolygonField(srid=4326, null=True, blank=True)
    center_point = PointField(srid=4326, null=True, blank=True)
    radius = models.FloatField(null=True, blank=True)

    # Phase 3.3: Configurable hysteresis buffer
    hysteresis_meters = models.FloatField(
        default=1.0,
        help_text="Buffer zone in meters to prevent boundary flapping (configurable per geofence)"
    )

    bu = models.ForeignKey('client_onboarding.Bt', null=True, blank=True, on_delete=models.CASCADE)
    client = models.ForeignKey(
        'client_onboarding.Bt', null=True, blank=True,
        on_delete=models.CASCADE, related_name='attendance_geofence_clients'
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    # Tenant fields (following pattern from PeopleEventlog)
    tenant = models.CharField(max_length=100, default='default')

    class Meta:
        db_table = 'geofence'
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='geofence_tenant_active_idx'),
            models.Index(fields=['tenant', 'bu'], name='geofence_tenant_bu_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.geofence_type})"


__all__ = ['Geofence']
