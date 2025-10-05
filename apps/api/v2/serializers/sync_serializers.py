"""
DRF Serializers for API v2 Sync Operations

Type-safe REST serializers using Pydantic validation.
Provides comprehensive validation and Kotlin/Swift codegen compatibility.

Compliance with .claude/rules.md:
- Rule #7: Serializers < 100 lines (focused, single responsibility)
- Rule #10: Comprehensive validation (via Pydantic)
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns

Integration:
- Uses PydanticSerializerMixin for automatic validation
- Generates OpenAPI schema for Kotlin codegen
- Backward compatible with existing v2 views
"""

from rest_framework import serializers
from django.utils import timezone
from typing import List, Dict, Any, Optional
from uuid import UUID

from apps.core.serializers.pydantic_integration import PydanticSerializerMixin
from apps.api.v2.pydantic_models import (
    VoiceSyncDataModel,
    VoiceSyncResponseModel,
    BatchSyncDataModel,
    BatchSyncResponseModel,
    VoiceDataItem,
    SyncBatchItem,
)


# ============================================================================
# VOICE SYNC SERIALIZERS
# ============================================================================

class VoiceDataItemSerializer(serializers.Serializer):
    """
    Serializer for individual voice verification record.

    Maps to VoiceDataItem Pydantic model.
    """
    verification_id = serializers.CharField(
        max_length=255,
        help_text="Unique verification identifier"
    )
    timestamp = serializers.DateTimeField(
        help_text="When verification occurred (ISO 8601)"
    )
    verified = serializers.BooleanField(
        help_text="Whether voice was verified successfully"
    )
    confidence_score = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0.0,
        max_value=1.0,
        help_text="Confidence score (0.0-1.0)"
    )
    quality_score = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0.0,
        max_value=1.0,
        help_text="Audio quality score (0.0-1.0)"
    )
    processing_time_ms = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Processing time in milliseconds"
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Additional metadata"
    )


class VoiceSyncRequestSerializer(PydanticSerializerMixin, serializers.Serializer):
    """
    Type-safe serializer for voice sync requests.

    Validates incoming voice verification data using Pydantic model.
    Generates OpenAPI schema for Kotlin codegen.
    """

    # Specify Pydantic model for validation
    pydantic_model = VoiceSyncDataModel
    full_validation = True

    # DRF field definitions (for OpenAPI schema generation)
    device_id = serializers.CharField(
        max_length=255,
        min_length=5,
        help_text="Unique device identifier (alphanumeric, hyphens, underscores only)"
    )
    voice_data = VoiceDataItemSerializer(
        many=True,
        min_length=1,
        max_length=100,
        help_text="Voice verification records (1-100 items)"
    )
    timestamp = serializers.DateTimeField(
        help_text="Client sync timestamp (ISO 8601)"
    )
    idempotency_key = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=255,
        min_length=16,
        help_text="Idempotency key for retry safety (optional but recommended)"
    )
    client_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Client ID for multi-tenant isolation"
    )
    bu_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Business Unit ID for multi-tenant isolation"
    )


class VoiceSyncResponseSerializer(serializers.Serializer):
    """
    Serializer for voice sync responses.

    Structured response for mobile clients after voice sync.
    """
    status = serializers.ChoiceField(
        choices=['success', 'partial', 'failed'],
        help_text="Overall sync status"
    )
    synced_count = serializers.IntegerField(
        min_value=0,
        help_text="Number of successfully synced items"
    )
    conflict_count = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="Number of conflicted items"
    )
    error_count = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="Number of failed items"
    )
    results = serializers.ListField(
        child=serializers.DictField(),
        default=list,
        help_text="Per-item results with status and errors"
    )
    server_timestamp = serializers.DateTimeField(
        default=timezone.now,
        help_text="Server processing timestamp"
    )
    prediction = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="ML conflict prediction data (if conflict risk detected)"
    )
    recommendation = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Recommended action from ML predictor"
    )


# ============================================================================
# BATCH SYNC SERIALIZERS
# ============================================================================

class SyncBatchItemSerializer(serializers.Serializer):
    """
    Serializer for individual batch item.

    Flexible schema for different entity types.
    """
    mobile_id = serializers.UUIDField(
        help_text="Client-generated unique identifier (UUID)"
    )
    entity_type = serializers.CharField(
        max_length=50,
        help_text="Type of entity (task, attendance, journal, ticket, work_order, etc.)"
    )
    operation = serializers.ChoiceField(
        choices=['create', 'update', 'delete'],
        help_text="Operation to perform"
    )
    version = serializers.IntegerField(
        min_value=1,
        help_text="Client version number (for conflict detection)"
    )
    data = serializers.JSONField(
        help_text="Entity data payload (structure varies by entity_type)"
    )
    client_timestamp = serializers.DateTimeField(
        help_text="When client created this change"
    )


class BatchSyncRequestSerializer(PydanticSerializerMixin, serializers.Serializer):
    """
    Type-safe serializer for batch sync requests.

    Handles multiple entity types in a single sync batch.
    """

    # Specify Pydantic model for validation
    pydantic_model = BatchSyncDataModel
    full_validation = True

    # DRF field definitions (for OpenAPI schema generation)
    device_id = serializers.CharField(
        max_length=255,
        min_length=5,
        help_text="Unique device identifier"
    )
    items = SyncBatchItemSerializer(
        many=True,
        min_length=1,
        max_length=1000,
        help_text="Batch items (1-1000 items)"
    )
    idempotency_key = serializers.CharField(
        max_length=255,
        min_length=16,
        help_text="Idempotency key (REQUIRED for batch operations)"
    )
    client_timestamp = serializers.DateTimeField(
        help_text="Client sync timestamp"
    )
    full_sync = serializers.BooleanField(
        default=False,
        help_text="Whether this is a full sync or delta sync"
    )
    client_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Client ID for multi-tenant isolation"
    )
    bu_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Business Unit ID for multi-tenant isolation"
    )


class BatchSyncResponseSerializer(serializers.Serializer):
    """
    Serializer for batch sync responses.

    Provides detailed results for each item in the batch.
    """
    status = serializers.ChoiceField(
        choices=['success', 'partial', 'failed'],
        help_text="Overall sync status"
    )
    total_items = serializers.IntegerField(
        min_value=0,
        help_text="Total number of items in batch"
    )
    synced_count = serializers.IntegerField(
        min_value=0,
        help_text="Number of successfully synced items"
    )
    conflict_count = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="Number of conflicted items"
    )
    error_count = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="Number of failed items"
    )
    results = serializers.ListField(
        child=serializers.DictField(),
        default=list,
        help_text="Per-item results with mobile_id, status, errors"
    )
    server_timestamp = serializers.DateTimeField(
        default=timezone.now,
        help_text="Server processing timestamp"
    )
    next_sync_token = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Token for next delta sync request"
    )


__all__ = [
    'VoiceDataItemSerializer',
    'VoiceSyncRequestSerializer',
    'VoiceSyncResponseSerializer',
    'SyncBatchItemSerializer',
    'BatchSyncRequestSerializer',
    'BatchSyncResponseSerializer',
]
