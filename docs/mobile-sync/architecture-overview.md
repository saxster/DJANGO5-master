# Mobile Sync System - Architecture Overview

## Executive Summary

The Mobile Sync System provides a robust, scalable solution for offline-first mobile applications to synchronize data with the backend server. It supports real-time WebSocket-based sync, conflict resolution, resumable file uploads, and comprehensive monitoring.

**Key Features:**
- ✅ Real-time bidirectional sync via WebSockets
- ✅ Offline-first with conflict resolution
- ✅ Resumable chunked file uploads
- ✅ Idempotency guarantees (24-hour window)
- ✅ Multi-tenant support with per-tenant policies
- ✅ Comprehensive health monitoring and alerting
- ✅ Performance optimized (P95 < 200ms)

---

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Mobile Clients                           │
│  (iOS, Android, Progressive Web Apps)                        │
└─────────────┬───────────────────────────────────────────────┘
              │
              │ WebSocket (wss://)
              │ + REST API (https://)
              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Load Balancer / CDN                         │
│  (nginx, AWS ALB, Cloudflare)                                │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│              Django Application Server (Daphne)               │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Sync WebSocket Consumer                              │   │
│  │  - Connection management                              │   │
│  │  - Message routing                                    │   │
│  │  - Heartbeat monitoring                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Sync Engine Service                                 │    │
│  │  - Data validation                                   │    │
│  │  - Conflict detection                                │    │
│  │  - Batch processing                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Support Services                                    │    │
│  │  - IdempotencyService                                │    │
│  │  - ConflictResolutionService                         │    │
│  │  - ResumableUploadService                            │    │
│  │  - SyncCacheService                                  │    │
│  │  - SyncHealthMonitor                                 │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────┬──────────────────────┬────────────────────────┘
              │                      │
              ▼                      ▼
┌──────────────────────┐   ┌──────────────────────┐
│  PostgreSQL 14+      │   │  Redis Cache         │
│  - Sync data         │   │  - Conflict policies │
│  - Conflict logs     │   │  - Device health     │
│  - Analytics         │   │  - Session data      │
│  - Upload sessions   │   │  - Idempotency cache │
└──────────────────────┘   └──────────────────────┘
```

---

## Core Data Flow

### 1. Sync Request Flow

```
Mobile Client                Server                    Database
     │                          │                          │
     │─── WebSocket Connect ───▶│                          │
     │◀── Connection OK ────────│                          │
     │                          │                          │
     │─── Sync Batch ──────────▶│                          │
     │    {items: [...]}        │                          │
     │                          │                          │
     │                          │─── Check Idempotency ───▶│
     │                          │◀── Not Duplicate ────────│
     │                          │                          │
     │                          │─── Validate Items ──────▶│
     │                          │◀── Validation OK ────────│
     │                          │                          │
     │                          │─── Detect Conflicts ────▶│
     │                          │◀── Conflicts Found ──────│
     │                          │                          │
     │                          │─── Resolve Conflicts ───▶│
     │                          │◀── Resolution Complete ──│
     │                          │                          │
     │                          │─── Persist Data ────────▶│
     │                          │◀── Success ──────────────│
     │                          │                          │
     │◀── Sync Response ────────│                          │
     │    {synced: N, failed: M}│                          │
     │                          │                          │
     │                          │─── Update Analytics ─────▶
     │                          │◀── Analytics Recorded ───│
```

### 2. Conflict Resolution Flow

```
1. Client sends update with client_version=5, server has version=6 → CONFLICT
2. Fetch tenant conflict policy from cache (or DB)
3. Apply resolution strategy:
   - client_wins: Accept client version
   - server_wins: Reject client, send server version
   - most_recent_wins: Compare timestamps
   - preserve_escalation: Complex merge logic
   - manual: Queue for human review
4. Log conflict resolution for audit
5. Send resolution result to client
```

### 3. Resumable Upload Flow

```
1. Client: Initialize upload session
   POST /api/v1/uploads/init
   → Returns upload_id, chunk_size, total_chunks

2. Client: Upload chunks (can be parallel)
   POST /api/v1/uploads/{upload_id}/chunk/{index}
   → Each chunk validated with SHA-256 checksum

3. Server: Track chunk progress
   - Missing chunks list updated
   - Expire sessions after 24 hours

4. Client: Finalize upload
   POST /api/v1/uploads/{upload_id}/finalize
   → Reassemble chunks, validate file hash

5. Server: Move to permanent storage
   → Clean up temp directory
```

---

## Data Models

### Core Models

**SyncIdempotencyRecord**
- Prevents duplicate processing of sync requests
- 24-hour TTL with automatic cleanup
- SHA-256 hash of request payload

**TenantConflictPolicy**
- Per-tenant, per-domain conflict resolution rules
- Supports 5 resolution strategies
- Cached for performance (1-hour TTL)

**ConflictResolutionLog**
- Audit trail for all conflict resolutions
- Tracks resolution strategy and outcome
- Used for conflict rate monitoring

**SyncAnalyticsSnapshot**
- Time-series metrics (hourly snapshots)
- Success rate, conflict rate, latency percentiles
- Per-tenant aggregation

**SyncDeviceHealth**
- Per-device sync health tracking
- Health score (0-100) based on success rate
- Network type, app version, OS version

**UploadSession**
- Tracks resumable upload progress
- Chunk-level metadata
- 24-hour expiration with cleanup

---

## Performance Characteristics

### Latency Targets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Sync (small batch < 10 items) | 50ms | 150ms | 200ms |
| Sync (large batch 100 items) | 200ms | 500ms | 800ms |
| Conflict detection | 10ms | 30ms | 50ms |
| Conflict resolution | 20ms | 50ms | 100ms |
| Upload chunk (1MB) | 100ms | 300ms | 500ms |
| Idempotency check (cache hit) | 1ms | 5ms | 10ms |
| Idempotency check (cache miss) | 20ms | 50ms | 100ms |

### Throughput Targets

- **Concurrent connections:** 10,000+ per server
- **Sync requests/second:** 1,000+ per server
- **Items synced/minute:** 50,000+ per server
- **Upload sessions:** 500+ concurrent per server

### Resource Usage

- **Database connections:** 25-50 active (with pgBouncer)
- **Memory per connection:** ~2MB
- **Redis cache size:** ~500MB for 10,000 tenants
- **Disk I/O:** Primarily upload temp storage

---

## Scalability Strategy

### Horizontal Scaling

1. **Application Servers:**
   - Stateless WebSocket consumers
   - Scale behind load balancer
   - Session affinity not required (reconnect on any server)

2. **Database:**
   - Read replicas for analytics queries
   - Connection pooling via pgBouncer
   - Partitioning for large conflict logs (by timestamp)

3. **Cache:**
   - Redis Cluster for distributed caching
   - Consistent hashing for key distribution

### Vertical Scaling

- **CPU:** Primarily async I/O, not CPU-bound
- **Memory:** Scale with connection count (2MB/connection)
- **Disk:** Fast SSD for upload temp storage

---

## Security Architecture

### Authentication & Authorization

- **WebSocket connections:** JWT token in query param or header
- **REST API:** Bearer token authentication
- **Multi-tenancy:** Tenant ID from user context, validated on all operations

### Data Protection

- **In-transit:** TLS 1.3 for all connections (wss://, https://)
- **At-rest:** PostgreSQL encrypted storage
- **PII:** Hashed device IDs, encrypted mobile numbers
- **File uploads:** Sanitized filenames, path traversal prevention

### Attack Prevention

- **Rate limiting:** Per-user, per-endpoint limits
- **SQL injection:** Parameterized queries, middleware validation
- **XSS:** Content Security Policy, input sanitization
- **CSRF:** Token validation for state-changing operations

---

## Monitoring & Observability

### Key Metrics

1. **Sync Health:**
   - Success rate (target: > 95%)
   - Conflict rate (target: < 5%)
   - Average sync duration (target: < 500ms P95)
   - Failed syncs per minute (alert: > 10/min)

2. **System Health:**
   - Active WebSocket connections
   - Database connection pool utilization
   - Cache hit rate (target: > 80%)
   - Queue depth (if using async tasks)

3. **Business Metrics:**
   - Unique active devices per day
   - Data volume synced per tenant
   - Upload completion rate
   - Conflict resolution accuracy

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Success rate | < 98% | < 95% |
| Conflict rate | > 3% | > 5% |
| P95 latency | > 300ms | > 500ms |
| Failed syncs/min | > 5 | > 10 |
| Device health score | < 80 | < 70 |
| Upload abandonment | > 15% | > 20% |

---

## Disaster Recovery

### Backup Strategy

- **Database:** Continuous WAL archiving + daily full backups
- **Upload files:** Replicated to S3 with versioning
- **Redis cache:** Ephemeral, rebuilt from DB on restart

### Recovery Procedures

1. **Database failure:**
   - Automatic failover to read replica (promoted to primary)
   - RPO: < 1 minute, RTO: < 5 minutes

2. **Application server failure:**
   - WebSocket reconnect with exponential backoff
   - Clients resume from last acknowledged sync

3. **Redis failure:**
   - Degraded performance (all requests hit DB)
   - Auto-rebuild cache on restart (warm cache script)

---

## Future Enhancements

### Roadmap

1. **Q1 2026: Delta Sync**
   - Send only changed fields, not full records
   - Reduce bandwidth by 60-80%

2. **Q2 2026: Compression**
   - gzip compression for sync payloads
   - Further reduce bandwidth by 40-50%

3. **Q3 2026: Offline Analytics**
   - Client-side analytics aggregation
   - Batch upload of aggregated metrics

4. **Q4 2026: GraphQL Subscriptions**
   - Real-time push notifications for data changes
   - Reduce polling overhead

---

## References

- [API Reference](./api-reference.md)
- [Client Integration Guide](./client-integration-guide.md)
- [Conflict Resolution Guide](./conflict-resolution-guide.md)
- [Troubleshooting Guide](./troubleshooting.md)
- [Operational Runbooks](./runbooks/)

---

**Last Updated:** 2025-09-28
**Version:** 1.0
**Maintained By:** Platform Engineering Team