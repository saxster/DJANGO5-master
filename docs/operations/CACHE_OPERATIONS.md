# Cache Operations Runbook

**Author:** Claude Code
**Date:** 2025-10-27
**Audience:** Operations Team

---

## Overview

This runbook covers Redis cache operations, monitoring, and troubleshooting.

---

## Health Checks

### Check Redis Status

```bash
# Ping Redis
redis-cli ping
# Expected: PONG

# Check Redis info
redis-cli info | grep -E "redis_version|used_memory|connected_clients"

# Check specific database
redis-cli -n 1 DBSIZE  # Default cache (DB 1)
redis-cli -n 3 DBSIZE  # Select2 cache (DB 3)
redis-cli -n 4 DBSIZE  # Sessions (DB 4)
redis-cli -n 0 DBSIZE  # Celery broker (DB 0)
redis-cli -n 2 DBSIZE  # Channel layers (DB 2)
```

### Monitor Dashboard

```bash
# Access web dashboard
open http://localhost:8000/admin/monitoring/cache/

# Verify configuration
python scripts/verify_redis_cache_config.py
python scripts/verify_redis_cache_config.py --environment production
```

---

## Common Issues & Solutions

### Issue 1: Cache Miss Rate High (>50%)

**Symptoms:**
- Dashboard shows low hit rate
- Slow page loads
- High database load

**Diagnosis:**
```bash
# Check hit/miss ratio
redis-cli INFO stats | grep keyspace

# Check memory usage
redis-cli INFO memory | grep used_memory
```

**Solutions:**
1. **Warm caches:**
   ```python
   python manage.py shell
   >>> from apps.core.caching.invalidation import warm_dropdown_caches
   >>> warm_dropdown_caches(tenant_id=1)
   ```

2. **Increase cache TTL** (if appropriate):
   - Edit `intelliwiz_config/settings/redis_optimized.py`
   - Increase `TIMEOUT` values

3. **Check for cache thrashing:**
   - Review invalidation patterns
   - Reduce unnecessary invalidations

---

### Issue 2: Redis Memory Full

**Symptoms:**
- Redis OOM errors
- Cache writes failing
- `MISCONF` errors

**Diagnosis:**
```bash
# Check memory usage
redis-cli INFO memory

# Check eviction policy
redis-cli CONFIG GET maxmemory-policy
```

**Solutions:**
1. **Increase Redis memory:**
   ```bash
   redis-cli CONFIG SET maxmemory 2gb
   ```

2. **Enable eviction:**
   ```bash
   redis-cli CONFIG SET maxmemory-policy allkeys-lru
   ```

3. **Clear specific database:**
   ```bash
   redis-cli -n 1 FLUSHDB  # Clear default cache
   ```

4. **Optimize cache usage:**
   - Review cache key patterns
   - Reduce TTL for less-critical caches
   - Enable compression in production

---

### Issue 3: Cache Invalidation Not Working

**Symptoms:**
- Stale data in dropdowns
- Users see old information
- Dashboard metrics don't update

**Diagnosis:**
```bash
# Check signal registration
python manage.py shell
>>> from apps.core.caching.invalidation import get_cache_invalidation_stats
>>> print(get_cache_invalidation_stats())

# Check recent invalidations in logs
grep "Auto-invalidated" /var/log/django/app.log | tail -20
```

**Solutions:**
1. **Manual cache clear:**
   ```python
   python manage.py shell
   >>> from apps.core.caching.invalidation import invalidate_cache_pattern
   >>> invalidate_cache_pattern('dropdown:*')
   ```

2. **Verify signals connected:**
   - Check `apps/core/apps.py` - signals should register on startup
   - Look for "Cache invalidation signals registered successfully" in logs

3. **Force invalidation:**
   ```python
   >>> from apps.core.caching.utils import clear_cache_pattern
   >>> clear_cache_pattern('tenant:*:*')
   ```

---

### Issue 4: Redis Connection Errors

**Symptoms:**
- `ConnectionError` in logs
- Cache operations failing
- `MISCONF` errors

**Diagnosis:**
```bash
# Check Redis is running
sudo systemctl status redis

# Test connection
redis-cli ping

# Check connection pool
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value', 60)
>>> print(cache.get('test'))
```

**Solutions:**
1. **Restart Redis:**
   ```bash
   sudo systemctl restart redis
   ```

2. **Check network connectivity:**
   ```bash
   telnet localhost 6379
   ```

3. **Verify settings:**
   - Check `REDIS_HOST`, `REDIS_PORT` in `.env`
   - Verify connection pool settings

---

## Monitoring

### Key Metrics to Watch

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Hit rate | >80% | 60-80% | <60% |
| Memory usage | <70% | 70-85% | >85% |
| Connected clients | <50 | 50-80 | >80 |
| Evictions/sec | 0 | <10 | >10 |

### Daily Checks

1. Check dashboard: http://localhost:8000/admin/monitoring/cache/
2. Review hit/miss ratios
3. Check memory usage trend
4. Review eviction rates

---

## Cache Warming

### Warm Critical Caches

```python
python manage.py shell

# Warm dropdown caches for all tenants
from apps.core.caching.invalidation import warm_dropdown_caches
for tenant_id in [1, 2, 3]:
    warm_dropdown_caches(tenant_id=tenant_id)

# Warm user permission caches
from apps.peoples.services.people_caching_service import warm_user_permission_cache
warm_user_permission_cache()
```

### Schedule Cache Warming

Already configured in beat schedule:
- `cache_warming_scheduled` runs every 15 minutes
- Queue: maintenance
- See: `background_tasks/maintenance_tasks.py`

---

## Distributed Invalidation

### How It Works

1. Model changes trigger `post_save` signal
2. Signal handler publishes invalidation event to Redis pub/sub
3. All app servers receive event and clear local caches
4. Ensures consistency across distributed deployment

### Test Distributed Invalidation

```python
# On server 1
from apps.core.caching.distributed_invalidation import publish_invalidation_event
publish_invalidation_event('dropdown:people', reason='manual_test')

# On server 2 - should see invalidation in logs
# Check logs for "Received invalidation event"
```

---

## Performance Optimization

### Enable Compression (Production Only)

Already enabled in production settings:
- Setting: `COMPRESSOR = 'django_redis.compressors.zlib.ZlibCompressor'`
- Location: `intelliwiz_config/settings/redis_optimized.py:254`

### Connection Pool Tuning

```python
# intelliwiz_config/settings/redis_optimized.py
CONNECTION_POOL_KWARGS = {
    'max_connections': 100,  # Increase for high traffic
    'health_check_interval': 30,  # Connection health checks
}
```

---

## Backup & Recovery

### Manual Redis Backup

```bash
# Save current state (synchronous)
redis-cli SAVE

# Save current state (background)
redis-cli BGSAVE

# Check last save time
redis-cli LASTSAVE

# Backup file location
ls -lh /var/lib/redis/dump.rdb
```

### Automated Backups

Already configured:
- Daily full backup: 3:30 AM (beat task)
- Hourly RDB snapshots
- See: `background_tasks/` (redis backup tasks)

### Restore from Backup

```bash
# 1. Stop Redis
sudo systemctl stop redis

# 2. Replace dump.rdb
sudo cp /backups/redis/dump.rdb /var/lib/redis/dump.rdb

# 3. Set permissions
sudo chown redis:redis /var/lib/redis/dump.rdb

# 4. Start Redis
sudo systemctl start redis

# 5. Verify data
redis-cli DBSIZE
```

---

## Security

### TLS/SSL Configuration

**Production Requirement (April 2025):**
- TLS MUST be enabled for PCI DSS compliance
- Set `REDIS_SSL_ENABLED=true` in environment

**Verify TLS:**
```bash
# Check TLS is enabled
python manage.py shell
>>> from intelliwiz_config.settings.redis_optimized import get_redis_tls_config
>>> print(get_redis_tls_config('production'))
```

### Password Rotation

```bash
# 1. Update Redis password
redis-cli CONFIG SET requirepass "new_strong_password"

# 2. Update environment variable
echo "REDIS_PASSWORD=new_strong_password" >> .env.production

# 3. Restart application
sudo systemctl restart gunicorn celery-workers

# 4. Verify connection
redis-cli -a new_strong_password ping
```

---

## Emergency Procedures

### Clear All Caches (CAUTION)

```bash
# Clear all databases (NUCLEAR OPTION)
redis-cli FLUSHALL

# Clear specific database
redis-cli -n 1 FLUSHDB  # Only default cache
```

### Restart Redis (Zero Downtime)

```bash
# With Redis Sentinel (production)
redis-cli -p 26379 SENTINEL failover mymaster

# Without Sentinel (dev/staging)
sudo systemctl restart redis
```

---

## References

- Dashboard: http://localhost:8000/admin/monitoring/cache/
- Configuration: `intelliwiz_config/settings/redis_optimized.py`
- Validation: `python scripts/verify_redis_cache_config.py`
