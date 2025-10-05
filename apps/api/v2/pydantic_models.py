"""
Pydantic Models for API v2

Type-safe data models for REST v2 endpoints with comprehensive validation.
These models serve as the single source of truth for Kotlin/Swift codegen.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines (split by domain)
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, validator, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID

from apps.core.validation.pydantic_base import (
    BaseDjangoModel,
    BusinessLogicModel,
    TenantAwareModel,
)


# ============================================================================
# VOICE SYNC MODELS
# ============================================================================

class VoiceDataItem(BaseModel):
    """
    Individual voice verification record.

    Maps to VoiceVerificationLog model.
    """
    verification_id: str = Field(..., min_length=1, max_length=255, description="Unique verification identifier")
    timestamp: datetime = Field(..., description="When verification occurred (ISO 8601)")
    verified: bool = Field(..., description="Whether voice was verified successfully")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Audio quality score (0.0-1.0)")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing time in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp_not_future(cls, v: datetime) -> datetime:
        """Ensure timestamp is not in the future."""
        from django.utils import timezone
        if v > timezone.now():
            raise ValueError("Timestamp cannot be in the future")
        return v


class VoiceSyncDataModel(TenantAwareModel):
    """
    Request model for voice sync operations.

    Validates voice verification data from mobile clients.
    """
    device_id: str = Field(..., min_length=5, max_length=255, description="Unique device identifier")
    voice_data: List[VoiceDataItem] = Field(..., min_items=1, max_items=100, description="Voice verification records (max 100)")
    timestamp: datetime = Field(..., description="Client sync timestamp (ISO 8601)")
    idempotency_key: Optional[str] = Field(None, min_length=16, max_length=255, description="Idempotency key for retry safety")

    @field_validator('device_id')
    @classmethod
    def validate_device_id_format(cls, v: str) -> str:
        """Validate device ID format (alphanumeric, hyphens, underscores only)."""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("device_id must contain only alphanumeric characters, hyphens, and underscores")
        return v


class VoiceSyncResultItem(BaseModel):
    """Individual voice sync result."""
    verification_id: str
    status: Literal['synced', 'conflict', 'error']
    server_id: Optional[int] = None
    error_message: Optional[str] = None


class VoiceSyncResponseModel(BaseModel):
    """
    Response model for voice sync operations.

    Returned to mobile clients after voice sync.
    """
    status: Literal['success', 'partial', 'failed'] = Field(..., description="Overall sync status")
    synced_count: int = Field(..., ge=0, description="Number of successfully synced items")
    conflict_count: int = Field(default=0, ge=0, description="Number of conflicted items")
    error_count: int = Field(default=0, ge=0, description="Number of failed items")
    results: List[VoiceSyncResultItem] = Field(default_factory=list, description="Per-item results")
    server_timestamp: datetime = Field(..., description="Server processing timestamp")
    prediction: Optional[Dict[str, Any]] = Field(None, description="ML conflict prediction data")
    recommendation: Optional[str] = Field(None, description="Recommended action from ML predictor")


# ============================================================================
# BATCH SYNC MODELS
# ============================================================================

class SyncBatchItemType(str):
    """Enum for batch item types (for Kotlin sealed class generation)."""
    TASK = "task"
    ATTENDANCE = "attendance"
    JOURNAL = "journal"
    TICKET = "ticket"
    WORK_ORDER = "work_order"


class SyncBatchItem(BaseModel):
    """
    Individual item in batch sync.

    Flexible schema for different entity types.
    """
    mobile_id: UUID = Field(..., description="Client-generated unique identifier")
    entity_type: str = Field(..., min_length=1, max_length=50, description="Type of entity (task, attendance, etc.)")
    operation: Literal['create', 'update', 'delete'] = Field(..., description="Operation to perform")
    version: int = Field(..., ge=1, description="Client version number (for conflict detection)")
    data: Dict[str, Any] = Field(..., description="Entity data payload")
    client_timestamp: datetime = Field(..., description="When client created this change")

    @field_validator('entity_type')
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate entity type is supported."""
        allowed_types = {'task', 'attendance', 'journal', 'ticket', 'work_order', 'asset', 'location'}
        if v.lower() not in allowed_types:
            raise ValueError(f"entity_type must be one of: {', '.join(sorted(allowed_types))}")
        return v.lower()


class BatchSyncDataModel(TenantAwareModel):
    """
    Request model for batch sync operations.

    Handles multiple entity types in a single sync batch.
    """
    device_id: str = Field(..., min_length=5, max_length=255, description="Unique device identifier")
    items: List[SyncBatchItem] = Field(..., min_items=1, max_items=1000, description="Batch items (max 1000)")
    idempotency_key: str = Field(..., min_length=16, max_length=255, description="Idempotency key (required)")
    client_timestamp: datetime = Field(..., description="Client sync timestamp")
    full_sync: bool = Field(default=False, description="Whether this is a full sync or delta")

    @field_validator('device_id')
    @classmethod
    def validate_device_id_format(cls, v: str) -> str:
        """Validate device ID format."""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("device_id must contain only alphanumeric characters, hyphens, and underscores")
        return v


class BatchSyncResultItem(BaseModel):
    """Individual batch item result."""
    mobile_id: UUID
    status: Literal['synced', 'conflict', 'error']
    server_id: Optional[int] = None
    server_version: Optional[int] = None
    conflict_reason: Optional[str] = None
    error_message: Optional[str] = None


class BatchSyncResponseModel(BaseModel):
    """
    Response model for batch sync operations.

    Provides detailed results for each item in the batch.
    """
    status: Literal['success', 'partial', 'failed']
    total_items: int = Field(..., ge=0)
    synced_count: int = Field(..., ge=0)
    conflict_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    results: List[BatchSyncResultItem] = Field(default_factory=list)
    server_timestamp: datetime
    next_sync_token: Optional[str] = Field(None, description="Token for delta sync")


# ============================================================================
# ML PREDICTION MODELS
# ============================================================================

class ConflictPredictionModel(BaseModel):
    """
    ML conflict prediction response.

    Returned when ML predictor detects high conflict risk.
    """
    risk_level: Literal['low', 'medium', 'high']
    confidence: float = Field(..., ge=0.0, le=1.0)
    predicted_conflicts: List[str] = Field(default_factory=list)
    recommendation: str
    factors: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# DEVICE MANAGEMENT MODELS
# ============================================================================

class DeviceItemModel(BaseModel):
    """
    Individual device in user's device list.

    Maps to UserDevice model.
    """
    device_id: str = Field(..., description="Unique device identifier")
    device_type: Literal['phone', 'tablet', 'laptop', 'desktop'] = Field(..., description="Device type")
    priority: int = Field(..., ge=0, le=200, description="Conflict resolution priority (0-200)")
    device_name: Optional[str] = Field(None, description="User-friendly device name")
    os_type: Optional[str] = Field(None, description="Operating system type")
    os_version: Optional[str] = Field(None, description="Operating system version")
    app_version: Optional[str] = Field(None, description="Application version")
    last_seen: datetime = Field(..., description="Last activity timestamp")
    is_active: bool = Field(..., description="Whether device is active")


class DeviceListResponseModel(BaseModel):
    """
    Response model for device list endpoint.

    Returns all devices belonging to authenticated user.
    """
    devices: List[DeviceItemModel] = Field(..., description="List of user devices")


class DeviceRegisterRequestModel(BaseModel):
    """
    Request model for device registration.

    Validates device registration payload from mobile clients.
    """
    device_id: str = Field(..., min_length=5, max_length=255, description="Unique device identifier")
    device_type: Literal['phone', 'tablet', 'laptop', 'desktop'] = Field(..., description="Device type")
    device_name: Optional[str] = Field(None, max_length=255, description="User-friendly device name")
    os_type: Optional[str] = Field(None, max_length=50, description="Operating system type")
    os_version: Optional[str] = Field(None, max_length=50, description="Operating system version")
    app_version: Optional[str] = Field(None, max_length=50, description="Application version")

    @field_validator('device_id')
    @classmethod
    def validate_device_id_format(cls, v: str) -> str:
        """Validate device ID format (alphanumeric, hyphens, underscores only)."""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("device_id must contain only alphanumeric characters, hyphens, and underscores")
        return v


class DeviceRegisterResponseModel(BaseModel):
    """
    Response model for device registration.

    Returns registration result with assigned priority.
    """
    device_id: str = Field(..., description="Registered device identifier")
    priority: int = Field(..., description="Assigned conflict resolution priority")
    status: Literal['registered', 'updated'] = Field(..., description="Registration status")


class DeviceSyncStateItemModel(BaseModel):
    """Individual sync state for a domain."""
    domain: str = Field(..., description="Data domain")
    last_sync_version: int = Field(..., ge=0, description="Last synced version")
    last_sync_timestamp: datetime = Field(..., description="When last synced")


class DeviceSyncStateResponseModel(BaseModel):
    """
    Response model for device sync state.

    Returns sync state for all domains on a device.
    """
    device_id: str = Field(..., description="Device identifier")
    sync_state: List[DeviceSyncStateItemModel] = Field(default_factory=list, description="Sync state per domain")


__all__ = [
    # Voice Sync
    'VoiceDataItem',
    'VoiceSyncDataModel',
    'VoiceSyncResultItem',
    'VoiceSyncResponseModel',
    # Batch Sync
    'SyncBatchItem',
    'BatchSyncDataModel',
    'BatchSyncResultItem',
    'BatchSyncResponseModel',
    # ML
    'ConflictPredictionModel',
    # Device Management
    'DeviceItemModel',
    'DeviceListResponseModel',
    'DeviceRegisterRequestModel',
    'DeviceRegisterResponseModel',
    'DeviceSyncStateItemModel',
    'DeviceSyncStateResponseModel',
]
