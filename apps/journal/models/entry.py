"""
Journal Entry Model

Complete journal entry model - ALL functionality moved from Kotlin.
Replaces the memory-only FeedManager implementation.

Features:
- Privacy controls with granular consent management
- Comprehensive wellbeing tracking (mood, stress, energy)
- Positive psychology integration (gratitude, affirmations, etc.)
- Work context and performance metrics
- Offline sync support with conflict resolution
- Multi-tenant isolation

Refactored from monolithic models.py (698 lines → focused modules).
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager
import uuid
from .enums import JournalEntryType, JournalPrivacyScope, JournalSyncStatus

User = get_user_model()


class JournalEntry(TenantAwareModel):
    """
    Complete journal entry model - ALL functionality moved from Kotlin
    Replaces the memory-only FeedManager implementation

    Features:
    - Privacy controls with granular consent management
    - Comprehensive wellbeing tracking (mood, stress, energy)
    - Positive psychology integration (gratitude, affirmations, etc.)
    - Work context and performance metrics
    - Offline sync support with conflict resolution
    - Multi-tenant isolation
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
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of activity in minutes"
    )

    # Privacy and consent controls (CRITICAL - was missing in Kotlin)
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

    # Enhanced wellbeing data (MOVED from Kotlin entities)
    mood_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Mood rating on 1-10 scale"
    )
    mood_description = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional mood description"
    )
    stress_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Stress level on 1-5 scale"
    )
    energy_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Energy level on 1-10 scale"
    )
    stress_triggers = models.JSONField(
        default=list,
        help_text="List of identified stress triggers"
    )
    coping_strategies = models.JSONField(
        default=list,
        help_text="List of coping strategies used"
    )

    # Positive psychology fields (NEW - from Kotlin JournalEntryFactory)
    gratitude_items = models.JSONField(
        default=list,
        help_text="List of things user is grateful for"
    )
    daily_goals = models.JSONField(
        default=list,
        help_text="List of daily goals or intentions"
    )
    affirmations = models.JSONField(
        default=list,
        help_text="List of positive affirmations"
    )
    achievements = models.JSONField(
        default=list,
        help_text="List of achievements or accomplishments"
    )
    learnings = models.JSONField(
        default=list,
        help_text="List of key learnings from the day"
    )
    challenges = models.JSONField(
        default=list,
        help_text="List of challenges faced"
    )

    # Location and work context
    location_site_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of work site or location"
    )
    location_address = models.TextField(
        blank=True,
        help_text="Full address of location"
    )
    location_coordinates = models.JSONField(
        null=True,
        blank=True,
        help_text='GPS coordinates as {"lat": 0.0, "lng": 0.0}'
    )
    location_area_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of work area (office, field, client site, etc.)"
    )
    team_members = models.JSONField(
        default=list,
        help_text="List of team members involved"
    )

    # Searchable fields and categorization
    tags = models.JSONField(
        default=list,
        help_text="List of tags for categorization and search"
    )
    priority = models.CharField(
        max_length=20,
        blank=True,
        help_text="Priority level (low, medium, high, urgent)"
    )
    severity = models.CharField(
        max_length=20,
        blank=True,
        help_text="Severity level for issues or concerns"
    )

    # Work performance metrics
    completion_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Completion rate as decimal (0.0 to 1.0)"
    )
    efficiency_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Efficiency score on 0-10 scale"
    )
    quality_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Quality score on 0-10 scale"
    )
    items_processed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of items or tasks processed"
    )

    # Entry state management
    is_bookmarked = models.BooleanField(
        default=False,
        help_text="Whether entry is bookmarked by user"
    )
    is_draft = models.BooleanField(
        default=False,
        help_text="Whether entry is still a draft"
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )

    # Sync and versioning (for offline mobile clients)
    sync_status = models.CharField(
        max_length=20,
        choices=JournalSyncStatus.choices,
        default=JournalSyncStatus.SYNCED,
        help_text="Current sync status with mobile clients"
    )
    mobile_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Client-generated ID for sync conflict resolution"
    )
    version = models.IntegerField(
        default=1,
        help_text="Version number for conflict resolution"
    )
    last_sync_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful sync with mobile client"
    )

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text="Flexible additional data and context"
    )

    objects = TenantAwareManager()

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"
        ordering = ['-timestamp', '-created_at']

        indexes = [
            models.Index(fields=['user', '-timestamp']),  # Performance: User timeline queries (descending)
            models.Index(fields=['entry_type', '-timestamp']),  # Performance: Type-filtered timeline
            models.Index(fields=['privacy_scope', 'user']),  # Performance: Privacy-aware queries
            models.Index(fields=['mood_rating', 'timestamp']),
            models.Index(fields=['stress_level', 'timestamp']),
            models.Index(fields=['sync_status', 'mobile_id']),
            models.Index(fields=['is_deleted', 'is_draft']),
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tags']),  # GIN index for JSON field (PostgreSQL specific)
            models.Index(fields=['timestamp', 'is_deleted']),  # Performance: MQTT health queries (Nov 5, 2025)
            models.Index(fields=['user', 'timestamp', 'is_deleted']),  # Performance: User timeline with deleted filter
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(mood_rating__gte=1, mood_rating__lte=10) | models.Q(mood_rating__isnull=True),
                name='valid_mood_rating_range'
            ),
            models.CheckConstraint(
                check=models.Q(stress_level__gte=1, stress_level__lte=5) | models.Q(stress_level__isnull=True),
                name='valid_stress_level_range'
            ),
            models.CheckConstraint(
                check=models.Q(energy_level__gte=1, energy_level__lte=10) | models.Q(energy_level__isnull=True),
                name='valid_energy_level_range'
            ),
            models.CheckConstraint(
                check=models.Q(completion_rate__gte=0.0, completion_rate__lte=1.0) | models.Q(completion_rate__isnull=True),
                name='valid_completion_rate_range'
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.peoplename} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

    def save(self, *args, **kwargs):
        """Override save to handle privacy scope defaults and validation"""
        if not self.timestamp:
            self.timestamp = timezone.now()

        # Set default privacy scope based on entry type
        if not self.privacy_scope:
            if self.entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
                self.privacy_scope = JournalPrivacyScope.PRIVATE
            else:
                self.privacy_scope = JournalPrivacyScope.PRIVATE  # Default to private

        # Auto-increment version for updates
        if self.pk:
            self.version += 1

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
        """Check if entry has mood, stress, or energy data"""
        return any([
            self.mood_rating is not None,
            self.stress_level is not None,
            self.energy_level is not None
        ])

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
            return False  # Placeholder
        elif effective_scope == JournalPrivacyScope.TEAM:
            # TODO: Implement team membership check
            return False  # Placeholder
        elif effective_scope == JournalPrivacyScope.AGGREGATE_ONLY:
            return False  # Only for aggregated analytics

        return False


__all__ = ['JournalEntry']
