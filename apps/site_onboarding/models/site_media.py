"""
Site media wrappers for photo and video documentation.

These wrap OnboardingMedia for site-specific classification and provide
convenience methods for Vision API analysis and GPS-tagged media.
"""

import uuid
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class SitePhoto(BaseModel, TenantAwareModel):
    """
    Photo documentation with Vision API analysis.

    Stores images with AI-powered object detection, hazard identification,
    and OCR text extraction.
    """

    photo_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "site_onboarding.OnboardingSite",
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name=_("Site")
    )
    zone = models.ForeignKey(
        "site_onboarding.OnboardingZone",
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
        db_table = "site_onboarding_photo"
        verbose_name = "Site Photo"
        verbose_name_plural = "Site Photos"
        indexes = [
            models.Index(fields=['zone', 'cdtz'], name='photo_zone_time_idx'),
            models.Index(fields=['site', 'cdtz'], name='photo_site_time_idx'),
        ]

    def __str__(self):
        return f"Photo at {self.zone.zone_name}"


class SiteVideo(BaseModel, TenantAwareModel):
    """
    Video documentation for site security audits.

    Stores video files with metadata for walkthrough documentation,
    incident recording, and training purposes.
    """

    video_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "site_onboarding.OnboardingSite",
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name=_("Site")
    )
    zone = models.ForeignKey(
        "site_onboarding.OnboardingZone",
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name=_("Zone"),
        null=True,
        blank=True
    )
    video_file = models.FileField(
        _("Video File"),
        upload_to="onboarding/videos/%Y/%m/%d/"
    )
    thumbnail = models.ImageField(
        _("Thumbnail"),
        upload_to="onboarding/video_thumbnails/%Y/%m/%d/",
        null=True,
        blank=True
    )
    duration_seconds = models.IntegerField(
        _("Duration (seconds)"),
        null=True,
        blank=True
    )
    gps_start = PointField(
        _("GPS at Start"),
        null=True,
        blank=True,
        geography=True
    )
    gps_end = PointField(
        _("GPS at End"),
        null=True,
        blank=True,
        geography=True
    )
    video_metadata = models.JSONField(
        _("Video Metadata"),
        default=dict,
        blank=True,
        help_text="Technical metadata: {resolution, codec, fps, size_bytes}"
    )
    transcript = models.TextField(
        _("Transcript"),
        blank=True,
        help_text="AI-generated transcript of audio track"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="site_videos",
        verbose_name=_("Uploaded By")
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_video"
        verbose_name = "Site Video"
        verbose_name_plural = "Site Videos"
        indexes = [
            models.Index(fields=['zone', 'cdtz'], name='video_zone_time_idx'),
            models.Index(fields=['site', 'cdtz'], name='video_site_time_idx'),
        ]

    def __str__(self):
        zone_name = self.zone.zone_name if self.zone else "General"
        return f"Video at {zone_name}"
