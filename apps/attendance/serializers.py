from rest_framework import serializers
from django.utils import timezone
from apps.attendance.models import PeopleEventlog
from apps.core.serializers import ValidatedModelSerializer, validate_gps_field
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

    def validate_punchintime(self, value):
        """Validate punch in time."""
        if not value:
            raise serializers.ValidationError("Punch in time is required")

        if value > timezone.now():
            raise serializers.ValidationError("Punch in time cannot be in the future")

        return value

    def validate_punchouttime(self, value):
        """Validate punch out time."""
        if value and value > timezone.now():
            raise serializers.ValidationError("Punch out time cannot be in the future")

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
        """Cross-field validation and business rules."""
        attrs = super().validate(attrs)

        punchin = attrs.get('punchintime') or (self.instance.punchintime if self.instance else None)
        punchout = attrs.get('punchouttime') or (self.instance.punchouttime if self.instance else None)

        if punchin and punchout:
            if punchout <= punchin:
                raise serializers.ValidationError(
                    {'punchouttime': 'Punch out time must be after punch in time'}
                )

            time_diff = punchout - punchin
            duration_hours = time_diff.total_seconds() / 3600
            if duration_hours > 24:
                raise serializers.ValidationError(
                    "Attendance duration cannot exceed 24 hours"
                )

        datefor = attrs.get('datefor')
        if datefor and punchin:
            if punchin.date() != datefor:
                logger.warning(
                    "Punch in date doesn't match datefor",
                    extra={'datefor': datefor, 'punchin_date': punchin.date()}
                )

        peventtype = attrs.get('peventtype')
        if peventtype and peventtype.tacode in ['PRESENT', 'HALFDAY']:
            if not punchin:
                raise serializers.ValidationError(
                    "Punch in time is required for present/halfday attendance"
                )

        return attrs
