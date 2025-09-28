from rest_framework import serializers
from django.utils import timezone
from apps.activity.models.job_model import Job, Jobneed, JobneedDetails
from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.core.serializers import (
    ValidatedModelSerializer,
    validate_name_field,
)
from apps.core.utils_new.cron_utilities import validate_cron_for_form
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class CustomTimeField(serializers.Field):
    def to_representation(self, value):
        if isinstance(value, datetime):
            return value.time().isoformat()
        elif isinstance(value, time):
            return value.isoformat()
        return None

    def to_internal_value(self, data):
        try:
            return datetime.strptime(data, "%H:%M:%S").time()
        except ValueError as e:
            raise serializers.ValidationError("Invalid time format. Use 'HH:MM:SS'.") from e


class JobSerializers(ValidatedModelSerializer):
    """
    Secure Job serializer with comprehensive validation.

    Compliance with Rule #13: Form Validation Requirements
    """

    starttime = CustomTimeField()
    endtime = CustomTimeField()

    xss_protect_fields = ['jobname', 'jobdesc']
    name_fields = ['jobname']

    class Meta:
        model = Job
        fields = [
            'id',
            'jobname',
            'jobdesc',
            'fromdate',
            'uptodate',
            'cron',
            'sgroup',
            'identifier',
            'planduration',
            'gracetime',
            'expirytime',
            'asset',
            'priority',
            'qset',
            'pgroup',
            'people',
            'geofence',
            'parent',
            'seqno',
            'starttime',
            'endtime',
            'frequency',
            'scantype',
            'ticketcategory',
            'shift',
            'other_info',
            'bu',
            'client',
            'enable',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_jobname(self, value):
        """Validate job name."""
        if not value:
            raise serializers.ValidationError("Job name is required")

        value = validate_name_field(value)
        if len(value) < 3:
            raise serializers.ValidationError("Job name must be at least 3 characters")
        return value

    def validate_planduration(self, value):
        """Validate plan duration is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Plan duration must be positive")
        return value

    def validate_gracetime(self, value):
        """Validate grace time is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Grace time must be positive")
        return value

    def validate_cron(self, value):
        """Validate cron expression."""
        if not value:
            return value

        error = validate_cron_for_form(value)
        if error:
            raise serializers.ValidationError(error)

        parts = value.strip().split()
        if len(parts) == 5 and parts[0] == "*":
            raise serializers.ValidationError(
                "Scheduling every minute is not allowed"
            )

        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        fromdate = attrs.get('fromdate')
        uptodate = attrs.get('uptodate')

        if fromdate and uptodate and fromdate > uptodate:
            raise serializers.ValidationError(
                {'uptodate': 'Valid to date cannot be before valid from date'}
            )

        people = attrs.get('people')
        pgroup = attrs.get('pgroup')

        if not people and not pgroup:
            raise serializers.ValidationError(
                "Job must be assigned to either a person or a group"
            )

        return attrs


class JobneedSerializers(ValidatedModelSerializer):
    """
    Secure Jobneed serializer with comprehensive validation.
    """

    xss_protect_fields = ['jobdesc', 'remarks']

    class Meta:
        model = Jobneed
        fields = [
            'id',
            'uuid',
            'identifier',
            'frequency',
            'parent',
            'job',
            'jobdesc',
            'asset',
            'ticketcategory',
            'qset',
            'people',
            'pgroup',
            'priority',
            'scantype',
            'multifactor',
            'jobstatus',
            'plandatetime',
            'expirydatetime',
            'gracetime',
            'starttime',
            'endtime',
            'performedby',
            'gpslocation',
            'remarks',
            'remarkstype',
            'alerts',
            'raisedtktflag',
            'ismailsent',
            'attachmentcount',
            'deviation',
            'seqno',
            'other_info',
            'ticket',
            'bu',
            'client',
            'cuser',
            'muser',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

    def validate_gracetime(self, value):
        """Validate grace time is not negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Grace time cannot be negative")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        plandatetime = attrs.get('plandatetime')
        expirydatetime = attrs.get('expirydatetime')

        if plandatetime and expirydatetime:
            if expirydatetime <= plandatetime:
                raise serializers.ValidationError(
                    {'expirydatetime': 'Expiry datetime must be after plan datetime'}
                )

        starttime = attrs.get('starttime')
        endtime = attrs.get('endtime')

        if starttime and endtime:
            if endtime <= starttime:
                logger.info("Task spans across days")

        return attrs


class JobneedDetailsSerializers(ValidatedModelSerializer):
    """
    Secure JobneedDetails serializer with comprehensive validation.
    """

    class Meta:
        model = JobneedDetails
        fields = [
            'id',
            'uuid',
            'jobneed',
            'question',
            'qset',
            'seqno',
            'answertype',
            'answer',
            'options',
            'min',
            'max',
            'alerton',
            'isavpt',
            'avpttype',
            'ismandatory',
            'alerts',
            'attachmentcount',
            'cuser',
            'muser',
            'ctzoffset',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

    def validate_seqno(self, value):
        """Validate sequence number is positive."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Sequence number must be positive")
        return value

    def validate_attachmentcount(self, value):
        """Validate attachment count is not negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Attachment count cannot be negative")
        return value


class QuestionSerializers(ValidatedModelSerializer):
    """
    Secure Question serializer (schedhuler-specific).
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


class QuestionSetSerializers(ValidatedModelSerializer):
    """
    Secure QuestionSet serializer (schedhuler-specific).
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


class QuestionSetBelongingSerializers(ValidatedModelSerializer):
    """
    Secure QuestionSetBelonging serializer (schedhuler-specific).
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