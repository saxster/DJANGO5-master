# WebSocket Message Schema & Real-Time Sync Protocol

> **Purpose:** Complete WebSocket message definitions for offline-first sync
> **Version:** 1.0.0
> **Last Updated:** November 7, 2025
> **WebSocket URL:** `wss://api.intelliwiz.com/ws/sync/`

---

## 📋 Table of Contents

- [Overview](#overview)
- [Connection & Authentication](#connection--authentication)
- [Message Types](#message-types)
- [Sync Protocol](#sync-protocol)
- [Conflict Resolution](#conflict-resolution)
- [Complete Examples](#complete-examples)
- [Kotlin Implementation](#kotlin-implementation)

---

## Overview

### WebSocket Purpose

**Real-time bidirectional sync** for offline-first architecture:
- Client sends pending operations (create, update, delete)
- Server sends updates from other devices/users
- Heartbeat keeps connection alive
- Automatic reconnection with exponential backoff

### Django Implementation

- **Consumer:** `apps/core/consumers.py:SyncConsumer`
- **Authentication:** JWT token in query params
- **Protocol:** JSON messages with `type` field
- **Channels Layer:** Redis-backed channel layer

---

## Connection & Authentication

### WebSocket URL

**Format:**
```
wss://api.intelliwiz.com/ws/sync/?token={access_token}&client_id={client_id}&mobile_id={device_id}
```

**Parameters:**
- `token`: JWT access token (from login response)
- `client_id`: Tenant ID (from login response)
- `mobile_id`: Unique device identifier (UUID, persistent)

**Example:**
```
wss://api.intelliwiz.com/ws/sync/?token=eyJhbGc...&client_id=42&mobile_id=device-android-abc123
```

---

### Connection Lifecycle

```
1. Connect
   → Send JWT token
   → Server validates token + client_id
   → Server responds: CONNECTION_ACCEPTED

2. Start Sync
   → Client sends: SYNC_START
   → Server responds: SYNC_DATA (batch of updates)
   → Client responds: SYNC_ACK

3. Heartbeat (every 30 seconds)
   → Client sends: HEARTBEAT
   → Server responds: HEARTBEAT_ACK

4. Disconnect
   → Client sends: DISCONNECT
   → Server closes connection gracefully
```

---

## Message Types

### 1. Connection Messages

#### CONNECTION_ACCEPTED (Server → Client)

**Purpose:** Confirm successful authentication

**Schema:**
```json
{
  "type": "connection_accepted",
  "user_id": 123,
  "client_id": 42,
  "mobile_id": "device-android-abc123",
  "server_time": "2025-11-15T08:00:00Z",
  "sync_available": true,
  "pending_updates_count": 15,
  "correlation_id": "conn-abc123"
}
```

**Kotlin:**
```kotlin
@Serializable
data class ConnectionAcceptedMessage(
    @SerialName("type") val type: String = "connection_accepted",
    @SerialName("user_id") val userId: Long,
    @SerialName("client_id") val clientId: Long,
    @SerialName("mobile_id") val mobileId: String,
    @SerialName("server_time") val serverTime: Instant,
    @SerialName("sync_available") val syncAvailable: Boolean,
    @SerialName("pending_updates_count") val pendingUpdatesCount: Int,
    @SerialName("correlation_id") val correlationId: String
)
```

---

#### HEARTBEAT (Client → Server, every 30s)

**Purpose:** Keep connection alive, detect network issues

**Schema:**
```json
{
  "type": "heartbeat",
  "mobile_id": "device-android-abc123",
  "client_timestamp": "2025-11-15T08:00:30Z"
}
```

**Server Response (HEARTBEAT_ACK):**
```json
{
  "type": "heartbeat_ack",
  "server_time": "2025-11-15T08:00:30.123Z",
  "latency_ms": 123,
  "correlation_id": "hb-456"
}
```

---

### 2. Sync Messages

#### SYNC_START (Client → Server)

**Purpose:** Initiate sync session, tell server when client last synced

**Schema:**
```json
{
  "type": "sync_start",
  "mobile_id": "device-android-abc123",
  "last_sync_timestamp": "2025-11-14T18:00:00Z",
  "entity_types": ["job", "attendance", "journal", "ticket"],
  "pending_operations_count": 5,
  "correlation_id": "sync-start-789"
}
```

**Fields:**
- `mobile_id`: Device identifier (for multi-device sync)
- `last_sync_timestamp`: When client last synced successfully (server sends updates after this time)
- `entity_types`: Which entity types to sync (empty = all)
- `pending_operations_count`: How many local changes to upload

---

#### SYNC_DATA (Server → Client OR Client → Server)

**Purpose:** Send entity updates (create, update, delete operations)

**Schema (Server → Client):**
```json
{
  "type": "sync_data",
  "correlation_id": "sync-data-batch-001",
  "batch_number": 1,
  "total_batches": 3,
  "operations": [
    {
      "operation_id": "op-server-1001",
      "entity_type": "job",
      "entity_id": 5001,
      "operation": "update",
      "data": {
        "id": 5001,
        "title": "Updated Job Title",
        "status": "in_progress",
        "priority": "high",
        "version": 8,
        "updated_at": "2025-11-15T09:00:00Z",
        "updated_by": {"id": 456, "name": "Jane Smith"}
      },
      "version": 8,
      "timestamp": "2025-11-15T09:00:00Z",
      "updated_by": 456
    },
    {
      "operation_id": "op-server-1002",
      "entity_type": "attendance",
      "entity_id": 7001,
      "operation": "update",
      "data": {
        "id": 7001,
        "status": "completed",
        "checkout_time": "2025-11-15T16:10:00Z",
        "hours_worked": 8.08,
        "version": 2
      },
      "version": 2,
      "timestamp": "2025-11-15T16:10:00Z",
      "updated_by": 123
    },
    {
      "operation_id": "op-server-1003",
      "entity_type": "ticket",
      "entity_id": 9001,
      "operation": "create",
      "data": {
        "id": 9001,
        "ticket_number": "TKT-2025-11-9001",
        "subject": "New ticket assigned to you",
        "status": "new",
        "assigned_to": 123,
        "version": 1
      },
      "version": 1,
      "timestamp": "2025-11-15T10:00:00Z",
      "updated_by": 789
    }
  ],
  "server_time": "2025-11-15T10:00:00Z"
}
```

**Schema (Client → Server):**
```json
{
  "type": "sync_data",
  "correlation_id": "sync-upload-client-001",
  "mobile_id": "device-android-abc123",
  "operations": [
    {
      "operation_id": "op-mobile-temp-001",
      "entity_type": "job",
      "entity_id": "temp-job-uuid-123",
      "operation": "create",
      "data": {
        "title": "Created offline",
        "job_type": "inspection",
        "scheduled_start": "2025-11-16T09:00:00Z",
        "assigned_to": [123]
      },
      "timestamp": "2025-11-15T12:00:00Z",
      "created_by": 123
    },
    {
      "operation_id": "op-mobile-002",
      "entity_type": "job",
      "entity_id": 5001,
      "operation": "update",
      "data": {
        "id": 5001,
        "priority": "urgent",
        "version": 7
      },
      "version": 7,
      "timestamp": "2025-11-15T12:05:00Z",
      "updated_by": 123
    }
  ],
  "client_time": "2025-11-15T12:05:00Z"
}
```

---

#### SYNC_ACK (Client → Server OR Server → Client)

**Purpose:** Acknowledge receipt of SYNC_DATA batch

**Schema (Client → Server):**
```json
{
  "type": "sync_ack",
  "correlation_id": "sync-data-batch-001",
  "operations_received": 3,
  "operations_applied": 3,
  "operations_failed": 0,
  "failed_operations": [],
  "client_timestamp": "2025-11-15T10:00:01Z"
}
```

**Schema (Server → Client) - Confirming client uploads:**
```json
{
  "type": "sync_ack",
  "correlation_id": "sync-upload-client-001",
  "operations_received": 2,
  "operations_applied": 2,
  "operations_failed": 0,
  "id_mappings": [
    {
      "temp_id": "temp-job-uuid-123",
      "real_id": 5010,
      "entity_type": "job"
    }
  ],
  "conflicts": [],
  "server_timestamp": "2025-11-15T12:05:01Z"
}
```

**Important:** `id_mappings` tells client to update temp IDs → real IDs.

---

### 3. Conflict Messages

#### CONFLICT_DETECTED (Server → Client)

**Purpose:** Notify client of version conflict (optimistic locking failure)

**Schema:**
```json
{
  "type": "conflict_detected",
  "correlation_id": "conflict-789",
  "operation_id": "op-mobile-002",
  "entity_type": "job",
  "entity_id": 5001,
  "conflict_reason": "version_mismatch",
  "client_version": 7,
  "server_version": 9,
  "client_data": {
    "priority": "urgent",
    "updated_at": "2025-11-15T12:05:00Z"
  },
  "server_data": {
    "priority": "high",
    "title": "Updated Title",
    "updated_at": "2025-11-15T11:00:00Z",
    "updated_by": {"id": 456, "name": "Jane Smith"}
  },
  "server_timestamp": "2025-11-15T12:05:01Z"
}
```

**Client Must:**
1. Show conflict resolution UI
2. Display diff between client and server versions
3. User chooses: `keep_local`, `accept_server`, or `merge`
4. Send `CONFLICT_RESOLUTION` message

---

#### CONFLICT_RESOLUTION (Client → Server)

**Purpose:** Resolve detected conflict

**Schema:**
```json
{
  "type": "conflict_resolution",
  "correlation_id": "conflict-789",
  "operation_id": "op-mobile-002",
  "entity_type": "job",
  "entity_id": 5001,
  "resolution_strategy": "merge",
  "merged_data": {
    "id": 5001,
    "title": "Updated Title",
    "priority": "urgent",
    "version": 9
  },
  "client_timestamp": "2025-11-15T12:06:00Z"
}
```

**Resolution Strategies:**
- `keep_local`: Discard server version, force client version
- `accept_server`: Discard client version, accept server version
- `merge`: Combine fields (client provides merged result)

**Server Response:**
```json
{
  "type": "conflict_resolved",
  "correlation_id": "conflict-789",
  "entity_type": "job",
  "entity_id": 5001,
  "accepted_version": 10,
  "server_timestamp": "2025-11-15T12:06:01Z"
}
```

---

### 4. Error Messages

#### ERROR (Server → Client)

**Purpose:** Notify client of operation failure

**Schema:**
```json
{
  "type": "error",
  "correlation_id": "sync-upload-client-001",
  "operation_id": "op-mobile-temp-001",
  "error_code": "VALIDATION_ERROR",
  "message": "Job creation failed - validation error",
  "field_errors": [
    {
      "field": "scheduled_start",
      "error": "must_be_future_date",
      "message": "Scheduled start must be in the future"
    }
  ],
  "retry_allowed": false,
  "server_timestamp": "2025-11-15T12:05:01Z"
}
```

**Client Behavior:**
- If `retry_allowed = false`: Remove from pending queue, show error to user
- If `retry_allowed = true`: Retry with exponential backoff
- Log error with correlation_id for support

---

## Sync Protocol

### Complete Sync Flow

```
┌────────────┐                           ┌────────────┐
│   Client   │                           │   Server   │
└────────────┘                           └────────────┘
      │                                        │
      │──── CONNECT (with JWT) ────────────▶  │
      │                                        │
      │◀─── CONNECTION_ACCEPTED ─────────────  │
      │     (server_time, pending_count=15)    │
      │                                        │
      │──── SYNC_START ─────────────────────▶  │
      │     (last_sync: Nov 14 18:00)          │
      │                                        │
      │◀─── SYNC_DATA (batch 1/3) ───────────  │
      │     (5 updates)                        │
      │                                        │
      │──── SYNC_ACK (batch 1) ──────────────▶ │
      │     (applied: 5, failed: 0)            │
      │                                        │
      │◀─── SYNC_DATA (batch 2/3) ───────────  │
      │     (5 updates)                        │
      │                                        │
      │──── SYNC_ACK (batch 2) ──────────────▶ │
      │                                        │
      │◀─── SYNC_DATA (batch 3/3) ───────────  │
      │     (5 updates)                        │
      │                                        │
      │──── SYNC_ACK (batch 3) ──────────────▶ │
      │                                        │
      │──── SYNC_DATA (client pending ops) ──▶ │
      │     (3 creates, 2 updates offline)     │
      │                                        │
      │◀─── SYNC_ACK ────────────────────────  │
      │     (temp-uuid → real IDs)             │
      │                                        │
      │──── HEARTBEAT ───────────────────────▶ │
      │                                        │
      │◀─── HEARTBEAT_ACK ────────────────────  │
      │     (every 30s)                        │
      │                                        │
      │◀─── REALTIME_UPDATE ─────────────────  │
      │     (job 5001 updated by other user)   │
      │                                        │
      │──── DISCONNECT ──────────────────────▶ │
      │                                        │
      │◀─── DISCONNECT_ACK ──────────────────  │
```

---

## Conflict Resolution

### Conflict Detection Algorithm

**Server-side logic:**

```python
def apply_client_operation(operation):
    """
    Apply client operation with conflict detection
    """
    entity_type = operation['entity_type']
    entity_id = operation['entity_id']
    client_version = operation.get('version')

    # Fetch current server state
    server_entity = get_entity(entity_type, entity_id)
    server_version = server_entity.version

    # Detect conflict
    if client_version and client_version < server_version:
        # Client has stale version - conflict!
        return {
            'type': 'conflict_detected',
            'conflict_reason': 'version_mismatch',
            'client_version': client_version,
            'server_version': server_version,
            'client_data': operation['data'],
            'server_data': serialize(server_entity)
        }

    # No conflict - apply update
    server_entity.update(operation['data'])
    server_entity.version += 1
    server_entity.save()

    return {
        'type': 'sync_ack',
        'accepted_version': server_entity.version
    }
```

---

### Conflict Resolution Strategies

#### Strategy 1: Last-Write-Wins (LWW)

**When to use:** Simple fields with no dependencies

**Algorithm:**
```python
def resolve_lww(client_data, server_data):
    """
    Compare timestamps, keep newer version
    """
    client_timestamp = parse(client_data['updated_at'])
    server_timestamp = parse(server_data['updated_at'])

    if client_timestamp > server_timestamp:
        return client_data  # Client wins
    else:
        return server_data  # Server wins
```

**Example:**
- Client changed priority to `urgent` at 12:05
- Server changed priority to `high` at 11:00
- Client timestamp newer → Client wins
- Final priority: `urgent`

---

#### Strategy 2: Field-Level Merge

**When to use:** Complex entities with independent fields

**Algorithm:**
```kotlin
fun mergeFields(
    clientVersion: Job,
    serverVersion: Job
): Job {
    return Job(
        id = serverVersion.id,
        // If field changed locally but not on server, keep local
        title = if (clientVersion.title != originalLocal.title && serverVersion.title == originalLocal.title) {
            clientVersion.title  // Local change
        } else {
            serverVersion.title  // Server change or both changed
        },
        // Priority: Local change
        priority = if (clientVersion.priority != originalLocal.priority) {
            clientVersion.priority
        } else {
            serverVersion.priority
        },
        // Status: Always take server (state transitions controlled by backend)
        status = serverVersion.status,
        // Version: Always take server + 1
        version = serverVersion.version + 1
    )
}
```

**Three-way merge requires:**
- Original version (before offline edits)
- Client version (with offline edits)
- Server version (with server edits)

**Mobile must store** original version in pending queue for merge!

---

#### Strategy 3: User-Prompted Merge

**When to use:** Conflicts in critical fields or complex scenarios

**Flow:**
```
1. Server sends CONFLICT_DETECTED
   → Client shows conflict resolution UI

2. UI shows diff:
   ┌─────────────────────────────────────┐
   │ Conflict Detected                   │
   ├─────────────────────────────────────┤
   │ Your changes:                       │
   │   Priority: urgent                  │
   │   Updated: 12:05 PM                 │
   │                                     │
   │ Server changes:                     │
   │   Title: "Updated by supervisor"    │
   │   Priority: high                    │
   │   Updated: 11:00 AM                 │
   │                                     │
   │ ┌─────────────┐ ┌─────────────┐    │
   │ │ Keep Mine   │ │ Use Server  │    │
   │ └─────────────┘ └─────────────┘    │
   └─────────────────────────────────────┘

3. User chooses "Keep Mine"
   → Send CONFLICT_RESOLUTION with merged_data

4. Server applies and confirms
   → Send CONFLICT_RESOLVED
```

---

### Conflict Example (Complete)

**Scenario:** User edits job offline, server also updates job

**Initial State (v5):**
```json
{
  "id": 5001,
  "title": "HVAC Inspection",
  "priority": "medium",
  "status": "scheduled",
  "version": 5
}
```

**Client Edit (offline at 12:05):**
```json
{
  "id": 5001,
  "priority": "urgent",  // Changed
  "version": 5  // Still thinks it's v5
}
```

**Server Edit (by supervisor at 11:00):**
```json
{
  "id": 5001,
  "title": "HVAC Inspection - Updated",  // Changed
  "priority": "high",  // Changed
  "status": "in_progress",  // Changed
  "version": 6  // Now v6
}
```

**Supervisor edits again (at 11:30):**
```json
{
  "id": 5001,
  "status": "pending_approval",  // Changed
  "version": 7  // Now v7
}
```

**Client Comes Online (12:10):**

1. Client sends update (thinks it's v5 → v6):
   ```json
   {
     "type": "sync_data",
     "operations": [{
       "entity_id": 5001,
       "operation": "update",
       "data": {"priority": "urgent", "version": 5}
     }]
   }
   ```

2. Server detects conflict (client v5, server v7):
   ```json
   {
     "type": "conflict_detected",
     "client_version": 5,
     "server_version": 7,
     "client_data": {"priority": "urgent"},
     "server_data": {
       "title": "HVAC Inspection - Updated",
       "priority": "high",
       "status": "pending_approval",
       "version": 7
     }
   }
   ```

3. Client shows conflict UI, user chooses merge:
   - Keep server title: "HVAC Inspection - Updated"
   - Keep client priority: "urgent"
   - Keep server status: "pending_approval"

4. Client sends resolution:
   ```json
   {
     "type": "conflict_resolution",
     "resolution_strategy": "merge",
     "merged_data": {
       "id": 5001,
       "title": "HVAC Inspection - Updated",
       "priority": "urgent",
       "status": "pending_approval",
       "version": 7
     }
   }
   ```

5. Server accepts and increments version:
   ```json
   {
     "type": "conflict_resolved",
     "entity_id": 5001,
     "accepted_version": 8
   }
   ```

---

## Complete Examples

### Example 1: First Sync After 24h Offline

**Client Context:**
- Last synced: Nov 14 18:00
- Offline for 24 hours
- Created 2 jobs, updated 1 job, checked in/out once

**Flow:**

**1. Client connects:**
```json
{
  "type": "connection_accepted",
  "server_time": "2025-11-15T18:00:00Z",
  "pending_updates_count": 47
}
```

**2. Client starts sync:**
```json
{
  "type": "sync_start",
  "last_sync_timestamp": "2025-11-14T18:00:00Z",
  "pending_operations_count": 4
}
```

**3. Server sends batch 1:**
```json
{
  "type": "sync_data",
  "batch_number": 1,
  "total_batches": 2,
  "operations": [
    {"operation": "update", "entity_type": "job", "entity_id": 5001, ...},
    {"operation": "update", "entity_type": "job", "entity_id": 5002, ...},
    {"operation": "create", "entity_type": "ticket", "entity_id": 9001, ...}
    // ... 22 more
  ]
}
```

**4. Client acknowledges batch 1:**
```json
{
  "type": "sync_ack",
  "operations_applied": 25,
  "operations_failed": 0
}
```

**5. Server sends batch 2:**
```json
{
  "type": "sync_data",
  "batch_number": 2,
  "total_batches": 2,
  "operations": [
    // ... remaining 22 operations
  ]
}
```

**6. Client acknowledges batch 2:**
```json
{
  "type": "sync_ack",
  "operations_applied": 22
}
```

**7. Client uploads pending operations:**
```json
{
  "type": "sync_data",
  "operations": [
    {
      "operation_id": "op-mobile-001",
      "entity_type": "job",
      "entity_id": "temp-job-abc",
      "operation": "create",
      "data": {
        "title": "Created offline",
        "job_type": "inspection",
        "scheduled_start": "2025-11-16T09:00:00Z"
      }
    },
    {
      "operation_id": "op-mobile-002",
      "entity_type": "job",
      "entity_id": "temp-job-def",
      "operation": "create",
      "data": {...}
    },
    {
      "operation_id": "op-mobile-003",
      "entity_type": "job",
      "entity_id": 5003,
      "operation": "update",
      "data": {"priority": "high", "version": 3}
    },
    {
      "operation_id": "op-mobile-004",
      "entity_type": "attendance",
      "entity_id": "temp-att-xyz",
      "operation": "create",
      "data": {
        "checkin_time": "2025-11-15T08:05:00Z",
        "shift_id": 501
      }
    }
  ]
}
```

**8. Server acknowledges:**
```json
{
  "type": "sync_ack",
  "operations_applied": 4,
  "id_mappings": [
    {"temp_id": "temp-job-abc", "real_id": 5010},
    {"temp_id": "temp-job-def", "real_id": 5011},
    {"temp_id": "temp-att-xyz", "real_id": 7050}
  ],
  "conflicts": []
}
```

**9. Client updates local database:**
```kotlin
idMappings.forEach { mapping ->
    database.updateTempId(
        tempId = mapping.tempId,
        realId = mapping.realId
    )
}
```

**10. Sync complete - resume normal operation.**

---

## Kotlin Implementation

### WebSocket Client Setup

```kotlin
// network/src/main/kotlin/com/intelliwiz/network/websocket/SyncWebSocketClient.kt

class SyncWebSocketClient(
    private val tokenProvider: TokenProvider,
    private val tenantManager: TenantManager,
    private val deviceIdProvider: DeviceIdProvider
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .pingInterval(30, TimeUnit.SECONDS)  // Heartbeat
        .build()

    private var webSocket: WebSocket? = null

    fun connect() {
        val token = tokenProvider.getAccessToken()
        val clientId = tenantManager.getCurrentClientId()
        val mobileId = deviceIdProvider.getDeviceId()

        val url = "wss://api.intelliwiz.com/ws/sync/?token=$token&client_id=$clientId&mobile_id=$mobileId"

        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = client.newWebSocket(request, SyncWebSocketListener())
    }

    fun sendMessage(message: WebSocketMessage) {
        val json = Json.encodeToString(message)
        webSocket?.send(json)
    }

    fun disconnect() {
        val message = DisconnectMessage(
            mobileId = deviceIdProvider.getDeviceId()
        )
        sendMessage(message)
        webSocket?.close(1000, "Client disconnect")
    }
}
```

---

### WebSocket Listener

```kotlin
class SyncWebSocketListener(
    private val messageHandler: WebSocketMessageHandler
) : WebSocketListener() {

    override fun onOpen(webSocket: WebSocket, response: Response) {
        Log.d("WebSocket", "Connected")
        // Server will send CONNECTION_ACCEPTED
    }

    override fun onMessage(webSocket: WebSocket, text: String) {
        try {
            // Parse message type
            val baseMessage = Json.decodeFromString<BaseMessage>(text)

            when (baseMessage.type) {
                "connection_accepted" -> {
                    val msg = Json.decodeFromString<ConnectionAcceptedMessage>(text)
                    messageHandler.handleConnectionAccepted(msg)
                }
                "sync_data" -> {
                    val msg = Json.decodeFromString<SyncDataMessage>(text)
                    messageHandler.handleSyncData(msg)
                }
                "sync_ack" -> {
                    val msg = Json.decodeFromString<SyncAckMessage>(text)
                    messageHandler.handleSyncAck(msg)
                }
                "conflict_detected" -> {
                    val msg = Json.decodeFromString<ConflictDetectedMessage>(text)
                    messageHandler.handleConflict(msg)
                }
                "error" -> {
                    val msg = Json.decodeFromString<ErrorMessage>(text)
                    messageHandler.handleError(msg)
                }
                "heartbeat_ack" -> {
                    // Heartbeat acknowledged
                }
                else -> {
                    Log.w("WebSocket", "Unknown message type: ${baseMessage.type}")
                }
            }
        } catch (e: Exception) {
            Log.e("WebSocket", "Failed to parse message", e)
        }
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        Log.e("WebSocket", "Connection failed", t)
        // Trigger exponential backoff reconnection
        messageHandler.handleConnectionFailure(t)
    }

    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
        Log.d("WebSocket", "Closed: $code - $reason")
    }
}
```

---

### Heartbeat Manager

```kotlin
class HeartbeatManager(
    private val webSocketClient: SyncWebSocketClient,
    private val scope: CoroutineScope
) {
    private var heartbeatJob: Job? = null

    fun start() {
        heartbeatJob = scope.launch {
            while (isActive) {
                delay(30_000)  // 30 seconds
                sendHeartbeat()
            }
        }
    }

    fun stop() {
        heartbeatJob?.cancel()
    }

    private fun sendHeartbeat() {
        val message = HeartbeatMessage(
            mobileId = deviceIdProvider.getDeviceId(),
            clientTimestamp = Clock.System.now()
        )
        webSocketClient.sendMessage(message)
    }
}
```

---

### Conflict Resolution UI

```kotlin
@Composable
fun ConflictResolutionDialog(
    conflict: ConflictDetectedMessage,
    onResolved: (ConflictResolutionMessage) -> Unit
) {
    AlertDialog(
        onDismissRequest = {},
        title = { Text("Conflict Detected") },
        text = {
            Column {
                Text("This ${conflict.entityType} was updated while you were offline.")
                Spacer(Modifier.height(16.dp))

                Text("Your changes:", fontWeight = FontWeight.Bold)
                Text(formatChanges(conflict.clientData))

                Spacer(Modifier.height(16.dp))

                Text("Server changes:", fontWeight = FontWeight.Bold)
                Text(formatChanges(conflict.serverData))
            }
        },
        confirmButton = {
            Button(onClick = {
                onResolved(ConflictResolutionMessage(
                    correlationId = conflict.correlationId,
                    resolutionStrategy = "keep_local",
                    mergedData = conflict.clientData
                ))
            }) {
                Text("Keep My Changes")
            }
        },
        dismissButton = {
            Button(onClick = {
                onResolved(ConflictResolutionMessage(
                    correlationId = conflict.correlationId,
                    resolutionStrategy = "accept_server",
                    mergedData = conflict.serverData
                ))
            }) {
                Text("Use Server Version")
            }
        }
    )
}
```

---

## Reconnection Strategy

### Exponential Backoff

```kotlin
class ReconnectionManager(
    private val webSocketClient: SyncWebSocketClient
) {
    private var reconnectAttempt = 0
    private val maxAttempts = 10

    fun scheduleReconnect() {
        if (reconnectAttempt >= maxAttempts) {
            Log.e("WebSocket", "Max reconnection attempts reached")
            return
        }

        val delayMs = calculateBackoff(reconnectAttempt)

        scope.launch {
            delay(delayMs)
            webSocketClient.connect()
            reconnectAttempt++
        }
    }

    private fun calculateBackoff(attempt: Int): Long {
        // Exponential backoff with jitter
        val baseDelay = 1000L  // 1 second
        val exponential = baseDelay * (2.0.pow(attempt)).toLong()
        val jitter = Random.nextLong(0, 1000)
        val maxDelay = 60_000L  // Max 1 minute

        return min(exponential + jitter, maxDelay)
    }

    fun reset() {
        reconnectAttempt = 0
    }
}
```

**Backoff Sequence:**
- Attempt 1: 1s + jitter (1-2s)
- Attempt 2: 2s + jitter (2-3s)
- Attempt 3: 4s + jitter (4-5s)
- Attempt 4: 8s + jitter (8-9s)
- Attempt 5: 16s + jitter (16-17s)
- Attempt 6+: 60s max (capped)

---

## Testing

### Test Cases

**1. Connection:**
- [ ] Connect with valid JWT → CONNECTION_ACCEPTED
- [ ] Connect with expired JWT → 401 error, connection closed
- [ ] Connect with wrong client_id → 403 error
- [ ] Reconnect after network loss → exponential backoff

**2. Sync:**
- [ ] SYNC_START → receive SYNC_DATA batches
- [ ] Acknowledge each batch → SYNC_ACK
- [ ] Upload pending operations → receive ID mappings
- [ ] Empty sync (no pending updates) → immediate ack

**3. Conflicts:**
- [ ] Detect version conflict → CONFLICT_DETECTED
- [ ] Resolve with keep_local → CONFLICT_RESOLVED
- [ ] Resolve with accept_server → CONFLICT_RESOLVED
- [ ] Resolve with merge → CONFLICT_RESOLVED

**4. Heartbeat:**
- [ ] Send HEARTBEAT every 30s → receive HEARTBEAT_ACK
- [ ] Miss heartbeat → connection timeout after 90s
- [ ] Reconnect after timeout → resume sync

**5. Errors:**
- [ ] Validation error on create → ERROR message, remove from queue
- [ ] Network error during upload → retry with backoff
- [ ] Server error (500) → retry with backoff

---

## Troubleshooting

**WebSocket won't connect:**
- Check JWT token is valid (not expired)
- Check client_id matches user's tenant
- Check mobile_id is valid UUID format
- Verify network allows WebSocket connections

**Messages not being delivered:**
- Check heartbeat is running (every 30s)
- Check connection is still open
- Verify message format matches schema

**Conflicts not resolving:**
- Ensure client sends correct version in CONFLICT_RESOLUTION
- Check merged_data includes all required fields
- Verify server has accepted resolution (CONFLICT_RESOLVED received)

**Sync very slow:**
- Server batches updates (25 per batch)
- Client should ack each batch immediately
- Don't process all batches before first ack

---

## Performance Considerations

**Batch Size:**
- Server sends max 25 operations per SYNC_DATA
- Prevents overwhelming client with 1000+ updates at once
- Client acks each batch before next is sent

**Heartbeat Interval:**
- 30 seconds is optimal
- Too frequent: Battery drain
- Too infrequent: Delayed disconnect detection

**Reconnection:**
- Use exponential backoff to avoid server overload
- Max delay: 60 seconds
- Reset backoff counter on successful connection

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Next Review:** December 7, 2025
