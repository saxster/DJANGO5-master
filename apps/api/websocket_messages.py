"""
Pydantic Models for WebSocket Messages

Type-safe WebSocket message definitions for mobile SDK synchronization.
Enables Kotlin/Swift codegen for sealed classes/enums.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines (split by message category)
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin sealed class generation:
    sealed class WebSocketMessage {
        data class Connection(...) : WebSocketMessage()
        data class SyncStart(...) : WebSocketMessage()
        ...
    }
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Union, Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


# ============================================================================
# BASE MESSAGE MODEL
# ============================================================================

class BaseWebSocketMessage(BaseModel):
    """
    Base class for all WebSocket messages.

    All messages must have a 'type' field for routing.
    """
    type: str = Field(..., min_length=1, max_length=100, description="Message type identifier")

    class Config:
        frozen = False  # Allow mutation for processing
        str_strip_whitespace = True


# ============================================================================
# CONNECTION MESSAGES (Server → Client)
# ============================================================================

class ConnectionEstablishedMessage(BaseWebSocketMessage):
    """
    Sent by server after successful WebSocket connection.

    Kotlin mapping:
        data class ConnectionEstablished(
            val userId: String,
            val deviceId: String,
            val serverTime: Instant,
            val features: ConnectionFeatures
        )
    """
    type: Literal['connection_established'] = 'connection_established'
    user_id: str = Field(..., description="Authenticated user ID")
    device_id: str = Field(..., description="Connected device ID")
    server_time: datetime = Field(..., description="Server timestamp (ISO 8601)")
    features: Dict[str, bool] = Field(
        default_factory=dict,
        description="Enabled features (real_time_sync, push_notifications, etc.)"
    )


class HeartbeatMessage(BaseWebSocketMessage):
    """
    Periodic heartbeat to maintain connection.

    Kotlin mapping:
        data class Heartbeat(val timestamp: Instant)
    """
    type: Literal['heartbeat'] = 'heartbeat'
    timestamp: datetime = Field(..., description="Server timestamp")


class HeartbeatAckMessage(BaseWebSocketMessage):
    """
    Server heartbeat acknowledgment.

    Sent by server in response to client heartbeat.

    Kotlin mapping:
        data class HeartbeatAck(val timestamp: Instant)
    """
    type: Literal['heartbeat_ack'] = 'heartbeat_ack'
    timestamp: datetime = Field(..., description="Server timestamp")


# ============================================================================
# SYNC MESSAGES (Client → Server)
# ============================================================================

class SyncStartMessage(BaseWebSocketMessage):
    """
    Client initiates sync for a specific domain.

    Kotlin mapping:
        data class SyncStart(
            val domain: SyncDomain,
            val sinceTimestamp: Instant?,
            val fullSync: Boolean
        )
    """
    type: Literal['start_sync'] = 'start_sync'
    domain: Literal['voice', 'attendance', 'task', 'journal', 'ticket'] = Field(
        ...,
        description="Data domain to sync"
    )
    since_timestamp: Optional[datetime] = Field(
        None,
        description="Last sync timestamp (null for full sync)"
    )
    full_sync: bool = Field(default=False, description="Whether to perform full sync")
    device_id: str = Field(..., description="Device identifier")


class SyncDataMessage(BaseWebSocketMessage):
    """
    Client sends sync data payload.

    Kotlin mapping:
        data class SyncData(
            val payload: JsonObject,
            val idempotencyKey: String,
            val domain: SyncDomain
        )
    """
    type: Literal['sync_data'] = 'sync_data'
    payload: Dict[str, Any] = Field(..., description="Sync data payload")
    idempotency_key: str = Field(..., min_length=16, description="Idempotency key")
    domain: str = Field(..., description="Data domain")
    client_timestamp: datetime = Field(..., description="Client timestamp")


class SyncCompleteMessage(BaseWebSocketMessage):
    """
    Client signals sync completion for a domain.

    Kotlin mapping:
        data class SyncComplete(
            val domain: SyncDomain,
            val itemCount: Int
        )
    """
    type: Literal['sync_complete'] = 'sync_complete'
    domain: str = Field(..., description="Data domain")
    item_count: int = Field(..., ge=0, description="Number of items synced")


# ============================================================================
# SERVER MESSAGES (Server → Client)
# ============================================================================

class ServerDataRequestMessage(BaseWebSocketMessage):
    """
    Server requests specific data from client.

    Kotlin mapping:
        data class ServerDataRequest(
            val domain: SyncDomain,
            val entityIds: List<String>
        )
    """
    type: Literal['server_data_request'] = 'server_data_request'
    domain: str = Field(..., description="Data domain")
    entity_ids: List[str] = Field(..., description="Requested entity IDs")
    request_id: str = Field(..., description="Request ID for correlation")


class ServerDataMessage(BaseWebSocketMessage):
    """
    Server pushes data to client (delta sync, notifications).

    Kotlin mapping:
        data class ServerData(
            val domain: SyncDomain,
            val data: List<JsonObject>,
            val nextSyncToken: String?
        )
    """
    type: Literal['server_data'] = 'server_data'
    domain: str = Field(..., description="Data domain")
    data: List[Dict[str, Any]] = Field(..., description="Server data items")
    next_sync_token: Optional[str] = Field(None, description="Token for next delta sync")
    server_timestamp: datetime = Field(..., description="Server timestamp")


class ConflictNotificationMessage(BaseWebSocketMessage):
    """
    Server notifies client of sync conflicts.

    Kotlin mapping:
        data class ConflictNotification(
            val conflicts: List<ConflictItem>,
            val resolutionRequired: Boolean
        )
    """
    type: Literal['conflict_notification'] = 'conflict_notification'
    conflicts: List[Dict[str, Any]] = Field(..., description="Conflict details")
    resolution_required: bool = Field(..., description="Whether manual resolution needed")
    conflict_ids: List[str] = Field(..., description="Conflict identifiers")


# ============================================================================
# CONFLICT RESOLUTION MESSAGES
# ============================================================================

class ConflictResolutionMessage(BaseWebSocketMessage):
    """
    Client provides manual conflict resolution.

    Kotlin mapping:
        data class ConflictResolution(
            val conflictId: String,
            val strategy: ResolutionStrategy,
            val data: JsonObject?
        )
    """
    type: Literal['conflict_resolution'] = 'conflict_resolution'
    conflict_id: str = Field(..., description="Conflict ID to resolve")
    strategy: Literal[
        'client_wins', 'server_wins', 'merge', 'manual'
    ] = Field(..., description="Resolution strategy")
    data: Optional[Dict[str, Any]] = Field(None, description="Resolution data if strategy=manual")


# ============================================================================
# ERROR MESSAGES (Server → Client)
# ============================================================================

class ErrorMessage(BaseWebSocketMessage):
    """
    Server reports error to client.

    Kotlin mapping:
        data class Error(
            val errorCode: ErrorCode,
            val message: String,
            val retryable: Boolean,
            val details: Map<String, Any>?
        )
    """
    type: Literal['error'] = 'error'
    error_code: str = Field(..., description="Error code (RATE_LIMIT_EXCEEDED, etc.)")
    message: str = Field(..., description="Human-readable error message")
    retryable: bool = Field(default=True, description="Whether client should retry")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")


# ============================================================================
# STATUS MESSAGES
# ============================================================================

class SyncStatusMessage(BaseWebSocketMessage):
    """
    Server provides sync status update.

    Kotlin mapping:
        data class SyncStatus(
            val domain: SyncDomain,
            val status: SyncStatus,
            val progress: SyncProgress
        )
    """
    type: Literal['sync_status'] = 'sync_status'
    domain: str = Field(..., description="Data domain")
    status: Literal['pending', 'in_progress', 'completed', 'failed'] = Field(
        ...,
        description="Current sync status"
    )
    progress: Dict[str, Any] = Field(
        default_factory=dict,
        description="Progress details (processed, total, etc.)"
    )


# ============================================================================
# UNION TYPE FOR ALL MESSAGES
# ============================================================================

WebSocketMessage = Union[
    # Connection
    ConnectionEstablishedMessage,
    HeartbeatMessage,
    HeartbeatAckMessage,
    # Sync - Client to Server
    SyncStartMessage,
    SyncDataMessage,
    SyncCompleteMessage,
    # Sync - Server to Client
    ServerDataRequestMessage,
    ServerDataMessage,
    ConflictNotificationMessage,
    SyncStatusMessage,
    # Conflict Resolution
    ConflictResolutionMessage,
    # Error
    ErrorMessage,
]


# ============================================================================
# MESSAGE TYPE REGISTRY (for validation)
# ============================================================================

MESSAGE_TYPE_MAP = {
    'connection_established': ConnectionEstablishedMessage,
    'heartbeat': HeartbeatMessage,
    'heartbeat_ack': HeartbeatAckMessage,
    'start_sync': SyncStartMessage,
    'sync_data': SyncDataMessage,
    'sync_complete': SyncCompleteMessage,
    'server_data_request': ServerDataRequestMessage,
    'server_data': ServerDataMessage,
    'conflict_notification': ConflictNotificationMessage,
    'conflict_resolution': ConflictResolutionMessage,
    'sync_status': SyncStatusMessage,
    'error': ErrorMessage,
}


def parse_websocket_message(raw_data: Dict[str, Any]) -> WebSocketMessage:
    """
    Parse and validate WebSocket message from raw data.

    Args:
        raw_data: Raw message dictionary (from JSON.parse)

    Returns:
        Validated Pydantic message model

    Raises:
        ValidationError: If message type unknown or validation fails
        KeyError: If 'type' field missing

    Example:
        >>> raw = {'type': 'heartbeat', 'timestamp': '2025-10-05T12:00:00Z'}
        >>> message = parse_websocket_message(raw)
        >>> isinstance(message, HeartbeatMessage)
        True
    """
    message_type = raw_data.get('type')
    if not message_type:
        raise KeyError("Message must have a 'type' field")

    model_class = MESSAGE_TYPE_MAP.get(message_type)
    if not model_class:
        raise ValueError(f"Unknown message type: {message_type}")

    return model_class.model_validate(raw_data)


__all__ = [
    # Base
    'BaseWebSocketMessage',
    # Connection
    'ConnectionEstablishedMessage',
    'HeartbeatMessage',
    'HeartbeatAckMessage',
    # Sync
    'SyncStartMessage',
    'SyncDataMessage',
    'SyncCompleteMessage',
    'ServerDataRequestMessage',
    'ServerDataMessage',
    'ConflictNotificationMessage',
    'SyncStatusMessage',
    # Conflict
    'ConflictResolutionMessage',
    # Error
    'ErrorMessage',
    # Union
    'WebSocketMessage',
    # Utilities
    'MESSAGE_TYPE_MAP',
    'parse_websocket_message',
]
