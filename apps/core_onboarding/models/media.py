"""
Multimodal Media Storage for Onboarding Platform

Supports universal media capture across all onboarding contexts:
- Client onboarding: Office photos, signage
- Site onboarding: Zone photos/videos, asset documentation
- Worker onboarding: ID documents, certificates, training videos

Features:
- 0 to N media per observation (flexible)
- GPS location capture
- AI analysis (Vision API, LLM processing)
- Context-agnostic (works with any entity)

Complies with:
- Rule #7: Model < 150 lines
- Rule #14: File upload security (filename sanitization)
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from apps.core.models import TenantAwareModel


class OnboardingMedia(TenantAwareModel):
    """
    Universal media storage for onboarding observations.

    Supports:
    - Photos (JPEG, PNG, WebP)
    - Videos (MP4, WebM, QuickTime)
    - Audio (MP3, WAV, WebM, OGG)
    - Documents (PDF, scanned images)

    Used by:
    - Client context: Office photos, signage
    - Site context: Zone documentation, asset photos
    - Worker context: ID scans, certificates
    """

    class MediaType(models.TextChoices):
        PHOTO = 'PHOTO', _('Photo')
        VIDEO = 'VIDEO', _('Video')
        AUDIO = 'AUDIO', _('Audio Recording')
        DOCUMENT = 'DOCUMENT', _('Document Scan')

    class ContextType(models.TextChoices):
        CLIENT = 'CLIENT', _('Client Setup')
        SITE = 'SITE', _('Site Survey')
        WORKER = 'WORKER', _('Worker Documents')

    # Identifiers
    media_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Context linkage (generic)
    context_type = models.CharField(
        _('Context Type'),
        max_length=20,
        choices=ContextType.choices,
        help_text=_('Which onboarding context this media belongs to')
    )
    context_object_id = models.CharField(
        _('Context Object ID'),
        max_length=100,
        help_text=_('UUID of the related object (site_id, request_id, etc.)')
    )

    # Media storage
    media_type = models.CharField(
        _('Media Type'),
        max_length=20,
        choices=MediaType.choices
    )
    file = models.FileField(
        _('File'),
        upload_to='onboarding_media/%Y/%m/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'jpg', 'jpeg', 'png', 'webp',  # Photos
                    'mp4', 'webm', 'mov',          # Videos
                    'mp3', 'wav', 'ogg',           # Audio
                    'pdf'                           # Documents
                ]
            )
        ]
    )
    thumbnail = models.ImageField(
        _('Thumbnail'),
        upload_to='onboarding_media/thumbnails/',
        null=True,
        blank=True,
        help_text=_('Auto-generated thumbnail for photos/videos')
    )

    # Geolocation (captured at upload time)
    gps_latitude = models.FloatField(_('GPS Latitude'), null=True, blank=True)
    gps_longitude = models.FloatField(_('GPS Longitude'), null=True, blank=True)
    gps_accuracy = models.FloatField(_('GPS Accuracy (meters)'), null=True, blank=True)
    compass_direction = models.FloatField(
        _('Compass Direction'),
        null=True,
        blank=True,
        help_text=_('Degrees (0-360) camera was facing')
    )

    # Voice/text annotation
    voice_transcript = models.TextField(
        _('Voice Transcript'),
        blank=True,
        help_text=_('Speech-to-text transcription if audio')
    )
    text_description = models.TextField(
        _('Text Description'),
        blank=True,
        help_text=_('User-provided text description')
    )
    translated_description = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Translations: {"es": "...", "hi": "...", "ta": "..."}')
    )

    # AI analysis
    ai_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Vision API or LLM analysis results')
    )
    detected_objects = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Detected objects: ["camera", "door", "person"]')
    )
    safety_concerns = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Safety issues: ["no fire extinguisher", "blocked exit"]')
    )

    # Metadata
    uploaded_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.PROTECT,
        related_name='uploaded_media'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False, help_text=_('AI analysis completed'))

    class Meta:
        db_table = 'core_onboarding_media'
        verbose_name = 'Onboarding Media'
        verbose_name_plural = 'Onboarding Media'
        indexes = [
            models.Index(fields=['context_type', 'context_object_id'], name='media_context_idx'),
            models.Index(fields=['uploaded_at'], name='media_uploaded_idx'),
            models.Index(fields=['media_type'], name='media_type_idx'),
        ]
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_media_type_display()} - {self.context_type} ({self.uploaded_at})"
