"""
Journal Serializer Validation Mixins

Consolidates duplicate validation logic across journal serializers.
Provides reusable validation mixins to reduce code duplication and ensure consistency.
"""

from rest_framework import serializers
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class WellbeingMetricsValidationMixin:
    """
    Mixin for validating wellbeing metrics fields

    Provides standardized validation for mood, stress, energy ratings
    across multiple serializers.
    """

    def validate_mood_rating(self, value):
        """Validate mood rating range"""
        if value is not None and (value < 1 or value > 10):
            raise serializers.ValidationError("Mood rating must be between 1 and 10")
        return value

    def validate_stress_level(self, value):
        """Validate stress level range"""
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Stress level must be between 1 and 5")
        return value

    def validate_energy_level(self, value):
        """Validate energy level range"""
        if value is not None and (value < 1 or value > 10):
            raise serializers.ValidationError("Energy level must be between 1 and 10")
        return value

    def validate_wellbeing_consistency(self, data):
        """
        Cross-field validation for wellbeing metrics consistency

        Ensures wellbeing metrics are logically consistent with each other.
        """
        mood = data.get('mood_rating')
        stress = data.get('stress_level')
        energy = data.get('energy_level')

        # Warning for inconsistent patterns (log but don't fail)
        if mood and stress:
            if mood >= 8 and stress >= 4:
                logger.warning("Potentially inconsistent wellbeing data: high mood with high stress")
            elif mood <= 3 and stress <= 2:
                logger.warning("Potentially inconsistent wellbeing data: low mood with low stress")

        if mood and energy:
            if mood >= 8 and energy <= 3:
                logger.warning("Potentially inconsistent wellbeing data: high mood with low energy")

        return data


class PerformanceMetricsValidationMixin:
    """
    Mixin for validating work performance metrics

    Standardizes validation for completion rates, efficiency scores, and quality metrics.
    """

    def validate_completion_rate(self, value):
        """Validate completion rate range"""
        if value is not None and (value < 0.0 or value > 1.0):
            raise serializers.ValidationError("Completion rate must be between 0.0 and 1.0")
        return value

    def validate_efficiency_score(self, value):
        """Validate efficiency score range"""
        if value is not None and (value < 0.0 or value > 10.0):
            raise serializers.ValidationError("Efficiency score must be between 0.0 and 10.0")
        return value

    def validate_quality_score(self, value):
        """Validate quality score range"""
        if value is not None and (value < 0.0 or value > 10.0):
            raise serializers.ValidationError("Quality score must be between 0.0 and 10.0")
        return value

    def validate_items_processed(self, value):
        """Validate items processed count"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Items processed cannot be negative")
        return value

    def validate_performance_consistency(self, data):
        """
        Cross-field validation for performance metrics consistency

        Ensures performance metrics are logically consistent.
        """
        completion = data.get('completion_rate')
        efficiency = data.get('efficiency_score')
        quality = data.get('quality_score')

        # Warning for unusual combinations
        if completion and efficiency:
            if completion >= 0.9 and efficiency <= 3.0:
                logger.warning("High completion rate with low efficiency score")

        if efficiency and quality:
            if efficiency >= 8.0 and quality <= 4.0:
                logger.warning("High efficiency with low quality score")

        return data


class LocationValidationMixin:
    """
    Mixin for validating location and coordinate data

    Provides standardized location validation across serializers.
    """

    def validate_location_coordinates(self, value):
        """Validate GPS coordinates format and range"""
        if not value:
            return value

        if not isinstance(value, dict):
            raise serializers.ValidationError("Location coordinates must be a dictionary")

        if 'lat' not in value or 'lng' not in value:
            raise serializers.ValidationError("Location coordinates must contain 'lat' and 'lng' keys")

        try:
            lat = float(value['lat'])
            lng = float(value['lng'])

            if lat < -90 or lat > 90:
                raise serializers.ValidationError("Latitude must be between -90 and 90")

            if lng < -180 or lng > 180:
                raise serializers.ValidationError("Longitude must be between -180 and 180")

        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid latitude or longitude values")

        return value

    def validate_location_site_name(self, value):
        """Validate location site name"""
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Location site name must be at least 2 characters")
        return value


class PrivacyValidationMixin:
    """
    Mixin for validating privacy and consent settings

    Ensures proper privacy scope validation based on entry type and user consent.
    """

    def validate_privacy_scope(self, value):
        """Validate privacy scope based on entry type"""
        entry_type = self.initial_data.get('entry_type')

        # Force private for sensitive wellbeing entries
        sensitive_types = ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']
        if entry_type in sensitive_types and value != 'private':
            raise serializers.ValidationError(
                f"Entry type '{entry_type}' must have private privacy scope"
            )

        return value

    def validate_consent_requirements(self, data):
        """
        Validate consent requirements for privacy scope

        Ensures user has given consent for non-private entries.
        """
        privacy_scope = data.get('privacy_scope', 'private')
        consent_given = data.get('consent_given', False)

        if privacy_scope != 'private' and not consent_given:
            raise serializers.ValidationError(
                "Consent must be given for entries with non-private privacy scope"
            )

        # Set consent timestamp if consent is given but timestamp is missing
        if consent_given and not data.get('consent_timestamp'):
            data['consent_timestamp'] = timezone.now()

        return data

    def validate_sharing_permissions(self, value):
        """Validate sharing permissions list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Sharing permissions must be a list")

        # Validate that all items are valid user IDs (UUIDs)
        for user_id in value:
            try:
                import uuid
                uuid.UUID(str(user_id))
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid user ID in sharing permissions: {user_id}")

        return value


class TimestampValidationMixin:
    """
    Mixin for validating timestamp and date-related fields

    Provides standardized timestamp validation and normalization.
    """

    def validate_timestamp(self, value):
        """Validate entry timestamp"""
        if not value:
            return timezone.now()

        # Don't allow future timestamps beyond 1 hour
        max_future = timezone.now() + timezone.timedelta(hours=1)
        if value > max_future:
            raise serializers.ValidationError("Timestamp cannot be more than 1 hour in the future")

        # Don't allow timestamps older than 1 year
        min_past = timezone.now() - timezone.timedelta(days=365)
        if value < min_past:
            raise serializers.ValidationError("Timestamp cannot be older than 1 year")

        return value

    def validate_duration_minutes(self, value):
        """Validate activity duration"""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError("Duration cannot be negative")
            if value > 1440:  # 24 hours
                raise serializers.ValidationError("Duration cannot exceed 24 hours")

        return value


class ContentValidationMixin:
    """
    Mixin for validating content and text fields

    Provides content validation, sanitization, and length checks.
    """

    def validate_title(self, value):
        """Validate entry title"""
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty")

        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters")

        if len(value) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters")

        return value.strip()

    def validate_content(self, value):
        """Validate entry content"""
        if value and len(value) > 10000:
            raise serializers.ValidationError("Content cannot exceed 10,000 characters")

        # Basic content sanitization - remove excessive whitespace
        if value:
            # Remove excessive newlines (more than 3 consecutive)
            import re
            value = re.sub(r'\n{4,}', '\n\n\n', value)
            value = value.strip()

        return value

    def validate_subtitle(self, value):
        """Validate entry subtitle"""
        if value and len(value) > 200:
            raise serializers.ValidationError("Subtitle cannot exceed 200 characters")

        return value.strip() if value else value


class JSONFieldValidationMixin:
    """
    Mixin for validating JSON fields

    Provides standardized validation for lists and structured data fields.
    """

    def validate_list_field(self, value, field_name, max_items=20, max_length=200):
        """
        Generic validation for list fields

        Args:
            value: List value to validate
            field_name: Name of field for error messages
            max_items: Maximum number of items allowed
            max_length: Maximum length per item
        """
        if not isinstance(value, list):
            raise serializers.ValidationError(f"{field_name} must be a list")

        if len(value) > max_items:
            raise serializers.ValidationError(f"{field_name} cannot have more than {max_items} items")

        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError(f"All {field_name} items must be strings")

            if len(item) > max_length:
                raise serializers.ValidationError(f"{field_name} items cannot exceed {max_length} characters")

        return value

    def validate_stress_triggers(self, value):
        """Validate stress triggers list"""
        return self.validate_list_field(value, "stress_triggers", max_items=10, max_length=100)

    def validate_coping_strategies(self, value):
        """Validate coping strategies list"""
        return self.validate_list_field(value, "coping_strategies", max_items=10, max_length=150)

    def validate_gratitude_items(self, value):
        """Validate gratitude items list"""
        return self.validate_list_field(value, "gratitude_items", max_items=10, max_length=200)

    def validate_daily_goals(self, value):
        """Validate daily goals list"""
        return self.validate_list_field(value, "daily_goals", max_items=5, max_length=150)

    def validate_affirmations(self, value):
        """Validate affirmations list"""
        return self.validate_list_field(value, "affirmations", max_items=10, max_length=200)

    def validate_achievements(self, value):
        """Validate achievements list"""
        return self.validate_list_field(value, "achievements", max_items=10, max_length=200)

    def validate_learnings(self, value):
        """Validate learnings list"""
        return self.validate_list_field(value, "learnings", max_items=10, max_length=200)

    def validate_challenges(self, value):
        """Validate challenges list"""
        return self.validate_list_field(value, "challenges", max_items=10, max_length=200)

    def validate_tags(self, value):
        """Validate tags list"""
        return self.validate_list_field(value, "tags", max_items=20, max_length=50)

    def validate_team_members(self, value):
        """Validate team members list"""
        return self.validate_list_field(value, "team_members", max_items=20, max_length=100)


class ComprehensiveJournalValidationMixin(
    WellbeingMetricsValidationMixin,
    PerformanceMetricsValidationMixin,
    LocationValidationMixin,
    PrivacyValidationMixin,
    TimestampValidationMixin,
    ContentValidationMixin,
    JSONFieldValidationMixin
):
    """
    Comprehensive validation mixin combining all journal validation logic

    Provides all validation capabilities in a single mixin for convenience.
    Serializers can inherit from this for complete validation coverage.
    """

    def validate(self, data):
        """
        Comprehensive cross-field validation

        Runs all validation checks and ensures data consistency.
        """
        # Run cross-field validations from all mixins
        data = self.validate_wellbeing_consistency(data)
        data = self.validate_performance_consistency(data)
        data = self.validate_consent_requirements(data)

        # Additional comprehensive validations
        data = self._validate_entry_type_consistency(data)
        data = self._validate_data_completeness(data)

        return super().validate(data) if hasattr(super(), 'validate') else data

    def _validate_entry_type_consistency(self, data):
        """Validate data consistency with entry type"""
        entry_type = data.get('entry_type')

        if not entry_type:
            return data

        # Wellbeing entries should have wellbeing metrics
        wellbeing_types = [
            'MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION',
            'GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS'
        ]

        if entry_type in wellbeing_types:
            has_wellbeing_data = any([
                data.get('mood_rating'),
                data.get('stress_level'),
                data.get('energy_level'),
                data.get('gratitude_items'),
                data.get('affirmations')
            ])

            if not has_wellbeing_data:
                logger.warning(f"Wellbeing entry type '{entry_type}' without wellbeing data")

        # Work entries should have work context
        work_types = [
            'SITE_INSPECTION', 'EQUIPMENT_MAINTENANCE', 'SAFETY_AUDIT',
            'PROJECT_MILESTONE', 'TEAM_COLLABORATION'
        ]

        if entry_type in work_types:
            has_work_data = any([
                data.get('location_site_name'),
                data.get('team_members'),
                data.get('completion_rate'),
                data.get('efficiency_score')
            ])

            if not has_work_data:
                logger.warning(f"Work entry type '{entry_type}' without work context data")

        return data

    def _validate_data_completeness(self, data):
        """Validate overall data completeness and quality"""
        # Count data richness
        data_points = 0

        # Core content
        if data.get('content') and len(data.get('content', '')) > 50:
            data_points += 2

        # Wellbeing metrics
        if data.get('mood_rating'):
            data_points += 1
        if data.get('stress_level'):
            data_points += 1
        if data.get('energy_level'):
            data_points += 1

        # Positive psychology
        if data.get('gratitude_items'):
            data_points += 1
        if data.get('achievements'):
            data_points += 1

        # Work context
        if data.get('location_site_name'):
            data_points += 1
        if data.get('completion_rate'):
            data_points += 1

        # Log data quality for analytics
        if data_points < 3:
            logger.debug("Low data richness journal entry")
        elif data_points >= 6:
            logger.debug("High data richness journal entry")

        return data