from rest_framework import serializers
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.attendance.models import PeopleEventlog
from apps.core.serializers import ValidatedModelSerializer, validate_gps_field
from apps.core.utils_new.timezone_utils import (
    validate_timezone_offset,
    normalize_client_timezone,
    validate_datetime_not_future,
    get_client_timezone_info
)
import logging

logger = logging.getLogger(__name__)


class PeopleEventlogSerializer(ValidatedModelSerializer):
    """
    Secure PeopleEventlog serializer with comprehensive validation.

    Compliance with Rule #13: Form Validation Requirements
    - Explicit field list (no __all__)
    - Field-level validation for critical biometric data
    - Cross-field validation for attendance logic
    - Business rule validation for shift compliance
    - Timezone normalization for mobile clients
    """

    xss_protect_fields = ['remarks']

    class Meta:
        model = PeopleEventlog
        fields = [
            'id',
            'uuid',
            'people',
            'datefor',
            'punchintime',
            'punchouttime',
            'peventtype',
            'shift',
            'verifiedby',
            'remarks',
            'remarkstype',
            'gpslocation',
            'startlocation',
            'endlocation',
            'journeypath',
            'distance',
            'duration',
            'expamt',
            'transportmodes',
            'facerecognitionin',
            'facerecognitionout',
            'bu',
            'client',
            'ctzoffset',
            'version',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'uuid',
            'created_at',
            'updated_at',
            'duration',
        ]

    def validate_ctzoffset(self, value):
        """
        Validate client timezone offset.

        Ensures offset is within valid range and logs timezone info.
        """
        if value is None:
            raise serializers.ValidationError(
                "Client timezone offset (ctzoffset) is required for mobile submissions"
            )

        if not validate_timezone_offset(value):
            tz_info = get_client_timezone_info(value)
            raise serializers.ValidationError(
                f"Invalid timezone offset: {value} minutes. "
                f"Must be between -720 and 840 minutes (UTC-12:00 to UTC+14:00). "
                f"Received offset would be: {tz_info['utc_offset_string']}"
            )

        # Log timezone for monitoring
        tz_info = get_client_timezone_info(value)
        logger.debug(
            f"Client timezone validated: {tz_info['name']} ({tz_info['utc_offset_string']})"
        )

        return value

    def validate_punchintime(self, value):
        """
        Validate punch in time with timezone awareness.

        Checks:
        - Value not in future (with 5-minute tolerance for clock skew)
        - Value is timezone-aware or will be normalized
        """
        if not value:
            raise serializers.ValidationError("Punch in time is required")

        # Validate not in future (allows 5-minute clock skew tolerance)
        if not validate_datetime_not_future(value, max_future_minutes=5):
            raise serializers.ValidationError(
                "Punch in time cannot be more than 5 minutes in the future. "
                "Check device clock synchronization."
            )

        return value

    def validate_punchouttime(self, value):
        """
        Validate punch out time with timezone awareness.

        Checks:
        - Value not in future (with 5-minute tolerance for clock skew)
        - Value is timezone-aware or will be normalized
        """
        if value and not validate_datetime_not_future(value, max_future_minutes=5):
            raise serializers.ValidationError(
                "Punch out time cannot be more than 5 minutes in the future. "
                "Check device clock synchronization."
            )

        return value

    def validate_distance(self, value):
        """Validate distance is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Distance must be positive")
        return value

    def validate_expamt(self, value):
        """Validate expense amount is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Expense amount must be positive")
        return value

    def validate_facerecognitionin(self, value):
        """Validate face recognition score for punch in."""
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("Face recognition score must be between 0 and 100")
        return value

    def validate_facerecognitionout(self, value):
        """Validate face recognition score for punch out."""
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("Face recognition score must be between 0 and 100")
        return value

    def validate(self, attrs):
        """
        Cross-field validation and business rules.

        Performs timezone normalization if client offset is provided.
        """
        attrs = super().validate(attrs)

        # Timezone normalization for mobile clients
        ctzoffset = attrs.get('ctzoffset')

        if ctzoffset is not None:
            # Normalize punchintime to UTC if provided as naive datetime
            punchintime = attrs.get('punchintime')
            if punchintime and punchintime.tzinfo is None:
                try:
                    attrs['punchintime'] = normalize_client_timezone(
                        punchintime,
                        ctzoffset
                    )
                    logger.info(
                        f"Normalized punch in time to UTC: {attrs['punchintime']} "
                        f"(client offset: {ctzoffset} minutes)"
                    )
                except DjangoValidationError as e:
                    raise serializers.ValidationError(
                        {'punchintime': f"Timezone normalization failed: {e}"}
                    )

            # Normalize punchouttime to UTC if provided as naive datetime
            punchouttime = attrs.get('punchouttime')
            if punchouttime and punchouttime.tzinfo is None:
                try:
                    attrs['punchouttime'] = normalize_client_timezone(
                        punchouttime,
                        ctzoffset
                    )
                    logger.info(
                        f"Normalized punch out time to UTC: {attrs['punchouttime']} "
                        f"(client offset: {ctzoffset} minutes)"
                    )
                except DjangoValidationError as e:
                    raise serializers.ValidationError(
                        {'punchouttime': f"Timezone normalization failed: {e}"}
                    )

        # Get normalized or existing times for validation
        punchin = attrs.get('punchintime') or (self.instance.punchintime if self.instance else None)
        punchout = attrs.get('punchouttime') or (self.instance.punchouttime if self.instance else None)

        # Validate punch in/out sequence
        if punchin and punchout:
            if punchout <= punchin:
                raise serializers.ValidationError(
                    {'punchouttime': 'Punch out time must be after punch in time'}
                )

            time_diff = punchout - punchin
            duration_hours = time_diff.total_seconds() / 3600
            if duration_hours > 24:
                raise serializers.ValidationError(
                    "Attendance duration cannot exceed 24 hours. "
                    f"Current duration: {duration_hours:.2f} hours"
                )

        # Validate date consistency
        datefor = attrs.get('datefor')
        if datefor and punchin:
            # Compare dates (punchin is now UTC, extract date component)
            punchin_date = punchin.date()
            if punchin_date != datefor:
                # Allow one day difference for timezone boundaries
                date_diff = abs((punchin_date - datefor).days)
                if date_diff > 1:
                    raise serializers.ValidationError(
                        f"Punch in date ({punchin_date}) differs from attendance date ({datefor}) "
                        f"by more than 1 day. Check timezone configuration."
                    )
                logger.warning(
                    "Punch in date mismatch (likely timezone boundary crossing)",
                    extra={
                        'datefor': datefor,
                        'punchin_date_utc': punchin_date,
                        'ctzoffset': ctzoffset
                    }
                )

        # Validate attendance type requirements
        peventtype = attrs.get('peventtype')
        if peventtype and peventtype.tacode in ['PRESENT', 'HALFDAY']:
            if not punchin:
                raise serializers.ValidationError(
                    "Punch in time is required for present/halfday attendance"
                )

        return attrs
