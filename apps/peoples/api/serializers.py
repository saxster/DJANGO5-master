"""
People Management REST API Serializers

Provides serializers for user profiles with split model architecture.

Compliance with .claude/rules.md:
- Serializer files < 100 lines each
- Specific validation
"""

from rest_framework import serializers
from apps.peoples.models import People
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class PeopleListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.

    Includes only essential fields for performance.
    """
    class Meta:
        model = People
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'bu_id', 'client_id', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']


class PeopleDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for detail views.

    Includes all user data with profile and organizational info.
    """
    # Add computed fields
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = People
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'is_staff', 'is_superuser',
            'bu_id', 'client_id', 'department', 'role',
            'phone', 'profile_image',
            'date_joined', 'last_login',
            'capabilities'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
        extra_kwargs = {
            'password': {'write_only': True},
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True},
        }

    def get_full_name(self, obj):
        """Return user's full name."""
        return f"{obj.first_name} {obj.last_name}".strip()


class PeopleCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users.

    Includes validation and secure handling.
    """
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = People
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone',
            'bu_id', 'client_id', 'department', 'role'
        ]

    def validate(self, attrs):
        """
        Validate input data.

        Checks:
        - Passwords match
        - Strength requirements met
        - Required fields present
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match'
            })

        # Validate strength
        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({
                'password': list(e.messages)
            })

        return attrs

    def create(self, validated_data):
        """
        Create new user with proper handling.

        Args:
            validated_data: Validated input data

        Returns:
            People: Created user instance
        """
        # Remove confirmation field
        validated_data.pop('password_confirm')

        # Extract and hash password
        password = validated_data.pop('password')

        # Create user
        user = People.objects.create_user(
            password=password,
            **validated_data
        )

        return user


class PeopleUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing users.

    Partial updates allowed.
    """
    class Meta:
        model = People
        fields = [
            'email', 'first_name', 'last_name', 'phone',
            'department', 'role', 'is_active'
        ]


class PeopleCapabilitiesSerializer(serializers.ModelSerializer):
    """
    Serializer for managing user capabilities.

    Admin-only access.
    """
    class Meta:
        model = People
        fields = ['id', 'username', 'capabilities']
        read_only_fields = ['id', 'username']

    def validate_capabilities(self, value):
        """
        Validate capabilities JSON structure.

        Args:
            value: Capabilities dict

        Returns:
            dict: Validated capabilities

        Raises:
            ValidationError: If format is invalid
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Capabilities must be a JSON object'
            )

        # Validate all values are boolean
        for key, val in value.items():
            if not isinstance(val, bool):
                raise serializers.ValidationError(
                    f'Capability "{key}" must be a boolean value'
                )

        return value


__all__ = [
    'PeopleListSerializer',
    'PeopleDetailSerializer',
    'PeopleCreateSerializer',
    'PeopleUpdateSerializer',
    'PeopleCapabilitiesSerializer',
]
