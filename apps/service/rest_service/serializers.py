"""
REST Service Serializers for Mobile API

Reuses validated serializers from core apps for consistency and security.

Compliance with Rule #13: Form Validation Requirements
- All serializers use explicit field lists
- All serializers have comprehensive validation
- Reuses validation logic from primary serializers
"""

from rest_framework import serializers
from apps.attendance.models import PeopleEventlog
from apps.peoples.models import People, Pgroup, Pgbelonging
from apps.onboarding.models import Bt, TypeAssist, Shift
from apps.activity.models.job_model import Jobneed, Job
from apps.activity.models.question_model import Question, QuestionSet
from apps.activity.models.location_model import Location
from apps.activity.models.asset_model import Asset

from apps.attendance.serializers import PeopleEventlogSerializer as BasePeopleEventlogSerializer
from apps.peoples.serializers import PeopleSerializer as BasePeopleSerializer
from apps.onboarding.serializers import (
    BtSerializers as BaseBtSerializer,
    TypeAssistSerializers as BaseTypeAssistSerializer,
    ShiftSerializers as BaseShiftSerializer,
)
from apps.schedhuler.serializers import (
    JobSerializers as BaseJobSerializer,
    JobneedSerializers as BaseJobneedSerializer,
)
from apps.activity.serializers import (
    QuestionSerializer as BaseQuestionSerializer,
    QuestionSetSerializer as BaseQuestionSetSerializer,
    AssetSerializer as BaseAssetSerializer,
    LocationSerializer as BaseLocationSerializer,
)
from apps.core.serializers import ValidatedModelSerializer


class PeopleEventLogSerializer(BasePeopleEventlogSerializer):
    """
    Mobile API serializer for PeopleEventlog.
    Inherits all validation from apps.attendance.serializers.PeopleEventlogSerializer
    """
    pass


class PeopleSerializer(BasePeopleSerializer):
    """
    Mobile API serializer for People.
    Inherits all validation from apps.peoples.serializers.PeopleSerializer
    """
    pass


class PgroupSerializer(ValidatedModelSerializer):
    """
    Secure Pgroup serializer with validation.
    """

    xss_protect_fields = ['groupname']
    name_fields = ['groupname']

    class Meta:
        model = Pgroup
        fields = [
            'id',
            'groupname',
            'grouplead',
            'identifier',
            'enable',
            'bu',
            'client',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_groupname(self, value):
        """Validate group name."""
        if not value:
            raise serializers.ValidationError("Group name is required")

        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError("Group name must be at least 2 characters")

        return value


class BtSerializer(BaseBtSerializer):
    """
    Mobile API serializer for Bt.
    Inherits all validation from apps.onboarding.serializers.BtSerializers
    """
    pass


class ShiftSerializer(BaseShiftSerializer):
    """
    Mobile API serializer for Shift.
    Inherits all validation from apps.onboarding.serializers.ShiftSerializers
    """
    pass


class TypeAssistSerializer(BaseTypeAssistSerializer):
    """
    Mobile API serializer for TypeAssist with field remapping.
    Inherits validation from apps.onboarding.serializers.TypeAssistSerializers
    """

    tatype_id = serializers.PrimaryKeyRelatedField(source="tatype", read_only=True)
    bu_id = serializers.PrimaryKeyRelatedField(source="bu", read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(source="client", read_only=True)
    cuser_id = serializers.PrimaryKeyRelatedField(source="cuser", read_only=True)
    muser_id = serializers.PrimaryKeyRelatedField(source="muser", read_only=True)

    class Meta(BaseTypeAssistSerializer.Meta):
        exclude = ["tenant", "bu", "client", "cuser", "muser", "tatype"]


class PgbelongingSerializer(ValidatedModelSerializer):
    """
    Secure Pgbelonging serializer with validation.
    """

    class Meta:
        model = Pgbelonging
        fields = [
            'id',
            'people',
            'pgroup',
            'isgrouplead',
            'bu',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        people = attrs.get('people')
        pgroup = attrs.get('pgroup')

        if people and pgroup:
            existing = Pgbelonging.objects.filter(
                people=people, pgroup=pgroup
            ).exclude(id=self.instance.id if self.instance else None)

            if existing.exists():
                raise serializers.ValidationError(
                    "This person is already a member of this group"
                )

        return attrs


class JobSerializer(BaseJobSerializer):
    """
    Mobile API serializer for Job.
    Inherits all validation from apps.schedhuler.serializers.JobSerializers
    """
    pass


class JobneedSerializer(BaseJobneedSerializer):
    """
    Mobile API serializer for Jobneed.
    Inherits all validation from apps.schedhuler.serializers.JobneedSerializers
    """
    pass


class AssetSerializer(BaseAssetSerializer):
    """
    Mobile API serializer for Asset.
    Inherits all validation from apps.activity.serializers.AssetSerializer
    """
    pass


class LocationSerializer(BaseLocationSerializer):
    """
    Mobile API serializer for Location.
    Inherits all validation from apps.activity.serializers.LocationSerializer
    """
    pass


class QuestionSerializer(BaseQuestionSerializer):
    """
    Mobile API serializer for Question.
    Inherits all validation from apps.activity.serializers.QuestionSerializer
    """
    pass


class QuestionSetSerializer(BaseQuestionSetSerializer):
    """
    Mobile API serializer for QuestionSet.
    Inherits all validation from apps.activity.serializers.QuestionSetSerializer
    """
    pass