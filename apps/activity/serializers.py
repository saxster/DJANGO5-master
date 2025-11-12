from rest_framework import serializers
from django.utils import timezone
from apps.activity.models.attachment_model import Attachment
from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.activity.models.asset_model import Asset
from apps.activity.models.location_model import Location
from apps.core.serializers import (
    ValidatedModelSerializer,
    validate_code_field,
    validate_name_field,
    validate_gps_field,
)
import logging

logger = logging.getLogger(__name__)


class AttachmentSerializer(ValidatedModelSerializer):
    """
    Secure Attachment serializer with file validation.

    Compliance with Rule #13 & #14: File upload security
    """

    xss_protect_fields = ['remarks']

    class Meta:
        model = Attachment
        fields = [
            'id',
            'uuid',
            'identifier',
            'owner',
            'file',
            'filetype',
            'isimage',
            'remarks',
            'seqno',
            'bu',
            'client',
            'cuser',
            'muser',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at', 'isimage']

    def validate_file(self, value):
        """Validate file upload security."""
        if not value:
            raise serializers.ValidationError("File is required")

        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 10MB")

        allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx', '.xls', '.xlsx']
        import os
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(f"File type {ext} not allowed")

        return value

    def validate_owner(self, value):
        """Validate owner field is not empty."""
        if not value:
            raise serializers.ValidationError("Owner is required")
        return value


class QuestionSerializer(ValidatedModelSerializer):
    """
    Secure Question serializer with comprehensive validation.
    """

    xss_protect_fields = ['quesname']
    name_fields = ['quesname']

    class Meta:
        model = Question
        fields = [
            'id',
            'quesname',
            'answertype',
            'options',
            'min',
            'max',
            'alerton',
            'isworkflow',
            'isavpt',
            'avpttype',
            'unit',
            'category',
            'bu',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_quesname(self, value):
        """Validate question name."""
        if not value:
            raise serializers.ValidationError("Question name is required")

        value = validate_name_field(value)

        if len(value) < 3:
            raise serializers.ValidationError("Question name must be at least 3 characters")

        return value

    def validate_min(self, value):
        """Validate min value."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Min value cannot be negative")
        return value

    def validate_max(self, value):
        """Validate max value."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Max value cannot be negative")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        min_val = attrs.get('min')
        max_val = attrs.get('max')

        if min_val is not None and max_val is not None:
            if min_val >= max_val:
                raise serializers.ValidationError(
                    {'max': 'Max value must be greater than min value'}
                )

        answertype = attrs.get('answertype')
        if answertype in ['CHECKBOX', 'DROPDOWN', 'MULTISELECT']:
            if not attrs.get('options'):
                raise serializers.ValidationError(
                    {'options': f'Options are required for {answertype} questions'}
                )

        return attrs


class QuestionSetSerializer(ValidatedModelSerializer):
    """
    Secure QuestionSet serializer with validation.
    """

    xss_protect_fields = ['qsetname']
    name_fields = ['qsetname']

    class Meta:
        model = QuestionSet
        fields = [
            'id',
            'qsetname',
            'type',
            'parent',
            'enable',
            'assetincludes',
            'site_type_includes',
            'buincludes',
            'site_grp_includes',
            'show_to_all_sites',
            'bu',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_qsetname(self, value):
        """Validate question set name."""
        if not value:
            raise serializers.ValidationError("Question set name is required")

        value = validate_name_field(value)

        if len(value) < 3:
            raise serializers.ValidationError("Question set name must be at least 3 characters")

        return value


class QuestionSetBelongingSerializer(ValidatedModelSerializer):
    """
    Secure QuestionSetBelonging serializer with validation.
    """

    class Meta:
        model = QuestionSetBelonging
        fields = [
            'id',
            'qset',
            'question',
            'seqno',
            'answertype',
            'options',
            'min',
            'max',
            'alerton',
            'isavpt',
            'avpttype',
            'ismandatory',
            'display_conditions',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_seqno(self, value):
        """Validate sequence number is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Sequence number must be positive")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        qset = attrs.get('qset')
        seqno = attrs.get('seqno')

        if qset and seqno:
            existing = QuestionSetBelonging.objects.filter(
                qset=qset, seqno=seqno
            ).exclude(id=self.instance.id if self.instance else None)

            if existing.exists():
                raise serializers.ValidationError(
                    {'seqno': 'Sequence number already exists in this question set'}
                )

        return attrs


class AssetSerializer(ValidatedModelSerializer):
    """
    Secure Asset serializer with comprehensive validation.
    """

    xss_protect_fields = ['assetname']
    code_fields = ['assetcode']
    name_fields = ['assetname']

    class Meta:
        model = Asset
        fields = [
            'id',
            'assetcode',
            'assetname',
            'runningstatus',
            'type',
            'category',
            'subcategory',
            'brand',
            'unit',
            'capacity',
            'identifier',
            'parent',
            'servprov',
            'location',
            'gpslocation',
            'iscritical',
            'enable',
            'bu',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_assetcode(self, value):
        """Validate asset code format and uniqueness."""
        if not value:
            raise serializers.ValidationError("Asset code is required")

        value = validate_code_field(value)

        instance_id = self.instance.id if self.instance else None
        self.validate_code_uniqueness(
            value, Asset, 'assetcode', exclude_id=instance_id
        )

        return value

    def validate_assetname(self, value):
        """Validate asset name."""
        if not value:
            raise serializers.ValidationError("Asset name is required")

        value = validate_name_field(value)

        if len(value) < 2:
            raise serializers.ValidationError("Asset name must be at least 2 characters")

        return value

    def validate_capacity(self, value):
        """Validate capacity is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Capacity must be positive")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        parent = attrs.get('parent')
        assetcode = attrs.get('assetcode')

        if parent and assetcode:
            if parent.assetcode == assetcode:
                raise serializers.ValidationError(
                    "Asset code cannot be same as parent asset code"
                )

        return attrs


class LocationSerializer(ValidatedModelSerializer):
    """
    Secure Location serializer with comprehensive validation.
    """

    xss_protect_fields = ['locname']
    code_fields = ['loccode']
    name_fields = ['locname']

    class Meta:
        model = Location
        fields = [
            'id',
            'loccode',
            'locname',
            'locstatus',
            'type',
            'parent',
            'gpslocation',
            'iscritical',
            'enable',
            'bu',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_loccode(self, value):
        """Validate location code format and uniqueness."""
        if not value:
            raise serializers.ValidationError("Location code is required")

        value = validate_code_field(value)

        instance_id = self.instance.id if self.instance else None
        self.validate_code_uniqueness(
            value, Location, 'loccode', exclude_id=instance_id
        )

        return value

    def validate_locname(self, value):
        """Validate location name."""
        if not value:
            raise serializers.ValidationError("Location name is required")

        value = validate_name_field(value)

        if len(value) < 2:
            raise serializers.ValidationError("Location name must be at least 2 characters")

        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        parent = attrs.get('parent')
        loccode = attrs.get('loccode')

        if parent and loccode:
            if parent.loccode == loccode:
                raise serializers.ValidationError(
                    "Location code cannot be same as parent location code"
                )

        return attrs
