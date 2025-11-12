"""
Tracking model - Temporary table for GPS tracking data.

Used for real-time location tracking of personnel during conveyance, tours, and site visits.
"""
import uuid
from django.db import models
from django.conf import settings
from django.contrib.gis.db.models import PointField


class Tracking(models.Model):
    """
    Temporary table for real-time GPS tracking.

    Stores location data for:
    - Conveyance tracking
    - External/internal tours
    - Site visits
    - General personnel tracking
    """

    class Identifier(models.TextChoices):
        NONE = ("NONE", "None")
        CONVEYANCE = ("CONVEYANCE", "Conveyance")
        EXTERNALTOUR = ("EXTERNALTOUR", "External Tour")
        INTERNALTOUR = ("INTERNALTOUR", "Internal Tour")
        SITEVISIT = ("SITEVISIT", "Site Visit")
        TRACKING = ("TRACKING", "Tracking")

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    deviceid = models.CharField(max_length=40)
    gpslocation = PointField(geography=True, null=True, blank=True, srid=4326)
    receiveddate = models.DateTimeField(editable=True, null=True)
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="People",
    )
    transportmode = models.CharField(max_length=55)
    reference = models.CharField(max_length=255, default=None)
    identifier = models.CharField(
        max_length=55, choices=Identifier.choices, default=Identifier.NONE.value
    )

    class Meta:
        db_table = "tracking"
        indexes = [
            models.Index(fields=['people', 'receiveddate']),
            models.Index(fields=['identifier', 'receiveddate']),
            models.Index(fields=['deviceid']),
        ]


__all__ = ['Tracking']
