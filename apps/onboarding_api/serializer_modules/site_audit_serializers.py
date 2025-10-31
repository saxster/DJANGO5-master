"""
Site Audit Serializers for Phase C: API Layer.

This module provides serializers for the multimodal site security auditing API,
handling voice + photo + GPS observations, zone management, coverage planning,
and report generation.

Following .claude/rules.md:
- Rule #13: Explicit field lists with custom validation
- Rule #11: Specific exception handling in validation methods
- Rule #6: Keep serializers focused (< 100 lines per class)
"""

from decimal import Decimal
from rest_framework import serializers
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Observation,
    SitePhoto,
    Asset,
    Checkpoint,
    MeterPoint,
    SOP,
    CoveragePlan
)


class SiteAuditStartSerializer(serializers.Serializer):
    """
    Serializer for starting a new site audit session.

    Validates business unit, site type, and optional configuration.
    """
    business_unit_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the business unit to audit"
    )
    site_type = serializers.ChoiceField(
        choices=OnboardingSite.SiteTypeChoices.choices,
        required=True,
        help_text="Type of site being audited"
    )
    language = serializers.CharField(
        max_length=10,
        default='en',
        help_text="Primary audit language (ISO 639-1 code)"
    )
    operating_hours = serializers.JSONField(
        required=False,
        help_text="Operating hours: {start: 'HH:MM', end: 'HH:MM'}"
    )
    gps_location = serializers.JSONField(
        required=False,
        help_text="Primary site GPS: {latitude: float, longitude: float}"
    )

    def validate_operating_hours(self, value):
        """Validate operating hours format."""
        if value:
            if not isinstance(value, dict):
                raise serializers.ValidationError("Operating hours must be an object")

            if 'start' not in value or 'end' not in value:
                raise serializers.ValidationError("Must provide 'start' and 'end' times")

            # Validate time format (HH:MM)
            import re
            time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')

            if not time_pattern.match(value['start']):
                raise serializers.ValidationError("Invalid start time format. Use HH:MM")
            if not time_pattern.match(value['end']):
                raise serializers.ValidationError("Invalid end time format. Use HH:MM")

        return value

    def validate_gps_location(self, value):
        """Validate GPS coordinates."""
        if value:
            if not isinstance(value, dict):
                raise serializers.ValidationError("GPS location must be an object")

            if 'latitude' not in value or 'longitude' not in value:
                raise serializers.ValidationError("Must provide latitude and longitude")

            try:
                lat = float(value['latitude'])
                lon = float(value['longitude'])

                if not (-90 <= lat <= 90):
                    raise serializers.ValidationError("Latitude must be between -90 and 90")
                if not (-180 <= lon <= 180):
                    raise serializers.ValidationError("Longitude must be between -180 and 180")
            except (TypeError, ValueError):
                raise serializers.ValidationError("Invalid GPS coordinates")

        return value


class ObservationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating multimodal observations.

    Supports photo, audio, text input, GPS, and zone hints.
    At least one input modality is required.
    """
    photo = serializers.ImageField(
        required=False,
        help_text="Photo of the zone/asset",
        max_length=5 * 1024 * 1024  # 5MB max
    )
    audio = serializers.FileField(
        required=False,
        help_text="Voice observation audio file",
        max_length=10 * 1024 * 1024  # 10MB max
    )
    text_input = serializers.CharField(
        required=False,
        max_length=2000,
        help_text="Manual text observation"
    )
    gps_latitude = serializers.FloatField(
        required=True,
        min_value=-90.0,
        max_value=90.0,
        help_text="GPS latitude at capture"
    )
    gps_longitude = serializers.FloatField(
        required=True,
        min_value=-180.0,
        max_value=180.0,
        help_text="GPS longitude at capture"
    )
    zone_hint = serializers.CharField(
        required=False,
        max_length=200,
        help_text="Operator's hint for zone identification"
    )
    compass_direction = serializers.FloatField(
        required=False,
        min_value=0.0,
        max_value=360.0,
        help_text="Compass direction in degrees (0-360)"
    )

    def validate(self, data):
        """Ensure at least one input modality is provided."""
        if not any([
            data.get('photo'),
            data.get('audio'),
            data.get('text_input')
        ]):
            raise serializers.ValidationError(
                "At least one input required: photo, audio, or text_input"
            )

        return data

    def validate_photo(self, value):
        """Validate photo file type and size."""
        if value:
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    f"Invalid image type. Allowed: {', '.join(allowed_types)}"
                )

            max_size = 5 * 1024 * 1024  # 5MB
            if value.size > max_size:
                raise serializers.ValidationError(
                    f"Image too large. Maximum size: {max_size / 1024 / 1024}MB"
                )

        return value

    def validate_audio(self, value):
        """Validate audio file type and size."""
        if value:
            allowed_types = [
                'audio/wav', 'audio/mpeg', 'audio/mp3',
                'audio/ogg', 'audio/webm', 'audio/flac'
            ]
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    f"Invalid audio type. Allowed: {', '.join(allowed_types)}"
                )

            max_size = 10 * 1024 * 1024  # 10MB
            if value.size > max_size:
                raise serializers.ValidationError(
                    f"Audio file too large. Maximum size: {max_size / 1024 / 1024}MB"
                )

        return value


class ObservationSerializer(serializers.ModelSerializer):
    """
    Serializer for Observation model with zone details.

    Includes computed fields for zone information.
    """
    zone_details = serializers.SerializerMethodField()
    confidence_score = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Observation
        fields = [
            'observation_id',
            'transcript_original',
            'transcript_english',
            'enhanced_observation',
            'entities',
            'severity',
            'confidence_score',
            'gps_at_capture',
            'media_links',
            'zone_details',
            'captured_by',
            'cdtz'
        ]
        read_only_fields = ['observation_id', 'confidence_score', 'cdtz']

    def get_zone_details(self, obj):
        """Get zone information for the observation."""
        if obj.zone:
            return {
                'zone_id': str(obj.zone.zone_id),
                'zone_name': obj.zone.zone_name,
                'zone_type': obj.zone.zone_type,
                'importance_level': obj.zone.importance_level
            }
        return None


class SitePhotoSerializer(serializers.ModelSerializer):
    """Serializer for site photos with vision analysis."""

    class Meta:
        model = SitePhoto
        fields = [
            'photo_id',
            'image',
            'thumbnail',
            'gps_coordinates',
            'compass_direction',
            'vision_analysis',
            'detected_objects',
            'safety_concerns',
            'uploaded_by',
            'cdtz'
        ]
        read_only_fields = [
            'photo_id',
            'vision_analysis',
            'detected_objects',
            'safety_concerns',
            'cdtz'
        ]


class ZoneSerializer(serializers.ModelSerializer):
    """
    Serializer for OnboardingZone with observation counts.

    Includes annotated fields for coverage tracking.
    """
    observations_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of observations for this zone"
    )
    photos_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of photos for this zone"
    )
    assets_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of assets in this zone"
    )

    class Meta:
        model = OnboardingZone
        fields = [
            'zone_id',
            'zone_type',
            'zone_name',
            'importance_level',
            'risk_level',
            'gps_coordinates',
            'coverage_required',
            'compliance_notes',
            'observations_count',
            'photos_count',
            'assets_count'
        ]
        read_only_fields = ['zone_id']


class ZoneCreateSerializer(serializers.Serializer):
    """Serializer for bulk zone creation."""
    zones = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of zones to create"
    )

    def validate_zones(self, value):
        """Validate each zone has required fields."""
        required_fields = ['zone_type', 'zone_name', 'importance_level']

        for idx, zone in enumerate(value):
            for field in required_fields:
                if field not in zone:
                    raise serializers.ValidationError(
                        f"Zone {idx}: Missing required field '{field}'"
                    )

            # Validate zone_type
            valid_types = [choice[0] for choice in OnboardingZone.ZoneTypeChoices.choices]
            if zone['zone_type'] not in valid_types:
                raise serializers.ValidationError(
                    f"Zone {idx}: Invalid zone_type. Valid: {', '.join(valid_types)}"
                )

            # Validate importance_level
            valid_importance = [choice[0] for choice in OnboardingZone.ImportanceLevelChoices.choices]
            if zone['importance_level'] not in valid_importance:
                raise serializers.ValidationError(
                    f"Zone {idx}: Invalid importance_level. Valid: {', '.join(valid_importance)}"
                )

        return value


class AssetCreateSerializer(serializers.Serializer):
    """Serializer for bulk asset creation."""
    assets = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of assets to create"
    )

    def validate_assets(self, value):
        """Validate each asset has required fields."""
        required_fields = ['zone_id', 'asset_type', 'asset_name', 'status']

        for idx, asset in enumerate(value):
            for field in required_fields:
                if field not in asset:
                    raise serializers.ValidationError(
                        f"Asset {idx}: Missing required field '{field}'"
                    )

            # Validate asset_type
            valid_types = [choice[0] for choice in Asset.AssetTypeChoices.choices]
            if asset['asset_type'] not in valid_types:
                raise serializers.ValidationError(
                    f"Asset {idx}: Invalid asset_type"
                )

            # Validate status
            valid_status = [choice[0] for choice in Asset.StatusChoices.choices]
            if asset['status'] not in valid_status:
                raise serializers.ValidationError(
                    f"Asset {idx}: Invalid status"
                )

        return value


class MeterPointCreateSerializer(serializers.Serializer):
    """Serializer for bulk meter point creation."""
    meter_points = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of meter points to create"
    )

    def validate_meter_points(self, value):
        """Validate each meter point has required fields."""
        required_fields = ['zone_id', 'meter_type', 'meter_name', 'reading_frequency']

        for idx, meter in enumerate(value):
            for field in required_fields:
                if field not in meter:
                    raise serializers.ValidationError(
                        f"Meter {idx}: Missing required field '{field}'"
                    )

            # Validate meter_type
            valid_types = [choice[0] for choice in MeterPoint.MeterTypeChoices.choices]
            if meter['meter_type'] not in valid_types:
                raise serializers.ValidationError(
                    f"Meter {idx}: Invalid meter_type"
                )

        return value


class CoveragePlanSerializer(serializers.ModelSerializer):
    """Serializer for guard coverage and shift planning."""

    total_posts = serializers.SerializerMethodField()
    total_shifts = serializers.SerializerMethodField()

    class Meta:
        model = CoveragePlan
        fields = [
            'plan_id',
            'guard_posts',
            'shift_assignments',
            'patrol_routes',
            'risk_windows',
            'compliance_notes',
            'generated_by',
            'approved_by',
            'approved_at',
            'total_posts',
            'total_shifts',
            'cdtz'
        ]
        read_only_fields = ['plan_id', 'cdtz']

    def get_total_posts(self, obj):
        """Calculate total guard posts."""
        return len(obj.guard_posts) if obj.guard_posts else 0

    def get_total_shifts(self, obj):
        """Calculate total shifts per day."""
        return len(obj.shift_assignments) if obj.shift_assignments else 0


class SOPSerializer(serializers.ModelSerializer):
    """Serializer for Standard Operating Procedures."""

    zone_details = serializers.SerializerMethodField()
    asset_details = serializers.SerializerMethodField()

    class Meta:
        model = SOP
        fields = [
            'sop_id',
            'sop_title',
            'purpose',
            'steps',
            'staffing_required',
            'compliance_references',
            'frequency',
            'translated_texts',
            'escalation_triggers',
            'zone_details',
            'asset_details',
            'llm_generated',
            'reviewed_by',
            'approved_at',
            'cdtz'
        ]
        read_only_fields = ['sop_id', 'cdtz']

    def get_zone_details(self, obj):
        """Get zone information if SOP is zone-specific."""
        if obj.zone:
            return {
                'zone_id': str(obj.zone.zone_id),
                'zone_name': obj.zone.zone_name,
                'zone_type': obj.zone.zone_type
            }
        return None

    def get_asset_details(self, obj):
        """Get asset information if SOP is asset-specific."""
        if obj.asset:
            return {
                'asset_id': str(obj.asset.asset_id),
                'asset_name': obj.asset.asset_name,
                'asset_type': obj.asset.asset_type
            }
        return None


class AuditAnalysisSerializer(serializers.Serializer):
    """Serializer for triggering site audit analysis."""

    force_reanalysis = serializers.BooleanField(
        default=False,
        help_text="Force re-analysis even if already analyzed"
    )
    include_recommendations = serializers.BooleanField(
        default=True,
        help_text="Include AI recommendations in analysis"
    )
    include_sops = serializers.BooleanField(
        default=True,
        help_text="Generate SOPs during analysis"
    )
    include_coverage_plan = serializers.BooleanField(
        default=True,
        help_text="Generate coverage plan during analysis"
    )
    target_languages = serializers.ListField(
        child=serializers.CharField(max_length=10),
        required=False,
        help_text="Languages for SOP translation (e.g., ['hi', 'mr'])"
    )


class ReportGenerationSerializer(serializers.Serializer):
    """Serializer for generating audit reports."""

    lang = serializers.CharField(
        max_length=10,
        default='en',
        help_text="Report language (ISO 639-1 code)"
    )
    save_to_kb = serializers.BooleanField(
        default=True,
        help_text="Save report to knowledge base"
    )
    format = serializers.ChoiceField(
        choices=['html', 'pdf', 'json'],
        default='html',
        help_text="Report output format"
    )
    include_photos = serializers.BooleanField(
        default=True,
        help_text="Include photos in report"
    )
    include_sops = serializers.BooleanField(
        default=True,
        help_text="Include SOPs in report"
    )
    include_coverage_plan = serializers.BooleanField(
        default=True,
        help_text="Include coverage plan in report"
    )


class AuditSessionStatusSerializer(serializers.Serializer):
    """Serializer for audit session status response."""

    state = serializers.CharField(help_text="Current session state")
    progress_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Audit completion percentage"
    )
    coverage = serializers.DictField(
        help_text="Coverage statistics"
    )
    current_zone = serializers.CharField(
        required=False,
        help_text="Currently audited zone"
    )
    next_recommended_zone = serializers.CharField(
        required=False,
        help_text="Suggested next zone"
    )
    observations_count = serializers.IntegerField(
        help_text="Total observations captured"
    )
    estimated_completion_minutes = serializers.IntegerField(
        required=False,
        help_text="Estimated time to complete audit"
    )


class NextQuestionsSerializer(serializers.Serializer):
    """Serializer for contextual next questions."""

    current_zone = serializers.CharField(required=False)
    questions = serializers.ListField(
        child=serializers.DictField()
    )
    completion_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2
    )
    critical_gaps = serializers.ListField(
        child=serializers.CharField()
    )


class CoverageMapSerializer(serializers.Serializer):
    """Serializer for coverage map visualization."""

    coverage_map = serializers.DictField(
        help_text="Overall coverage statistics"
    )
    zones = serializers.ListField(
        child=serializers.DictField(),
        help_text="Zone-level coverage details"
    )
    critical_gaps = serializers.ListField(
        child=serializers.DictField(),
        help_text="Critical zones not yet covered"
    )
    recommended_route = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="Optimized route for remaining zones"
    )