"""
Site Video Model - Video documentation for site security audits.

Stores video files with metadata for walkthrough documentation,
incident recording, and training purposes.
"""

import uuid
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from .upload_utils import upload_site_video, upload_site_video_thumbnail


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
        upload_to=upload_site_video
    )
    thumbnail = models.ImageField(
        _("Thumbnail"),
        upload_to=upload_site_video_thumbnail,
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
