# Mobile Sync Deployment Runbook

## Pre-Deployment Checklist

### 1. Environment Validation

- [ ] PostgreSQL 14.2+ with PostGIS extension installed
- [ ] Redis 6.0+ running and accessible
- [ ] Python 3.10+ with all dependencies from `requirements.txt`
- [ ] Daphne ASGI server configured
- [ ] SSL certificates valid (for wss:// connections)
- [ ] Load balancer configured for WebSocket sticky sessions

### 2. Configuration Review

- [ ] `DATABASES['CONN_MAX_AGE']` set to 600 (production)
- [ ] Redis cache configured for sync services
- [ ] `SYNC_ALERT_WEBHOOK` and `SYNC_SLACK_WEBHOOK` configured
- [ ] `CORS_ALLOWED_ORIGINS` includes mobile app domains
- [ ] `ALLOWED_HOSTS` includes all server hostnames

### 3. Database Preparation

```bash
# Backup current database
pg_dump -U dbuser -d intelliwiz_db -F c -f backup_pre_sync_$(date +%Y%m%d).dump

# Verify backup
pg_restore --list backup_pre_sync_$(date +%Y%m%d).dump | head -20

# Check database size and available space
psql -U dbuser -d intelliwiz_db -c "SELECT pg_size_pretty(pg_database_size('intelliwiz_db'));"
df -h /var/lib/postgresql
```

---

## Migration Sequence

### Run Migrations in Order

**CRITICAL:** Run migrations in the exact order specified below.

```bash
# 1. Sync idempotency model
python manage.py migrate core 0010_sync_idempotency_record

# 2. Conflict policy models
python manage.py migrate core 0011_tenant_conflict_policy

# 3. Analytics models
python manage.py migrate core 0012_sync_analytics_models

# 4. Upload session model
python manage.py migrate core 0013_upload_session

# 5. Device health model
python manage.py migrate core 0014_sync_device_health

# 6. Conflict resolution log
python manage.py migrate core 0015_conflict_resolution_log

# 7. Voice verification log (if not exists)
python manage.py migrate voice_recognition 0001_voice_verification_log
```

### Verify Migrations

```bash
# Check migration status
python manage.py showmigrations core voice_recognition

# Verify indexes created
psql -U dbuser -d intelliwiz_db -c "
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename LIKE 'sync_%'
ORDER BY tablename, indexname;
"

# Verify foreign keys
psql -U dbuser -d intelliwiz_db -c "
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name LIKE 'sync_%';
"
```

### Performance Check

Run EXPLAIN ANALYZE on critical queries:

```sql
-- Idempotency lookup (should use index)
EXPLAIN ANALYZE
SELECT * FROM sync_idempotency_record
WHERE idempotency_key = 'test_key'
  AND expires_at > NOW();

-- Conflict policy lookup (should use index)
EXPLAIN ANALYZE
SELECT * FROM sync_tenant_conflict_policy
WHERE tenant_id = 1 AND domain = 'journal';

-- Device health lookup (should use index)
EXPLAIN ANALYZE
SELECT * FROM sync_device_health
WHERE device_id = 'test_device' AND user_id = 1;
```

Expected: All queries should use Index Scan, not Seq Scan.

---

## Application Deployment

### 1. Code Deployment

```bash
# Pull latest code
git fetch origin
git checkout v2.0.0-sync  # Tag or branch

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Verify no syntax errors
python manage.py check --deploy
```

### 2. Service Configuration

**Daphne Service (systemd)**

```ini
# /etc/systemd/system/daphne.service
[Unit]
Description=Daphne ASGI Server
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/intelliwiz
ExecStart=/opt/intelliwiz/venv/bin/daphne \
    -b 0.0.0.0 \
    -p 8000 \
    --proxy-headers \
    intelliwiz_config.asgi:application
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart daphne
sudo systemctl status daphne
```

### 3. Load Balancer Configuration

**Nginx WebSocket Proxy:**

```nginx
upstream daphne_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;  # Add more for HA
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/ssl/certs/example.com.crt;
    ssl_certificate_key /etc/ssl/private/example.com.key;

    location /ws/ {
        proxy_pass http://daphne_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket timeouts
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location /api/ {
        proxy_pass http://daphne_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Post-Deployment Validation

### 1. Smoke Tests

```bash
# Test WebSocket connection
python testing/load_testing/sync_load_test.py --scenario concurrent --connections 10

# Test upload functionality
curl -X POST https://api.example.com/api/v1/uploads/init \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.pdf","total_size":1048576,"mime_type":"application/pdf","file_hash":"abc123"}'

# Test health check
python manage.py monitor_sync_health --hours 1
```

### 2. Performance Validation

Run full load test in staging:

```bash
cd testing/load_testing
python sync_load_test.py --scenario all --duration 300

# Expected results:
# ✅ P95 latency < 200ms
# ✅ 0% data loss
# ✅ 100% conflict resolution accuracy
```

### 3. Monitoring Setup

```bash
# Start continuous health monitoring
python manage.py monitor_sync_health --continuous --interval 300 \
  --slack-webhook https://hooks.slack.com/services/YOUR/WEBHOOK/URL &

# Verify metrics collection
psql -U dbuser -d intelliwiz_db -c "SELECT COUNT(*) FROM sync_analytics_snapshot WHERE timestamp > NOW() - INTERVAL '1 hour';"
```

---

## Cron Job Configuration

Add to crontab (`crontab -e`):

```cron
# Cleanup expired records every hour
0 * * * * cd /opt/intelliwiz && /opt/intelliwiz/venv/bin/python manage.py shell -c "from apps.core.services.sync_async_processor import sync_async_processor; import asyncio; asyncio.run(sync_async_processor.cleanup_expired_records_async())"

# Aggregate analytics every hour
15 * * * * cd /opt/intelliwiz && /opt/intelliwiz/venv/bin/python manage.py shell -c "from apps.core.services.sync_async_processor import sync_async_processor; import asyncio; asyncio.run(sync_async_processor.aggregate_analytics_async())"

# Warm cache daily at 2 AM
0 2 * * * cd /opt/intelliwiz && /opt/intelliwiz/venv/bin/python manage.py shell -c "from apps.core.services.sync_cache_service import sync_cache_service; from apps.tenants.models import Tenant; [sync_cache_service.warm_cache_for_tenant(t.id) for t in Tenant.objects.all()]"
```

---

## Blue-Green Deployment Strategy

### Preparation

1. **Deploy to green environment** (no traffic)
2. **Run smoke tests** on green
3. **Warm cache** on green environment
4. **Monitor green** for 10 minutes

### Cutover

1. **Update load balancer** to route 10% traffic to green
2. **Monitor metrics** for 5 minutes
3. **Gradually increase** to 50%, then 100%
4. **Keep blue environment** running for 30 minutes

### Validation

```bash
# Check active connections by environment
psql -U dbuser -d intelliwiz_db -c "
SELECT application_name, COUNT(*)
FROM pg_stat_activity
WHERE datname = 'intelliwiz_db'
GROUP BY application_name;
"

# Monitor error rates
tail -f /var/log/intelliwiz/error.log | grep "SYNC_ERROR"
```

---

## Rollback Plan

### Immediate Rollback (< 5 minutes)

```bash
# 1. Switch load balancer back to blue environment
sudo nginx -s reload  # Or update ALB target group

# 2. Verify traffic restored
curl https://api.example.com/health

# 3. Investigate green environment logs
tail -n 1000 /var/log/intelliwiz/error.log
```

### Database Rollback (< 30 minutes)

**ONLY if migrations are causing issues:**

```bash
# 1. Stop application servers
sudo systemctl stop daphne

# 2. Revert migrations (reverse order)
python manage.py migrate voice_recognition 0000_initial
python manage.py migrate core 0009_previous_migration

# 3. Restore database backup (LAST RESORT)
pg_restore -U dbuser -d intelliwiz_db -c backup_pre_sync_$(date +%Y%m%d).dump

# 4. Restart application
sudo systemctl start daphne
```

---

## Monitoring Dashboards

### Key Metrics to Monitor (First 24 Hours)

1. **Sync Performance:**
   - WebSocket connection count
   - Sync request latency (P50, P95, P99)
   - Success rate (should be > 95%)
   - Conflict rate (should be < 5%)

2. **System Health:**
   - Database connection pool utilization
   - Redis cache hit rate (should be > 80%)
   - Application server CPU/memory
   - Disk I/O for upload temp storage

3. **Error Rates:**
   - HTTP 5xx errors
   - WebSocket connection failures
   - Database query failures
   - Cache misses

### Alert Configuration

Ensure these alerts are configured:

- [ ] Success rate < 95% → Critical alert
- [ ] P95 latency > 500ms → Warning alert
- [ ] Failed syncs > 10/minute → Critical alert
- [ ] Upload abandonment > 20% → Warning alert
- [ ] Database connections > 90% → Critical alert

---

## Troubleshooting Common Issues

See [Troubleshooting Guide](../mobile-sync/troubleshooting.md) for detailed procedures.

---

**Last Updated:** 2025-09-28
**Version:** 1.0