# Sync Outage Response Runbook

## Severity Classification

| Severity | Description | Response Time | Example |
|----------|-------------|---------------|---------|
| **P0 - Critical** | Complete sync outage | < 15 minutes | All sync requests failing |
| **P1 - High** | Partial outage (> 50% failure) | < 30 minutes | 50%+ users affected |
| **P2 - Medium** | Degraded performance | < 2 hours | High latency but functional |
| **P3 - Low** | Minor issues | < 24 hours | Single tenant affected |

---

## P0: Complete Sync Outage

### Symptoms
- Success rate < 50%
- All WebSocket connections failing
- Database unreachable
- Redis cache unavailable

### Immediate Actions (First 5 Minutes)

1. **Verify the outage:**
   ```bash
   # Check sync health
   python manage.py monitor_sync_health --hours 1

   # Check WebSocket connectivity
   wscat -c wss://api.example.com/ws/mobile/sync/?device_id=test
   ```

2. **Check system status:**
   ```bash
   # Application server
   sudo systemctl status daphne

   # Database
   sudo systemctl status postgresql
   psql -U dbuser -d intelliwiz_db -c "SELECT 1;"

   # Redis
   sudo systemctl status redis
   redis-cli ping

   # Load balancer
   curl https://api.example.com/health
   ```

3. **Alert stakeholders:**
   - Post in #incidents Slack channel
   - Update status page: "Investigating sync service issues"
   - Page on-call engineer if outside business hours

### Root Cause Investigation (5-15 Minutes)

#### Scenario A: Database Unavailable

**Symptoms:** PostgreSQL not responding

**Actions:**
```bash
# Check database logs
sudo tail -n 500 /var/log/postgresql/postgresql-14-main.log

# Check connection count
psql -U dbuser -d intelliwiz_db -c "SELECT COUNT(*) FROM pg_stat_activity;"

# Check for locks
psql -U dbuser -d intelliwiz_db -c "
SELECT pid, state, query, wait_event_type
FROM pg_stat_activity
WHERE state = 'active' AND wait_event_type IS NOT NULL;
"

# If connection maxed out, kill idle connections
psql -U dbuser -d intelliwiz_db -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle' AND state_change < NOW() - INTERVAL '5 minutes';
"

# Restart PostgreSQL (LAST RESORT)
sudo systemctl restart postgresql
```

#### Scenario B: Application Server Crashed

**Symptoms:** Daphne process not running

**Actions:**
```bash
# Check application logs
sudo tail -n 500 /var/log/intelliwiz/error.log | grep -i "error\|exception\|traceback"

# Check system resources
free -h
df -h
top -b -n 1 | head -20

# Restart Daphne
sudo systemctl restart daphne
sudo systemctl status daphne

# Verify recovery
curl https://api.example.com/health
```

#### Scenario C: Redis Cache Failure

**Symptoms:** Redis unavailable

**Actions:**
```bash
# Check Redis logs
sudo tail -n 500 /var/log/redis/redis-server.log

# Check Redis memory
redis-cli info memory

# Restart Redis
sudo systemctl restart redis

# Verify cache rebuilt
python manage.py shell -c "from django.core.cache import cache; print(cache.get('test_key'))"

# Warm cache
from apps.core.services.sync_cache_service import sync_cache_service
from apps.tenants.models import Tenant
for tenant in Tenant.objects.all():
    sync_cache_service.warm_cache_for_tenant(tenant.id)
```

#### Scenario D: Network/Load Balancer Issue

**Symptoms:** Application healthy but unreachable

**Actions:**
```bash
# Check nginx status
sudo systemctl status nginx
sudo nginx -t

# Check nginx logs
sudo tail -n 500 /var/log/nginx/error.log

# Check network connectivity
ping api.example.com
telnet api.example.com 443

# Check SSL certificate
openssl s_client -connect api.example.com:443 -servername api.example.com

# Restart nginx
sudo systemctl restart nginx
```

### Resolution & Validation (15-30 Minutes)

1. **Verify fix:**
   ```bash
   # Run smoke tests
   python testing/load_testing/sync_load_test.py --scenario concurrent --connections 100

   # Check health metrics
   python manage.py monitor_sync_health --hours 1
   ```

2. **Monitor recovery:**
   ```bash
   # Watch success rate for 10 minutes
   watch -n 10 'python manage.py monitor_sync_health --hours 1 | grep "Success Rate"'
   ```

3. **Update stakeholders:**
   - Post resolution in #incidents
   - Update status page: "Sync service restored"
   - Schedule post-mortem within 24 hours

### Post-Incident Review (Within 24 Hours)

1. **Document timeline:**
   - Detection time
   - Response time
   - Resolution time
   - Total downtime

2. **Root cause analysis:**
   - What happened?
   - Why did it happen?
   - Why wasn't it detected earlier?

3. **Action items:**
   - Preventive measures
   - Monitoring improvements
   - Runbook updates

---

## P1: Partial Outage (50%+ Failure)

### Symptoms
- Success rate 50-95%
- Some tenants affected
- High error rate for specific operations

### Actions

1. **Identify scope:**
   ```bash
   # Check per-tenant success rates
   python manage.py shell
   from apps.core.models.sync_analytics import SyncAnalyticsSnapshot
   for snapshot in SyncAnalyticsSnapshot.objects.filter(timestamp__gte=timezone.now() - timedelta(hours=1)):
       print(f"Tenant {snapshot.tenant_id}: {snapshot.success_rate_pct:.1f}%")
   ```

2. **Isolate affected tenants:**
   - Identify common characteristics
   - Check tenant-specific configurations
   - Review recent changes for affected tenants

3. **Mitigate impact:**
   - Rate limit affected operations if needed
   - Scale up resources if capacity issue
   - Redirect affected users to maintenance page

---

## P2: Degraded Performance

### Symptoms
- P95 latency > 500ms
- Slow database queries
- High CPU/memory usage

### Actions

1. **Identify bottleneck:**
   ```sql
   -- Slow queries
   SELECT pid, now() - query_start as duration, query
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - query_start > interval '1 second'
   ORDER BY duration DESC;

   -- Missing indexes
   SELECT schemaname, tablename, attname, n_distinct, correlation
   FROM pg_stats
   WHERE schemaname = 'public' AND tablename LIKE 'sync_%'
   ORDER BY abs(correlation) DESC;
   ```

2. **Optimize queries:**
   - Add missing indexes
   - Use EXPLAIN ANALYZE
   - Optimize N+1 patterns

3. **Scale resources:**
   - Add more application servers
   - Increase database connection pool
   - Scale Redis cache

---

## Communication Templates

### Initial Alert

```
🚨 Sync Service Outage - Investigating

Status: INVESTIGATING
Severity: P0
Started: 2025-09-28 12:00 UTC
Impact: All mobile sync operations failing

We are actively investigating sync service issues. Updates will be provided every 15 minutes.
```

### Resolution Alert

```
✅ Sync Service Restored

Status: RESOLVED
Severity: P0
Started: 2025-09-28 12:00 UTC
Resolved: 2025-09-28 12:25 UTC
Downtime: 25 minutes

Root Cause: Database connection pool exhaustion
Fix: Increased connection pool size and restarted services

Post-mortem will be published within 24 hours.
```

---

**Last Updated:** 2025-09-28
**On-Call Contact:** +1-555-SYNC-OPS