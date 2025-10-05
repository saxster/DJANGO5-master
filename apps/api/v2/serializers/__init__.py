"""
API v2 Serializers

Type-safe serializers for REST v2 endpoints with Pydantic validation.

Following .claude/rules.md:
- Rule #7: Serializers < 100 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns
"""

from .sync_serializers import (
    VoiceSyncRequestSerializer,
    VoiceSyncResponseSerializer,
    BatchSyncRequestSerializer,
    BatchSyncResponseSerializer,
)

from .device_serializers import (
    DeviceListResponseSerializer,
    DeviceRegisterRequestSerializer,
    DeviceRegisterResponseSerializer,
    DeviceSyncStateResponseSerializer,
)

__all__ = [
    # Sync serializers
    'VoiceSyncRequestSerializer',
    'VoiceSyncResponseSerializer',
    'BatchSyncRequestSerializer',
    'BatchSyncResponseSerializer',
    # Device serializers
    'DeviceListResponseSerializer',
    'DeviceRegisterRequestSerializer',
    'DeviceRegisterResponseSerializer',
    'DeviceSyncStateResponseSerializer',
]
