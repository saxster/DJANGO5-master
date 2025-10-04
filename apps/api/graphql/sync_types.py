"""
GraphQL Types for Mobile Sync System

Defines all GraphQL types, inputs, and enums for sync operations.

Follows .claude/rules.md:
- Rule #1: GraphQL security protection (input validation)
- Rule #7: Keep type definitions focused and under 200 lines
- Rule #11: Specific error types
"""

import graphene
from graphene import ObjectType, InputObjectType, Enum, Field, List, String, Int, Float, Boolean, ID
from datetime import datetime


class SyncDomainEnum(Enum):
    """Data domains that can be synced."""
    JOURNAL = 'journal'
    ATTENDANCE = 'attendance'
    TASK = 'task'
    TICKET = 'ticket'
    WORK_ORDER = 'work_order'
    BEHAVIORAL = 'behavioral'
    SESSION = 'session'
    METRICS = 'metrics'


class SyncOperationEnum(Enum):
    """Sync operation types."""
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    SYNC = 'sync'


class ResolutionStrategyEnum(Enum):
    """Conflict resolution strategies."""
    CLIENT_WINS = 'client_wins'
    SERVER_WINS = 'server_wins'
    MOST_RECENT_WINS = 'most_recent_wins'
    PRESERVE_ESCALATION = 'preserve_escalation'
    MANUAL = 'manual'


class VoiceDataInput(InputObjectType):
    """Input type for voice verification data."""
    verification_id = ID(required=True)
    timestamp = String(required=True)
    verified = Boolean(required=True)
    confidence_score = Float()
    quality_score = Float()
    processing_time_ms = Int()
    metadata = graphene.JSONString()


class BehavioralDataInput(InputObjectType):
    """Input type for behavioral analytics data."""
    session_id = ID(required=True)
    events = List(graphene.JSONString, required=True)
    duration_ms = Int(required=True)
    user_interactions = Int()
    screen_changes = Int()
    metadata = graphene.JSONString()


class SessionDataInput(InputObjectType):
    """Input type for session tracking data."""
    session_id = ID(required=True)
    start_time = String(required=True)
    end_time = String()
    duration_ms = Int()
    activities = List(graphene.JSONString)
    metadata = graphene.JSONString()


class MetricsDataInput(InputObjectType):
    """Input type for performance metrics."""
    metric_type = String(required=True)
    value = Float(required=True)
    unit = String()
    timestamp = String(required=True)
    tags = graphene.JSONString()


class SyncBatchInput(InputObjectType):
    """Input type for batch sync operations."""
    idempotency_key = String(required=True)
    device_id = String(required=True)
    voice_data = List(VoiceDataInput)
    behavioral_data = List(BehavioralDataInput)
    session_data = List(SessionDataInput)
    metrics_data = List(MetricsDataInput)
    client_timestamp = String(required=True)
    metadata = graphene.JSONString()


class ConflictResolutionInput(InputObjectType):
    """Input type for manual conflict resolution."""
    conflict_id = ID(required=True)
    resolution_strategy = Field(ResolutionStrategyEnum, required=True)
    chosen_version = String(required=True)
    merge_data = graphene.JSONString()
    notes = String()


class SyncErrorType(ObjectType):
    """Type for sync errors."""
    code = String(required=True)
    message = String(required=True)
    field = String()
    item_id = String()
    details = graphene.JSONString()


class SyncItemResultType(ObjectType):
    """Result for individual sync item."""
    item_id = String(required=True)
    success = Boolean(required=True)
    error = Field(SyncErrorType)
    conflict_detected = Boolean(default_value=False)
    conflict_id = ID()


class ConflictType(ObjectType):
    """Type for conflict details."""
    conflict_id = ID(required=True)
    domain = Field(SyncDomainEnum, required=True)
    mobile_id = ID(required=True)
    server_version = Int(required=True)
    client_version = Int(required=True)
    resolution_strategy = Field(ResolutionStrategyEnum)
    resolution_required = Boolean(required=True)
    server_data = graphene.JSONString()
    client_data = graphene.JSONString()
    created_at = String(required=True)


class SyncMetricsType(ObjectType):
    """Performance metrics for sync operation."""
    total_items = Int(required=True)
    synced_items = Int(required=True)
    failed_items = Int(required=True)
    conflicts_detected = Int(default_value=0)
    duration_ms = Float(required=True)
    bandwidth_bytes = Int()
    cache_hit_rate = Float()


class SyncResponseType(ObjectType):
    """Response type for sync operations."""
    success = Boolean(required=True)
    synced_items = Int(required=True)
    failed_items = Int(default_value=0)
    conflicts = List(ConflictType, default_value=[])
    errors = List(SyncErrorType, default_value=[])
    metrics = Field(SyncMetricsType)
    server_timestamp = String(required=True)
    idempotency_key = String(required=True)


class SyncBatchResponseType(ObjectType):
    """Response type for batch sync operations."""
    success = Boolean(required=True)
    voice_sync_result = Field(SyncResponseType)
    behavioral_sync_result = Field(SyncResponseType)
    session_sync_result = Field(SyncResponseType)
    metrics_sync_result = Field(SyncResponseType)
    overall_metrics = Field(SyncMetricsType)
    warnings = List(String, default_value=[])


class ConflictResolutionResponseType(ObjectType):
    """Response type for conflict resolution."""
    success = Boolean(required=True)
    conflict_id = ID(required=True)
    resolution_result = String(required=True)
    winning_version = String()
    merge_details = graphene.JSONString()
    message = String()
    error = Field(SyncErrorType)


class DeviceInfoType(ObjectType):
    """Device information for sync context."""
    device_id = ID(required=True)
    device_type = String()
    last_sync_at = String()
    sync_count = Int()
    health_score = Float()


class SyncHealthType(ObjectType):
    """Sync health status."""
    status = String(required=True)
    success_rate = Float(required=True)
    avg_latency_ms = Float()
    conflict_rate = Float()
    last_sync_at = String()
    active_devices = List(DeviceInfoType)