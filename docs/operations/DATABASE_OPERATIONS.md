# Database Operations Runbook

**Author:** Claude Code
**Date:** 2025-10-27
**Audience:** Operations Team

---

## Overview

This runbook covers PostgreSQL database operations, optimization, and troubleshooting.

---

## Health Checks

### Check Database Status

```bash
# PostgreSQL service status
sudo systemctl status postgresql

# Connection test
psql -U postgres -d intelliwiz_db -c "SELECT version();"

# Check for idle connections
psql -U postgres -d intelliwiz_db -c "
  SELECT count(*) as idle_connections
  FROM pg_stat_activity
  WHERE state = 'idle';
"

# Check active queries
psql -U postgres -d intelliwiz_db -c "
  SELECT pid, query_start, state, query
  FROM pg_stat_activity
  WHERE state = 'active'
  LIMIT 10;
"
```

### Monitor Dashboard

```bash
# Access web dashboard
open http://localhost:8000/admin/monitoring/database/

# API metrics
curl http://localhost:8000/admin/monitoring/database/api/metrics/
```

---

## Connection Pool Management

### Check Pool Configuration

```python
# View current settings
python manage.py shell
>>> from django.conf import settings
>>> pool = settings.DATABASES['default']['OPTIONS']['pool']
>>> print(f"Min: {pool['min_size']}, Max: {pool['max_size']}")
```

### Environment Variables

```bash
# Set pool size (before starting application)
export DB_POOL_MIN_SIZE=5
export DB_POOL_MAX_SIZE=20
export DB_POOL_TIMEOUT=30

# Verify settings
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['OPTIONS']['pool'])"
```

### Tune Pool Size

**Guidelines:**
- **Min size:** Start with 5
- **Max size:** (concurrent users / 4) or CPU cores * 2
- **Timeout:** 30 seconds default

**Production recommendations:**
- Low traffic (<100 users): min=5, max=20
- Medium traffic (100-500 users): min=10, max=50
- High traffic (>500 users): min=20, max=100

---

## Query Performance

### Identify Slow Queries

```bash
# View slow query log (last 24 hours)
# Access dashboard or run:
python manage.py shell
>>> from apps.core.models.query_performance import QueryPerformance
>>> from datetime import timedelta
>>> from django.utils import timezone
>>> slow = QueryPerformance.objects.filter(
...     executed_at__gte=timezone.now() - timedelta(hours=24),
...     execution_time__gte=1.0
... ).order_by('-execution_time')[:20]
>>> for q in slow:
...     print(f"{q.execution_time}s - {q.query_type}")
```

### Enable Query Logging

```python
# Temporary (for debugging)
python manage.py shell_plus --print-sql

# Permanent (in settings)
# Add to intelliwiz_config/settings/development.py:
LOGGING['loggers']['django.db.backends'] = {
    'level': 'DEBUG',
    'handlers': ['console'],
}
```

---

## Index Management

### Check Index Usage

```sql
-- View index statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 20;

-- Find unused indexes (scans = 0)
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexname NOT LIKE '%_pkey';
```

### Add Missing Indexes

```bash
# Audit database indexes
python manage.py audit_database_indexes

# Auto-create recommended indexes (if available)
python scripts/utilities/create_orm_indexes.py
```

---

## Common Issues & Solutions

### Issue 1: Connection Pool Exhausted

**Symptoms:**
- `psycopg.OperationalError: connection pool exhausted`
- Users getting 500 errors
- Long page load times

**Diagnosis:**
```bash
# Check current connections
psql -U postgres -d intelliwiz_db -c "
  SELECT count(*)
  FROM pg_stat_activity
  WHERE datname = 'intelliwiz_db';
"

# Check connection pool setting
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['OPTIONS']['pool']['max_size'])"
```

**Solutions:**
1. **Increase pool size:**
   ```bash
   export DB_POOL_MAX_SIZE=50
   sudo systemctl restart gunicorn
   ```

2. **Kill idle connections:**
   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE datname = 'intelliwiz_db'
     AND state = 'idle'
     AND state_change < now() - interval '10 minutes';
   ```

3. **Check for connection leaks:**
   - Review code for missing `connection.close()`
   - Enable `ATOMIC_REQUESTS = True` (already enabled)

---

### Issue 2: Slow Queries

**Symptoms:**
- Dashboard shows queries >1 second
- High database CPU usage
- User complaints about slow pages

**Diagnosis:**
```sql
-- Find slow queries (pg_stat_statements required)
SELECT
    query,
    mean_exec_time,
    calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Solutions:**
1. **Add indexes:**
   - Check EXPLAIN ANALYZE for query
   - Add indexes on WHERE/JOIN columns

2. **Optimize queries:**
   - Use `select_related()` for foreign keys
   - Use `prefetch_related()` for many-to-many
   - Add `.only()` to limit columns

3. **Example optimization:**
   ```python
   # BEFORE (N+1 query)
   jobs = Job.objects.all()
   for job in jobs:
       print(job.asset.name)  # Extra query per job!

   # AFTER (optimized)
   jobs = Job.objects.select_related('asset').all()
   for job in jobs:
       print(job.asset.name)  # No extra queries!
   ```

---

### Issue 3: Database Locks

**Symptoms:**
- Transactions timing out
- Users seeing "database locked" errors
- Long-running queries blocking others

**Diagnosis:**
```sql
-- View blocking queries
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.query AS blocked_query,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**Solutions:**
1. **Kill blocking query:**
   ```sql
   SELECT pg_cancel_backend(12345);  -- Cancel query (PID from diagnosis)
   SELECT pg_terminate_backend(12345);  -- Force terminate if cancel fails
   ```

2. **Prevent locks:**
   - Keep transactions short
   - Avoid long-running queries in transactions
   - Use `SELECT FOR UPDATE NOWAIT` for explicit locking

---

## Performance Optimization

### Vacuum & Analyze

```bash
# Auto-vacuum stats
psql -U postgres -d intelliwiz_db -c "
  SELECT
    schemaname,
    tablename,
    last_vacuum,
    last_autovacuum,
    n_dead_tup
  FROM pg_stat_user_tables
  WHERE n_dead_tup > 1000
  ORDER BY n_dead_tup DESC;
"

# Manual vacuum (if needed)
psql -U postgres -d intelliwiz_db -c "VACUUM ANALYZE;"

# Vacuum specific table
psql -U postgres -d intelliwiz_db -c "VACUUM ANALYZE activity_job;"
```

### Update Statistics

```bash
# Analyze tables for query planner
psql -U postgres -d intelliwiz_db -c "ANALYZE;"

# Specific table
psql -U postgres -d intelliwiz_db -c "ANALYZE activity_asset;"
```

---

## Backup & Recovery

### Manual Backup

```bash
# Full backup
pg_dump -U postgres -d intelliwiz_db -F c -f /backups/intelliwiz_$(date +%Y%m%d).dump

# Schema only
pg_dump -U postgres -d intelliwiz_db -s -f /backups/schema_$(date +%Y%m%d).sql

# Data only
pg_dump -U postgres -d intelliwiz_db -a -f /backups/data_$(date +%Y%m%d).sql

# Specific tables
pg_dump -U postgres -d intelliwiz_db -t activity_job -t activity_asset -f /backups/activity_$(date +%Y%m%d).dump
```

### Restore from Backup

```bash
# Full restore (CAUTION: drops existing database)
pg_restore -U postgres -d postgres -C /backups/intelliwiz_20251027.dump

# Restore specific table
pg_restore -U postgres -d intelliwiz_db -t activity_job /backups/activity_20251027.dump

# Restore data only (preserves schema)
psql -U postgres -d intelliwiz_db -f /backups/data_20251027.sql
```

---

## Maintenance Windows

### Recommended Schedule

**Daily (automated):**
- Auto-vacuum runs continuously
- Statistics updated by autovacuum

**Weekly:**
- Review slow queries
- Check for missing indexes
- Vacuum analyze (if autovacuum insufficient)

**Monthly:**
- Full vacuum (during low-traffic window)
- Reindex critical tables
- Update PostgreSQL minor version

### Execute Maintenance

```bash
# During maintenance window (low traffic)

# 1. Announce maintenance
# 2. Full vacuum and analyze
psql -U postgres -d intelliwiz_db -c "VACUUM FULL ANALYZE;"

# 3. Reindex critical tables
psql -U postgres -d intelliwiz_db -c "REINDEX TABLE activity_job;"
psql -U postgres -d intelliwiz_db -c "REINDEX TABLE peoples_people;"

# 4. Update statistics
psql -U postgres -d intelliwiz_db -c "ANALYZE;"

# 5. Verify health
python manage.py check --database default
```

---

## Monitoring Alerts

### Recommended Thresholds

| Alert | Threshold | Action |
|-------|-----------|--------|
| Connection pool >80% | Warn | Plan to scale |
| Slow queries >5s | Alert | Investigate immediately |
| Database size growth >10% per day | Warn | Check for data issues |
| Failed health checks | Critical | Page on-call engineer |

---

## References

- Dashboard: http://localhost:8000/admin/monitoring/database/
- Configuration: `intelliwiz_config/settings/database.py`
- Connection Pooling: psycopg3 native pools
- Index Audit: `python manage.py audit_database_indexes`
