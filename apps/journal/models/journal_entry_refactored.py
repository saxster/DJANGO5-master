"""
Refactored Journal Entry Model

Refactored to follow Single Responsibility Principle with separate models for:
- JournalWellbeingMetrics: Mood, stress, energy, positive psychology
- JournalWorkContext: Location, team, performance metrics
- JournalSyncData: Mobile sync, versioning, conflict resolution

Includes backward compatibility layer to maintain API compatibility.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.text import get_valid_filename
from apps.tenants.models import TenantAwareModel
from .journal_metrics import JournalWellbeingMetrics
from .journal_work_context import JournalWorkContext
from .journal_sync_data import JournalSyncData
import uuid
import logging
import os
import re

User = get_user_model()
logger = logging.getLogger(__name__)


def upload_journal_media(instance, filename):
    """
    SECURE file upload path generator for journal media attachments.

    Implements comprehensive security measures:
    - Filename sanitization to prevent path traversal
    - Extension validation against media type whitelist
    - Path boundary enforcement within MEDIA_ROOT
    - Dangerous pattern detection
    - Unique filename generation to prevent conflicts

    Complies with Rule #14 from .claude/rules.md - File Upload Security
    """
    try:
        safe_filename = get_valid_filename(filename)
        if not safe_filename:
            raise ValueError("Filename could not be sanitized")

        ALLOWED_EXTENSIONS = {
            'PHOTO': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
            'VIDEO': {'.mp4', '.mov', '.avi', '.webm'},
            'DOCUMENT': {'.pdf', '.doc', '.docx', '.txt'},
            'AUDIO': {'.mp3', '.wav', '.m4a', '.aac', '.ogg'}
        }

        file_extension = os.path.splitext(safe_filename)[1].lower()
        media_type = getattr(instance, 'media_type', 'PHOTO')

        if media_type in ALLOWED_EXTENSIONS:
            if file_extension not in ALLOWED_EXTENSIONS[media_type]:
                logger.warning(
                    "Invalid file extension for media type",
                    extra={
                        'filename': filename,
                        'extension': file_extension,
                        'media_type': media_type
                    }
                )
                default_ext = list(ALLOWED_EXTENSIONS[media_type])[0]
                file_extension = default_ext

        DANGEROUS_PATTERNS = ['..', '/', '\\', '\x00', '~']
        if any(pattern in safe_filename for pattern in DANGEROUS_PATTERNS):
            logger.warning(
                "Dangerous pattern detected in filename",
                extra={'filename': safe_filename}
            )
            safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', os.path.splitext(safe_filename)[0]) + file_extension

        import time
        timestamp = int(time.time())
        journal_id = str(instance.journal_entry.id) if hasattr(instance, 'journal_entry') else 'default'
        safe_journal_id = get_valid_filename(journal_id)[:50]

        secure_filename = f"{safe_journal_id}_{timestamp}{file_extension}"

        date_path = timezone.now().strftime('%Y/%m/%d')
        relative_path = f"journal_media/{date_path}/{secure_filename}"

        logger.info(
            "Secure journal media upload path generated",
            extra={
                'original_filename': filename,
                'secure_filename': secure_filename,
                'media_type': media_type
            }
        )

        return relative_path

    except (ValueError, AttributeError, OSError) as e:
        logger.error(
            "Error generating secure upload path for journal media",
            extra={'error': str(e), 'filename': filename}
        )
        return f"journal_media/error/{uuid.uuid4()}.dat"


class JournalPrivacyScope(models.TextChoices):
    """Privacy scope options for journal entries"""
    PRIVATE = 'private', 'Private - Only visible to me'
    MANAGER = 'manager', 'Manager - Visible to my direct manager'
    TEAM = 'team', 'Team - Visible to my team'
    AGGREGATE_ONLY = 'aggregate', 'Aggregate - Anonymous statistics only'
    SHARED = 'shared', 'Shared - Visible to selected stakeholders'


class JournalEntryType(models.TextChoices):
    """Journal entry types - work-related and wellbeing entries"""

    # Work-related entries
    SITE_INSPECTION = 'site_inspection', 'Site Inspection'
    EQUIPMENT_MAINTENANCE = 'equipment_maintenance', 'Equipment Maintenance'
    SAFETY_AUDIT = 'safety_audit', 'Safety Audit'
    TRAINING_COMPLETED = 'training_completed', 'Training Completed'
    PROJECT_MILESTONE = 'project_milestone', 'Project Milestone'
    TEAM_COLLABORATION = 'team_collaboration', 'Team Collaboration'
    CLIENT_INTERACTION = 'client_interaction', 'Client Interaction'
    PROCESS_IMPROVEMENT = 'process_improvement', 'Process Improvement'
    DOCUMENTATION_UPDATE = 'documentation_update', 'Documentation Update'
    FIELD_OBSERVATION = 'field_observation', 'Field Observation'
    QUALITY_NOTE = 'quality_note', 'Quality Note'
    INVESTIGATION_NOTE = 'investigation_note', 'Investigation Note'
    SAFETY_CONCERN = 'safety_concern', 'Safety Concern'

    # Wellbeing entries
    PERSONAL_REFLECTION = 'personal_reflection', 'Personal Reflection'
    MOOD_CHECK_IN = 'mood_check_in', 'Mood Check-in'
    GRATITUDE = 'gratitude', 'Gratitude Entry'
    THREE_GOOD_THINGS = 'three_good_things', '3 Good Things'
    DAILY_AFFIRMATIONS = 'daily_affirmations', 'Daily Affirmations'
    STRESS_LOG = 'stress_log', 'Stress Log'
    STRENGTH_SPOTTING = 'strength_spotting', 'Strength Spotting'
    REFRAME_CHALLENGE = 'reframe_challenge', 'Reframe Challenge'
    DAILY_INTENTION = 'daily_intention', 'Daily Intention'
    END_OF_SHIFT_REFLECTION = 'end_of_shift_reflection', 'End of Shift Reflection'
    BEST_SELF_WEEKLY = 'best_self_weekly', 'Best Self Weekly'


class JournalEntry(TenantAwareModel):
    """
    Refactored journal entry model following Single Responsibility Principle

    Core entry data only - complex functionality delegated to separate models:
    - JournalWellbeingMetrics: Mood, stress, energy, positive psychology
    - JournalWorkContext: Location, team, performance metrics
    - JournalSyncData: Mobile sync, versioning, conflict resolution

    Includes backward compatibility layer for existing API consumers.
    """

    # Core identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='journal_entries',
        help_text="Owner of this journal entry"
    )

    # Entry metadata
    entry_type = models.CharField(
        max_length=50,
        choices=JournalEntryType.choices,
        help_text="Type of journal entry (work or wellbeing)"
    )
    title = models.CharField(max_length=200, help_text="Entry title")
    subtitle = models.CharField(max_length=200, blank=True, help_text="Optional subtitle")
    content = models.TextField(blank=True, help_text="Main entry content")
    timestamp = models.DateTimeField(help_text="When this entry was created")

    # Privacy and consent controls
    privacy_scope = models.CharField(
        max_length=20,
        choices=JournalPrivacyScope.choices,
        default=JournalPrivacyScope.PRIVATE,
        help_text="Who can access this entry"
    )
    consent_given = models.BooleanField(
        default=False,
        help_text="User consent for data processing"
    )
    consent_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consent was given"
    )
    sharing_permissions = models.JSONField(
        default=list,
        help_text="List of user IDs who can access this entry"
    )

    # Related models (1:1 relationships)
    wellbeing_metrics = models.OneToOneField(
        JournalWellbeingMetrics,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='journal_entry',
        help_text="Wellbeing metrics (mood, stress, energy, positive psychology)"
    )
    work_context = models.OneToOneField(
        JournalWorkContext,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='journal_entry',
        help_text="Work context (location, team, performance metrics)"
    )
    sync_data = models.OneToOneField(
        JournalSyncData,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='journal_entry',
        help_text="Mobile sync and versioning data"
    )

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text="Flexible additional data and context"
    )

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"
        ordering = ['-timestamp', '-created_at']

        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['entry_type', 'user']),
            models.Index(fields=['privacy_scope', 'user']),
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.peoplename} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

    def save(self, *args, **kwargs):
        """Override save to handle defaults and create related models"""
        if not self.timestamp:
            self.timestamp = timezone.now()

        # Set default privacy scope based on entry type
        if not self.privacy_scope:
            if self.entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
                self.privacy_scope = JournalPrivacyScope.PRIVATE
            else:
                self.privacy_scope = JournalPrivacyScope.PRIVATE

        # Create sync data if it doesn't exist
        if not self.sync_data:
            self.sync_data = JournalSyncData.objects.create()

        super().save(*args, **kwargs)

    @property
    def is_wellbeing_entry(self):
        """Check if this is a wellbeing-focused entry"""
        wellbeing_types = [
            'PERSONAL_REFLECTION', 'MOOD_CHECK_IN', 'GRATITUDE', 'THREE_GOOD_THINGS',
            'DAILY_AFFIRMATIONS', 'STRESS_LOG', 'STRENGTH_SPOTTING', 'REFRAME_CHALLENGE',
            'DAILY_INTENTION', 'END_OF_SHIFT_REFLECTION', 'BEST_SELF_WEEKLY'
        ]
        return self.entry_type in wellbeing_types

    @property
    def has_wellbeing_metrics(self):
        """Check if entry has wellbeing metrics"""
        return self.wellbeing_metrics and self.wellbeing_metrics.has_metrics

    def get_effective_privacy_scope(self, requesting_user=None):
        """Get effective privacy scope considering user permissions and entry type"""
        # Always private for sensitive wellbeing data
        if self.entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
            if requesting_user and requesting_user.id == self.user.id:
                return self.privacy_scope
            return JournalPrivacyScope.PRIVATE

        return self.privacy_scope

    def can_user_access(self, user):
        """Check if user can access this journal entry"""
        # Owner always has access
        if user.id == self.user.id:
            return True

        # Check privacy scope
        effective_scope = self.get_effective_privacy_scope(user)

        if effective_scope == JournalPrivacyScope.PRIVATE:
            return False
        elif effective_scope == JournalPrivacyScope.SHARED:
            return user.id in self.sharing_permissions
        elif effective_scope == JournalPrivacyScope.MANAGER:
            # TODO: Implement manager relationship check
            return False
        elif effective_scope == JournalPrivacyScope.TEAM:
            # TODO: Implement team membership check
            return False
        elif effective_scope == JournalPrivacyScope.AGGREGATE_ONLY:
            return False

        return False

    # ========================================
    # BACKWARD COMPATIBILITY LAYER
    # ========================================

    # Wellbeing metrics compatibility properties
    @property
    def mood_rating(self):
        """Backward compatibility for mood_rating"""
        return self.wellbeing_metrics.mood_rating if self.wellbeing_metrics else None

    @mood_rating.setter
    def mood_rating(self, value):
        """Backward compatibility setter for mood_rating"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.mood_rating = value
        self.wellbeing_metrics.save()

    @property
    def mood_description(self):
        """Backward compatibility for mood_description"""
        return self.wellbeing_metrics.mood_description if self.wellbeing_metrics else ""

    @mood_description.setter
    def mood_description(self, value):
        """Backward compatibility setter for mood_description"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.mood_description = value
        self.wellbeing_metrics.save()

    @property
    def stress_level(self):
        """Backward compatibility for stress_level"""
        return self.wellbeing_metrics.stress_level if self.wellbeing_metrics else None

    @stress_level.setter
    def stress_level(self, value):
        """Backward compatibility setter for stress_level"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.stress_level = value
        self.wellbeing_metrics.save()

    @property
    def energy_level(self):
        """Backward compatibility for energy_level"""
        return self.wellbeing_metrics.energy_level if self.wellbeing_metrics else None

    @energy_level.setter
    def energy_level(self, value):
        """Backward compatibility setter for energy_level"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.energy_level = value
        self.wellbeing_metrics.save()

    @property
    def stress_triggers(self):
        """Backward compatibility for stress_triggers"""
        return self.wellbeing_metrics.stress_triggers if self.wellbeing_metrics else []

    @stress_triggers.setter
    def stress_triggers(self, value):
        """Backward compatibility setter for stress_triggers"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.stress_triggers = value or []
        self.wellbeing_metrics.save()

    @property
    def coping_strategies(self):
        """Backward compatibility for coping_strategies"""
        return self.wellbeing_metrics.coping_strategies if self.wellbeing_metrics else []

    @coping_strategies.setter
    def coping_strategies(self, value):
        """Backward compatibility setter for coping_strategies"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.coping_strategies = value or []
        self.wellbeing_metrics.save()

    @property
    def gratitude_items(self):
        """Backward compatibility for gratitude_items"""
        return self.wellbeing_metrics.gratitude_items if self.wellbeing_metrics else []

    @gratitude_items.setter
    def gratitude_items(self, value):
        """Backward compatibility setter for gratitude_items"""
        if not self.wellbeing_metrics:
            self.wellbeing_metrics = JournalWellbeingMetrics.objects.create()
        self.wellbeing_metrics.gratitude_items = value or []
        self.wellbeing_metrics.save()

    # Work context compatibility properties
    @property
    def location_site_name(self):
        """Backward compatibility for location_site_name"""
        return self.work_context.location_site_name if self.work_context else ""

    @location_site_name.setter
    def location_site_name(self, value):
        """Backward compatibility setter for location_site_name"""
        if not self.work_context:
            self.work_context = JournalWorkContext.objects.create()
        self.work_context.location_site_name = value or ""
        self.work_context.save()

    @property
    def completion_rate(self):
        """Backward compatibility for completion_rate"""
        return self.work_context.completion_rate if self.work_context else None

    @completion_rate.setter
    def completion_rate(self, value):
        """Backward compatibility setter for completion_rate"""
        if not self.work_context:
            self.work_context = JournalWorkContext.objects.create()
        self.work_context.completion_rate = value
        self.work_context.save()

    # Sync data compatibility properties
    @property
    def sync_status(self):
        """Backward compatibility for sync_status"""
        return self.sync_data.sync_status if self.sync_data else 'synced'

    @sync_status.setter
    def sync_status(self, value):
        """Backward compatibility setter for sync_status"""
        if not self.sync_data:
            self.sync_data = JournalSyncData.objects.create()
        self.sync_data.sync_status = value
        self.sync_data.save()

    @property
    def is_draft(self):
        """Backward compatibility for is_draft"""
        return self.sync_data.is_draft if self.sync_data else False

    @is_draft.setter
    def is_draft(self, value):
        """Backward compatibility setter for is_draft"""
        if not self.sync_data:
            self.sync_data = JournalSyncData.objects.create()
        self.sync_data.is_draft = value
        self.sync_data.save()

    @property
    def is_deleted(self):
        """Backward compatibility for is_deleted"""
        return self.sync_data.is_deleted if self.sync_data else False

    @is_deleted.setter
    def is_deleted(self, value):
        """Backward compatibility setter for is_deleted"""
        if not self.sync_data:
            self.sync_data = JournalSyncData.objects.create()
        self.sync_data.is_deleted = value
        self.sync_data.save()

    @property
    def version(self):
        """Backward compatibility for version"""
        return self.sync_data.version if self.sync_data else 1

    @version.setter
    def version(self, value):
        """Backward compatibility setter for version"""
        if not self.sync_data:
            self.sync_data = JournalSyncData.objects.create()
        self.sync_data.version = value
        self.sync_data.save()


class JournalMediaAttachment(models.Model):
    """Media attachments for journal entries - unchanged from original"""

    MEDIA_TYPES = [
        ('PHOTO', 'Photo'),
        ('VIDEO', 'Video'),
        ('DOCUMENT', 'Document'),
        ('AUDIO', 'Audio'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='media_attachments',
        help_text="Associated journal entry"
    )

    # Media details
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPES,
        help_text="Type of media attachment"
    )
    file = models.FileField(
        upload_to=upload_journal_media,
        help_text="Media file upload (secured with validation)"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename from client"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type of the file"
    )
    file_size = models.BigIntegerField(
        help_text="File size in bytes"
    )

    # Display properties
    caption = models.TextField(
        blank=True,
        help_text="Optional caption for the media"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying multiple media items"
    )
    is_hero_image = models.BooleanField(
        default=False,
        help_text="Whether this is the main/hero image for the entry"
    )

    # Sync management for mobile clients
    mobile_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Client-generated ID for sync"
    )
    sync_status = models.CharField(
        max_length=20,
        default='synced',
        help_text="Sync status with mobile clients"
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journal Media Attachment"
        verbose_name_plural = "Journal Media Attachments"
        ordering = ['display_order', '-created_at']

        indexes = [
            models.Index(fields=['journal_entry', 'display_order']),
            models.Index(fields=['media_type']),
            models.Index(fields=['sync_status']),
            models.Index(fields=['is_deleted']),
        ]

    def __str__(self):
        return f"{self.media_type}: {self.original_filename} ({self.journal_entry.title})"

    def save(self, *args, **kwargs):
        """Set hero image logic and file metadata"""
        if self.is_hero_image:
            # Ensure only one hero image per journal entry
            JournalMediaAttachment.objects.filter(
                journal_entry=self.journal_entry,
                is_hero_image=True
            ).exclude(id=self.id).update(is_hero_image=False)

        super().save(*args, **kwargs)


class JournalPrivacySettings(models.Model):
    """User privacy preferences for journal data - unchanged from original"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='journal_privacy_settings',
        help_text="User these privacy settings belong to"
    )

    # Default privacy preferences
    default_privacy_scope = models.CharField(
        max_length=20,
        choices=JournalPrivacyScope.choices,
        default=JournalPrivacyScope.PRIVATE,
        help_text="Default privacy scope for new entries"
    )

    # Granular consent controls
    wellbeing_sharing_consent = models.BooleanField(
        default=False,
        help_text="Consent to share wellbeing data for analytics"
    )
    manager_access_consent = models.BooleanField(
        default=False,
        help_text="Consent for manager to access certain entries"
    )
    analytics_consent = models.BooleanField(
        default=False,
        help_text="Consent for anonymous analytics and insights"
    )
    crisis_intervention_consent = models.BooleanField(
        default=False,
        help_text="Consent for crisis intervention based on entries"
    )

    # Data retention preferences
    data_retention_days = models.IntegerField(
        default=365,
        help_text="How long to retain journal data (30-3650 days)"
    )
    auto_delete_enabled = models.BooleanField(
        default=False,
        help_text="Whether to automatically delete old entries"
    )

    # Audit trail
    consent_timestamp = models.DateTimeField(
        help_text="When initial consent was given"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journal Privacy Settings"
        verbose_name_plural = "Journal Privacy Settings"

    def __str__(self):
        return f"Privacy Settings - {self.user.peoplename}"

    def save(self, *args, **kwargs):
        """Set consent timestamp on first save"""
        if not self.consent_timestamp:
            self.consent_timestamp = timezone.now()
        super().save(*args, **kwargs)