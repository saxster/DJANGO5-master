from rest_framework import serializers
from django.utils import timezone
from .models import Bt, Shift, TypeAssist, GeofenceMaster
from apps.core.serializers import (
    ValidatedModelSerializer,
    validate_code_field,
    validate_name_field,
    validate_gps_field,
)
import logging

logger = logging.getLogger(__name__)


class BtSerializers(ValidatedModelSerializer):
    """
    Secure Bt (Business Unit/Site) serializer with comprehensive validation.

    Compliance with Rule #13: Form Validation Requirements
    """

    xss_protect_fields = ['buname', 'address']
    code_fields = ['bucode']
    name_fields = ['buname']

    class Meta:
        model = Bt
        fields = [
            'id',
            'bucode',
            'buname',
            'parent',
            'butype',
            'identifier',
            'siteincharge',
            'address',
            'gpslocation',
            'permissibledistance',
            'gpsenable',
            'iswarehouse',
            'isserviceprovider',
            'isvendor',
            'skipsiteaudit',
            'enablesleepingguard',
            'deviceevent',
            'solid',
            'enable',
            'bupreferences',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_bucode(self, value):
        """Validate business unit code."""
        if not value:
            raise serializers.ValidationError("Business unit code is required")

        value = validate_code_field(value)

        instance_id = self.instance.id if self.instance else None
        self.validate_code_uniqueness(
            value, Bt, 'bucode', exclude_id=instance_id
        )

        return value

    def validate_buname(self, value):
        """Validate business unit name."""
        if not value:
            raise serializers.ValidationError("Business unit name is required")

        value = validate_name_field(value)
        return value

    def validate_permissibledistance(self, value):
        """Validate permissible distance is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Permissible distance must be positive")
        return value

    def validate_solid(self, value):
        """Validate SOL ID format."""
        if value and not str(value).isalnum():
            raise serializers.ValidationError("SOL ID must be alphanumeric")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        parent = attrs.get('parent')
        bucode = attrs.get('bucode')

        if parent and bucode:
            if parent.bucode == bucode:
                raise serializers.ValidationError(
                    "Business unit code cannot be same as parent code"
                )

        gpsenable = attrs.get('gpsenable')
        gpslocation = attrs.get('gpslocation')

        if gpsenable and not gpslocation:
            logger.warning(
                "GPS enabled but no GPS location provided",
                extra={'bucode': bucode}
            )

        return attrs


class ShiftSerializers(ValidatedModelSerializer):
    """
    Secure Shift serializer with comprehensive validation.
    """

    xss_protect_fields = ['shiftname']
    name_fields = ['shiftname']

    class Meta:
        model = Shift
        fields = [
            'id',
            'shiftname',
            'starttime',
            'endtime',
            'shiftduration',
            'nightshiftappicable',
            'designation',
            'captchafreq',
            'peoplecount',
            'shift_data',
            'overtime',
            'bu',
            'client',
            'enable',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'shiftduration']

    def validate_shiftname(self, value):
        """Validate shift name."""
        if not value:
            raise serializers.ValidationError("Shift name is required")

        value = validate_name_field(value)
        return value

    def validate_peoplecount(self, value):
        """Validate people count is positive."""
        if value is not None and value < 1:
            raise serializers.ValidationError("People count must be at least 1")
        return value

    def validate_overtime(self, value):
        """Validate overtime is not negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Overtime cannot be negative")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        starttime = attrs.get('starttime')
        endtime = attrs.get('endtime')
        overtime = attrs.get('overtime')
        shiftduration = attrs.get('shiftduration')

        if starttime and endtime:
            if endtime <= starttime:
                from datetime import datetime, timedelta
                endtime_next_day = datetime.combine(datetime.today() + timedelta(days=1), endtime.time()) if isinstance(endtime, datetime) else endtime
                if not (isinstance(endtime, datetime) and endtime > starttime):
                    logger.info("Shift spans midnight")

        if overtime and shiftduration:
            shift_hours = shiftduration / 60
            if overtime > shift_hours:
                raise serializers.ValidationError(
                    "Overtime hours cannot exceed shift duration"
                )

        return attrs


class TypeAssistSerializers(ValidatedModelSerializer):
    """
    Secure TypeAssist serializer with comprehensive validation.
    """

    xss_protect_fields = ['taname']
    code_fields = ['tacode']
    name_fields = ['taname']

    class Meta:
        model = TypeAssist
        fields = [
            'id',
            'tacode',
            'taname',
            'tatype',
            'sortorder',
            'enable',
            'bu',
            'client',
            'cuser',
            'muser',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_tacode(self, value):
        """Validate type assist code."""
        if not value:
            raise serializers.ValidationError("Type assist code is required")

        value = validate_code_field(value)

        if len(value) > 25:
            raise serializers.ValidationError("Code cannot exceed 25 characters")

        return value

    def validate_taname(self, value):
        """Validate type assist name."""
        if not value:
            raise serializers.ValidationError("Type assist name is required")

        value = validate_name_field(value)
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        tacode = attrs.get('tacode')
        tatype = attrs.get('tatype')

        if tacode and tatype:
            from django.db.models import Q
            instance_id = self.instance.id if self.instance else None

            query = Q(tacode=tacode, tatype=tatype)
            if instance_id:
                query &= ~Q(id=instance_id)

            if TypeAssist.objects.filter(query).exists():
                raise serializers.ValidationError(
                    "This combination of code and type already exists"
                )

        return attrs


class GeofenceMasterSerializers(ValidatedModelSerializer):
    """
    Secure GeofenceMaster serializer with comprehensive validation.
    """

    xss_protect_fields = ['gfname', 'alerttext']
    code_fields = ['gfcode']
    name_fields = ['gfname']

    class Meta:
        model = GeofenceMaster
        fields = [
            'id',
            'gfcode',
            'gfname',
            'gfarea',
            'alerttopeople',
            'alerttogroup',
            'alerttext',
            'enable',
            'bu',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_gfcode(self, value):
        """Validate geofence code."""
        if not value:
            raise serializers.ValidationError("Geofence code is required")

        value = validate_code_field(value)

        instance_id = self.instance.id if self.instance else None
        self.validate_code_uniqueness(
            value, GeofenceMaster, 'gfcode', exclude_id=instance_id
        )

        return value

    def validate_gfname(self, value):
        """Validate geofence name."""
        if not value:
            raise serializers.ValidationError("Geofence name is required")

        value = validate_name_field(value)
        return value

    def validate_alerttext(self, value):
        """Validate alert text is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Alert text is required")
        return value.strip()

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        alerttopeople = attrs.get('alerttopeople')
        alerttogroup = attrs.get('alerttogroup')

        if not alerttopeople and not alerttogroup:
            raise serializers.ValidationError(
                "At least one of alert to people or alert to group must be specified"
            )

        return attrs