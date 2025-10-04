# Mobile Sync API Reference

## WebSocket Sync API

### Connection

```
wss://api.example.com/ws/mobile/sync/?device_id={device_id}
```

**Authentication:** JWT token in query parameter or `Authorization` header

**Query Parameters:**
- `device_id` (required): Unique device identifier

### Message Format

All messages follow this structure:

```json
{
  "type": "message_type",
  "payload": { ... },
  "timestamp": "2025-09-28T12:00:00Z"
}
```

### Client→Server Messages

#### 1. Sync Request

Sync data from mobile client to server.

```json
{
  "type": "sync",
  "payload": {
    "idempotency_key": "sha256_hash_of_request",
    "voice_data": [{
      "verification_id": "uuid",
      "timestamp": "2025-09-28T12:00:00Z",
      "verified": true,
      "confidence_score": 0.95,
      "quality_score": 0.88,
      "processing_time_ms": 150
    }],
    "behavioral_data": [{
      "session_id": "uuid",
      "events": [...],
      "duration_ms": 60000
    }]
  }
}
```

**Response:**

```json
{
  "type": "sync_response",
  "payload": {
    "synced_items": 10,
    "failed_items": 0,
    "conflicts": [],
    "errors": []
  },
  "timestamp": "2025-09-28T12:00:01Z"
}
```

#### 2. Heartbeat

Keep connection alive.

```json
{
  "type": "heartbeat",
  "payload": {
    "client_time": "2025-09-28T12:00:00Z"
  }
}
```

**Response:**

```json
{
  "type": "heartbeat_ack",
  "payload": {
    "server_time": "2025-09-28T12:00:00.123Z"
  }
}
```

#### 3. Conflict Resolution

Respond to conflict detected by server.

```json
{
  "type": "resolve_conflict",
  "payload": {
    "conflict_id": "uuid",
    "resolution": "accept_server",
    "client_data": { ... }
  }
}
```

### Server→Client Messages

#### 1. Sync Acknowledgment

```json
{
  "type": "sync_response",
  "payload": {
    "synced_items": 10,
    "failed_items": 2,
    "errors": [{
      "item_id": "uuid",
      "error": "validation_failed",
      "message": "Missing required field"
    }]
  }
}
```

#### 2. Conflict Notification

```json
{
  "type": "conflict",
  "payload": {
    "conflict_id": "uuid",
    "domain": "journal",
    "mobile_id": "uuid",
    "server_version": 5,
    "client_version": 4,
    "server_data": { ... },
    "resolution_options": ["accept_server", "accept_client", "merge"]
  }
}
```

#### 3. Server Push

```json
{
  "type": "server_push",
  "payload": {
    "updates": [{
      "entity_type": "task",
      "entity_id": "uuid",
      "operation": "update",
      "data": { ... }
    }]
  }
}
```

---

## REST API

### Resumable Uploads

#### Initialize Upload

```http
POST /api/v1/uploads/init
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "filename": "report.pdf",
  "total_size": 10485760,
  "mime_type": "application/pdf",
  "file_hash": "sha256_hash"
}
```

**Response:**

```json
{
  "upload_id": "uuid",
  "chunk_size": 1048576,
  "total_chunks": 10,
  "expires_at": "2025-09-29T12:00:00Z"
}
```

#### Upload Chunk

```http
POST /api/v1/uploads/{upload_id}/chunk/{chunk_index}
Authorization: Bearer {jwt_token}
Content-Type: application/octet-stream
X-Chunk-Checksum: sha256_hash

{binary_data}
```

**Response:**

```json
{
  "uploaded": true,
  "chunk_index": 0,
  "remaining_chunks": 9,
  "progress_pct": 10.0
}
```

#### Get Upload Status

```http
GET /api/v1/uploads/{upload_id}/status
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "upload_id": "uuid",
  "status": "active",
  "uploaded_chunks": [0, 1, 2],
  "missing_chunks": [3, 4, 5, 6, 7, 8, 9],
  "progress_pct": 30.0,
  "expires_at": "2025-09-29T12:00:00Z"
}
```

#### Finalize Upload

```http
POST /api/v1/uploads/{upload_id}/finalize
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "finalized": true,
  "file_url": "https://cdn.example.com/files/uuid.pdf",
  "file_size": 10485760,
  "checksum": "sha256_hash"
}
```

#### Cancel Upload

```http
DELETE /api/v1/uploads/{upload_id}
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "cancelled": true,
  "message": "Upload session cancelled and cleaned up"
}
```

---

## Conflict Resolution API

### Get Tenant Policy

```http
GET /api/v1/sync/policies/{tenant_id}/{domain}
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "tenant_id": 123,
  "domain": "journal",
  "resolution_policy": "most_recent_wins",
  "auto_resolve": true,
  "notify_on_conflict": false
}
```

### Get Conflict Logs

```http
GET /api/v1/sync/conflicts?tenant_id=123&domain=journal&since=2025-09-01
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "conflicts": [{
    "id": "uuid",
    "mobile_id": "uuid",
    "domain": "journal",
    "server_version": 5,
    "client_version": 4,
    "resolution_strategy": "most_recent_wins",
    "resolution_result": "resolved",
    "winning_version": "server",
    "created_at": "2025-09-28T12:00:00Z"
  }],
  "total": 1,
  "conflict_rate_pct": 2.5
}
```

---

## Health & Monitoring API

### Sync Health Check

```http
GET /api/v1/sync/health?tenant_id=123&hours=1
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "health_status": "healthy",
  "metrics": {
    "success_rate": 98.5,
    "conflict_rate": 2.1,
    "avg_sync_duration_ms": 125.5,
    "failed_syncs_per_minute": 0.5,
    "upload_abandonment_rate": 5.2,
    "avg_device_health_score": 95.3
  },
  "alerts": []
}
```

### Device Health

```http
GET /api/v1/sync/devices/{device_id}/health
Authorization: Bearer {jwt_token}
```

**Response:**

```json
{
  "device_id": "abc123",
  "health_score": 95.5,
  "total_syncs": 1250,
  "failed_syncs_count": 10,
  "avg_sync_duration_ms": 110.5,
  "conflicts_encountered": 25,
  "last_sync_at": "2025-09-28T12:00:00Z",
  "network_type": "wifi",
  "app_version": "2.1.0",
  "os_version": "iOS 17.0"
}
```

---

## Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| `SYNC_001` | Invalid payload format | Check JSON schema |
| `SYNC_002` | Missing required field | Add required field |
| `SYNC_003` | Idempotency key conflict | Retry with different key |
| `SYNC_004` | Conflict detected | Resolve via conflict API |
| `SYNC_005` | Version mismatch | Update client SDK |
| `UPLOAD_001` | Invalid upload session | Reinitialize upload |
| `UPLOAD_002` | Chunk checksum mismatch | Re-upload chunk |
| `UPLOAD_003` | Session expired | Start new upload |
| `AUTH_001` | Invalid token | Re-authenticate |
| `AUTH_002` | Token expired | Refresh token |
| `RATE_001` | Rate limit exceeded | Retry after backoff |

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| WebSocket sync | 100 requests | 1 minute |
| Upload init | 10 requests | 1 minute |
| Upload chunk | 1000 requests | 1 minute |
| Health check | 60 requests | 1 minute |

---

**Last Updated:** 2025-09-28