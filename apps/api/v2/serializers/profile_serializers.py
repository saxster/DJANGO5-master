"""
Serializers for profile and onboarding endpoints.

These serializers provide schema-validated data contracts for mobile app integration,
ensuring exact alignment with Kotlin DTOs for profile management and onboarding flows.
"""
from rest_framework import serializers
from django.db import transaction
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational


class PeopleProfileSerializer(serializers.ModelSerializer):
    """
    Profile information for current user.

    Nested in ProfileRetrieveSerializer.
    """

    peopleimg = serializers.ImageField(allow_null=True, required=False)

    class Meta:
        model = PeopleProfile
        fields = [
            'peopleimg',
            'dateofbirth',
            'dateofjoin',
            'gender',
            'profile_completion_percentage',
        ]
        read_only_fields = ['profile_completion_percentage']


class PeopleOrganizationalSerializer(serializers.ModelSerializer):
    """
    Organizational information for current user.

    Nested in ProfileRetrieveSerializer.
    """

    location = serializers.StringRelatedField()
    department = serializers.StringRelatedField()
    designation = serializers.StringRelatedField()
    reportto = serializers.PrimaryKeyRelatedField(read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    bu = serializers.StringRelatedField()

    class Meta:
        model = PeopleOrganizational
        fields = [
            'location',
            'department',
            'designation',
            'reportto',
            'client',
            'bu',
        ]


class OnboardingStatusSerializer(serializers.Serializer):
    """
    Onboarding status nested in profile response.

    Read-only serializer for onboarding tracking fields.
    """

    first_login_completed = serializers.BooleanField()
    onboarding_completed_at = serializers.DateTimeField(allow_null=True)
    onboarding_skipped = serializers.BooleanField()


class ProfileRetrieveSerializer(serializers.ModelSerializer):
    """
    Complete user profile for GET /api/v2/people/profile/me/

    Matches mobile ProfileDto structure.
    Returns denormalized data from People + PeopleProfile + PeopleOrganizational.
    """

    full_name = serializers.SerializerMethodField()
    phone = serializers.CharField(source='mobno', allow_null=True, allow_blank=True)
    capabilities = serializers.SerializerMethodField()
    profile = PeopleProfileSerializer(source='peopleprofile', read_only=True)
    organizational = PeopleOrganizationalSerializer(source='peopleorganizational', read_only=True)
    onboarding_status = serializers.SerializerMethodField()

    class Meta:
        model = People
        fields = [
            'id',
            'username',
            'email',
            'full_name',
            'phone',
            'client_id',
            'tenant_id',
            'capabilities',
            'profile',
            'organizational',
            'onboarding_status',
        ]

    def get_full_name(self, obj):
        """Return user's full name."""
        return obj.peoplename

    def get_capabilities(self, obj):
        """Return all 13 capability flags."""
        return obj.get_all_capabilities()

    def get_onboarding_status(self, obj):
        """Return onboarding tracking fields."""
        return {
            'first_login_completed': obj.first_login_completed,
            'onboarding_completed_at': obj.onboarding_completed_at,
            'onboarding_skipped': obj.onboarding_skipped,
        }


class ProfileUpdateSerializer(serializers.Serializer):
    """
    Partial update for PATCH /api/v2/people/profile/me/

    Supports updating People, PeopleProfile, and PeopleOrganizational.
    All fields are optional (partial update).
    """

    email = serializers.EmailField(required=False)
    mobno = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # Profile fields (nested)
    profile = serializers.DictField(required=False)

    # Organizational fields (nested)
    organizational = serializers.DictField(required=False)

    def validate_profile(self, value):
        """Validate profile update data."""
        allowed_fields = {'gender', 'dateofbirth', 'dateofjoin', 'dateofreport'}
        invalid_fields = set(value.keys()) - allowed_fields
        if invalid_fields:
            raise serializers.ValidationError(f"Invalid fields: {invalid_fields}")

        # Validate date logic
        if 'dateofbirth' in value and 'dateofjoin' in value:
            from datetime import date
            dob = value['dateofbirth'] if isinstance(value['dateofbirth'], date) else None
            doj = value['dateofjoin'] if isinstance(value['dateofjoin'], date) else None

            if dob and doj and dob > doj:
                raise serializers.ValidationError("Date of joining cannot be before date of birth")

        return value

    def validate_organizational(self, value):
        """Validate organizational update data."""
        allowed_fields = {'location', 'department', 'designation'}
        invalid_fields = set(value.keys()) - allowed_fields
        if invalid_fields:
            raise serializers.ValidationError(f"Invalid fields: {invalid_fields}")

        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update People, Profile, and Organizational models atomically."""
        # Update People fields
        if 'email' in validated_data:
            instance.email = validated_data['email']
        if 'mobno' in validated_data:
            instance.mobno = validated_data['mobno']

        if 'email' in validated_data or 'mobno' in validated_data:
            instance.save()

        # Update Profile
        if 'profile' in validated_data:
            profile, created = PeopleProfile.objects.get_or_create(people=instance)
            for field, value in validated_data['profile'].items():
                setattr(profile, field, value)
            profile.save()

        # Update Organizational
        if 'organizational' in validated_data:
            if hasattr(instance, 'peopleorganizational'):
                org = instance.peopleorganizational
                for field, value in validated_data['organizational'].items():
                    setattr(org, field, value)
                org.save()

        return instance


class ProfileCompletionStatusSerializer(serializers.Serializer):
    """
    Response for GET /api/v2/people/profile/completion-status/

    Matches mobile ProfileCompletionDto exactly.
    All fields are required (mobile expects all keys).
    """

    is_complete = serializers.BooleanField()
    completion_percentage = serializers.IntegerField()
    missing_fields = serializers.ListField(
        child=serializers.DictField()
    )
    has_completed_onboarding = serializers.BooleanField()
    onboarding_completed_at = serializers.CharField(allow_null=True)
    onboarding_skipped = serializers.BooleanField()
    first_login_completed = serializers.BooleanField()
    can_skip_onboarding = serializers.BooleanField()
    required_documents = serializers.ListField(child=serializers.CharField())
    onboarding_workflow_state = serializers.CharField(allow_null=True)


class MarkOnboardingCompleteSerializer(serializers.Serializer):
    """
    Request body for POST /api/v2/people/profile/mark-onboarding-complete/

    Matches mobile MarkOnboardingCompleteRequestDto.
    """

    skipped = serializers.BooleanField()
    completed_steps = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list
    )


class MarkOnboardingCompleteResponseSerializer(serializers.Serializer):
    """
    Response for POST /api/v2/people/profile/mark-onboarding-complete/

    Matches mobile MarkOnboardingCompleteResponseDto.
    """

    success = serializers.BooleanField()
    onboarding_completed_at = serializers.CharField(allow_null=True)
    onboarding_skipped = serializers.BooleanField()
    first_login_completed = serializers.BooleanField()


class ProfileImageResponseSerializer(serializers.Serializer):
    """
    Response for POST /api/v2/people/profile/me/image/

    Matches mobile ProfileImageResponseDto.
    """

    image_url = serializers.URLField()
    profile_completion_percentage = serializers.IntegerField()
