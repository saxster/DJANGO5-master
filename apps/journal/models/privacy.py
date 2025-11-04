"""
Journal Privacy Settings Model

User privacy preferences for journal data with granular consent controls.
CRITICAL - was missing in Kotlin implementation.

Refactored from monolithic models.py (698 lines → focused modules).
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .enums import JournalPrivacyScope

User = get_user_model()


class JournalPrivacySettings(models.Model):
    """User privacy preferences for journal data (CRITICAL - was missing in Kotlin)"""

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
        validators=[MinValueValidator(30), MaxValueValidator(3650)],
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

    def get_effective_privacy_scope(self, entry_type):
        """Determine effective privacy scope based on entry type and consent"""
        # Always private for sensitive wellbeing data
        if entry_type in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
            return JournalPrivacyScope.PRIVATE
        return self.default_privacy_scope

    def can_share_wellbeing_data(self):
        """Check if user has consented to sharing wellbeing data"""
        return self.wellbeing_sharing_consent and self.analytics_consent

    def should_trigger_crisis_intervention(self, journal_entry):
        """Check if crisis intervention should be triggered for entry"""
        if not self.crisis_intervention_consent:
            return False

        # Basic crisis indicators (more sophisticated logic in services)
        if journal_entry.mood_rating and journal_entry.mood_rating <= 2:
            return True
        if journal_entry.stress_level and journal_entry.stress_level >= 5:
            return True

        return False


__all__ = ['JournalPrivacySettings']
