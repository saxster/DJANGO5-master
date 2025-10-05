"""
DRF Serializers for API v2 Device Management

Type-safe REST serializers using Pydantic validation.
Provides comprehensive validation and Kotlin/Swift codegen compatibility.

Compliance with .claude/rules.md:
- Rule #7: Serializers < 100 lines (focused, single responsibility)
- Rule #10: Comprehensive validation (via Pydantic)
- Rule #13: Required validation patterns
"""

from rest_framework import serializers
from typing import List

from apps.core.serializers.pydantic_integration import PydanticSerializerMixin
from apps.api.v2.pydantic_models import (
    DeviceListResponseModel,
    DeviceRegisterRequestModel,
    DeviceRegisterResponseModel,
    DeviceSyncStateResponseModel,
    DeviceItemModel,
    DeviceSyncStateItemModel,
)


# ============================================================================
# DEVICE ITEM SERIALIZERS
# ============================================================================

class DeviceItemSerializer(serializers.Serializer):
    """Serializer for individual device in list."""
    device_id = serializers.CharField(help_text="Unique device identifier")
    device_type = serializers.ChoiceField(
        choices=['phone', 'tablet', 'laptop', 'desktop'],
        help_text="Device type"
    )
    priority = serializers.IntegerField(
        min_value=0,
        max_value=200,
        help_text="Conflict resolution priority"
    )
    device_name = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="User-friendly device name"
    )
    os_type = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Operating system type"
    )
    os_version = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Operating system version"
    )
    app_version = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Application version"
    )
    last_seen = serializers.DateTimeField(help_text="Last activity timestamp")
    is_active = serializers.BooleanField(help_text="Whether device is active")


class DeviceListResponseSerializer(PydanticSerializerMixin, serializers.Serializer):
    """Type-safe serializer for device list response."""

    pydantic_model = DeviceListResponseModel
    full_validation = True

    devices = DeviceItemSerializer(many=True, help_text="List of user devices")


# ============================================================================
# DEVICE REGISTRATION SERIALIZERS
# ============================================================================

class DeviceRegisterRequestSerializer(PydanticSerializerMixin, serializers.Serializer):
    """Type-safe serializer for device registration requests."""

    pydantic_model = DeviceRegisterRequestModel
    full_validation = True

    device_id = serializers.CharField(
        max_length=255,
        min_length=5,
        help_text="Unique device identifier (alphanumeric, hyphens, underscores only)"
    )
    device_type = serializers.ChoiceField(
        choices=['phone', 'tablet', 'laptop', 'desktop'],
        help_text="Device type"
    )
    device_name = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=255,
        help_text="User-friendly device name"
    )
    os_type = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=50,
        help_text="Operating system type"
    )
    os_version = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=50,
        help_text="Operating system version"
    )
    app_version = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=50,
        help_text="Application version"
    )


class DeviceRegisterResponseSerializer(PydanticSerializerMixin, serializers.Serializer):
    """Type-safe serializer for device registration responses."""

    pydantic_model = DeviceRegisterResponseModel
    full_validation = True

    device_id = serializers.CharField(help_text="Registered device identifier")
    priority = serializers.IntegerField(help_text="Assigned conflict resolution priority")
    status = serializers.ChoiceField(
        choices=['registered', 'updated'],
        help_text="Registration status"
    )


# ============================================================================
# DEVICE SYNC STATE SERIALIZERS
# ============================================================================

class DeviceSyncStateItemSerializer(serializers.Serializer):
    """Serializer for individual sync state item."""
    domain = serializers.CharField(help_text="Data domain")
    last_sync_version = serializers.IntegerField(
        min_value=0,
        help_text="Last synced version"
    )
    last_sync_timestamp = serializers.DateTimeField(help_text="When last synced")


class DeviceSyncStateResponseSerializer(PydanticSerializerMixin, serializers.Serializer):
    """Type-safe serializer for device sync state response."""

    pydantic_model = DeviceSyncStateResponseModel
    full_validation = True

    device_id = serializers.CharField(help_text="Device identifier")
    sync_state = DeviceSyncStateItemSerializer(
        many=True,
        help_text="Sync state per domain"
    )


__all__ = [
    'DeviceItemSerializer',
    'DeviceListResponseSerializer',
    'DeviceRegisterRequestSerializer',
    'DeviceRegisterResponseSerializer',
    'DeviceSyncStateItemSerializer',
    'DeviceSyncStateResponseSerializer',
]
