# Mobile Sync Performance Optimization Guide

## Overview

This guide provides recommendations for optimizing database connection pooling and query performance for the mobile sync system.

## Database Connection Pooling

### Current Configuration

**Development:**
- `CONN_MAX_AGE = 0` (connections closed after each request)
- Good for debugging, but not representative of production

**Production:**
- `CONN_MAX_AGE = 300` (5 minutes)
- Reuses connections for 5 minutes before recycling

### Recommended Settings for High-Volume Sync

For optimal sync performance under load, consider these PostgreSQL-specific settings:

```python
# Production settings for high-volume sync operations
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "CONN_MAX_AGE": 600,  # 10 minutes for sync workloads
        "OPTIONS": {
            "sslmode": "require",
            # Connection pool settings
            "connect_timeout": 5,
            "options": "-c statement_timeout=30000",  # 30 second timeout
        },
        # Use pgBouncer for connection pooling in production
        "CONN_HEALTH_CHECKS": True,  # Django 4.1+
    }
}
```

### Using pgBouncer (Recommended for Production)

For optimal performance at scale, use pgBouncer:

```ini
# pgbouncer.ini
[databases]
intelliwiz = host=localhost port=5432 dbname=intelliwiz_db

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 10
reserve_pool_timeout = 5
```

**Django Configuration with pgBouncer:**

```python
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "HOST": "localhost",
        "PORT": "6432",  # pgBouncer port
        "CONN_MAX_AGE": 0,  # Let pgBouncer handle pooling
        "DISABLE_SERVER_SIDE_CURSORS": True,  # Required with pgBouncer
    }
}
```

## Query Optimization

### Use select_related() and prefetch_related()

**Before (N+1 queries):**
```python
# Bad - causes N+1 queries
policies = TenantConflictPolicy.objects.filter(tenant_id=tenant_id)
for policy in policies:
    print(policy.tenant.tenantname)  # Extra query per policy
```

**After (1 query):**
```python
# Good - single query with JOIN
policies = TenantConflictPolicy.objects.filter(
    tenant_id=tenant_id
).select_related('tenant', 'created_by')
```

### Cache Frequently Accessed Data

Use `SyncCacheService` for frequently accessed configuration:

```python
from apps.core.services.sync_cache_service import sync_cache_service

# Cache hit: ~1ms
policy = sync_cache_service.get_conflict_policy(tenant_id, 'journal')

# Database query: ~10-50ms
policy = TenantConflictPolicy.objects.get(tenant_id=tenant_id, domain='journal')
```

### Index Optimization

Ensure these indexes exist for sync operations:

```sql
-- Conflict policies (already indexed in migration)
CREATE INDEX idx_conflict_policy_tenant_domain ON sync_tenant_conflict_policy(tenant_id, domain);
CREATE INDEX idx_conflict_policy_auto_resolve ON sync_tenant_conflict_policy(auto_resolve);

-- Sync analytics
CREATE INDEX idx_sync_analytics_timestamp ON sync_analytics_snapshot(timestamp DESC);
CREATE INDEX idx_sync_analytics_tenant_time ON sync_analytics_snapshot(tenant_id, timestamp DESC);

-- Device health
CREATE INDEX idx_device_health_device ON sync_device_health(device_id);
CREATE INDEX idx_device_health_user_tenant ON sync_device_health(user_id, tenant_id);
CREATE INDEX idx_device_health_score ON sync_device_health(health_score);

-- Upload sessions
CREATE INDEX idx_upload_session_user_status ON upload_session(user_id, status);
CREATE INDEX idx_upload_session_expires ON upload_session(expires_at) WHERE status = 'active';
```

## Performance Benchmarks

### Target Metrics

| Metric | Target | Current (Baseline) |
|--------|--------|-------------------|
| P95 Sync Latency | < 200ms | ~150ms |
| Throughput | 1,000 syncs/sec | ~500 syncs/sec |
| Conflict Resolution | < 50ms | ~30ms |
| Cache Hit Rate | > 80% | ~60% |
| Database Connections | < 50 active | ~30 active |

### Load Testing Results

Run load tests to validate performance:

```bash
# Run sync load test
cd testing/load_testing
python sync_load_test.py --scenario all --duration 300

# Expected results:
# - 1,000 concurrent requests: < 200ms P95
# - 10,000 items/minute: 100% success
# - 0% data loss under load
```

## Monitoring

### Key Metrics to Monitor

1. **Database Connection Pool:**
   - Active connections
   - Idle connections
   - Connection wait time

2. **Sync Performance:**
   - Request latency (P50, P95, P99)
   - Throughput (requests/second)
   - Error rate

3. **Cache Performance:**
   - Hit rate (should be > 80%)
   - Miss rate
   - Eviction rate

### PostgreSQL Monitoring Queries

```sql
-- Active connections by state
SELECT state, count(*)
FROM pg_stat_activity
WHERE datname = 'intelliwiz_db'
GROUP BY state;

-- Long-running queries (> 1 second)
SELECT pid, now() - query_start as duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '1 second'
ORDER BY duration DESC;

-- Table bloat and maintenance
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename LIKE 'sync_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Optimization Checklist

- [ ] Verify CONN_MAX_AGE is set appropriately (300-600 for production)
- [ ] Consider pgBouncer for connection pooling at scale
- [ ] Ensure all sync queries use select_related()/prefetch_related()
- [ ] Enable Redis caching for tenant policies
- [ ] Monitor cache hit rates (target > 80%)
- [ ] Run load tests to validate P95 latency < 200ms
- [ ] Set up database connection monitoring
- [ ] Configure slow query logging (> 100ms)
- [ ] Schedule regular VACUUM and ANALYZE on sync tables
- [ ] Review and optimize indexes quarterly

## Troubleshooting

### High Connection Count

**Symptoms:** Database refusing connections, `Too many connections` error

**Solutions:**
1. Check for connection leaks:
   ```python
   from django.db import connection
   print(f"Queries executed: {len(connection.queries)}")
   ```
2. Reduce CONN_MAX_AGE if connections idle too long
3. Implement pgBouncer for connection pooling
4. Increase PostgreSQL `max_connections` (with caution)

### Slow Sync Performance

**Symptoms:** P95 latency > 500ms, timeout errors

**Solutions:**
1. Check for missing indexes with EXPLAIN ANALYZE
2. Verify cache hit rate (should be > 80%)
3. Look for N+1 query patterns
4. Consider database query optimization
5. Scale horizontally with read replicas

### Cache Thrashing

**Symptoms:** High cache miss rate, frequent evictions

**Solutions:**
1. Increase Redis memory allocation
2. Review cache TTL settings (currently 1 hour for policies)
3. Warm cache during deployment
4. Implement cache preloading for high-traffic tenants

---

**Last Updated:** 2025-09-28
**Maintained By:** Platform Engineering Team