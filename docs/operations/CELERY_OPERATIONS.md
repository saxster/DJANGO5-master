# Celery Operations Runbook

**Author:** Claude Code
**Date:** 2025-10-27
**Audience:** Operations Team

---

## Overview

This runbook covers day-to-day operations of the Celery distributed task queue system.

---

## Starting/Stopping Services

### Start Celery Workers

```bash
# Development - single worker
celery -A intelliwiz_config worker --loglevel=info

# Production - multi-queue workers
celery -A intelliwiz_config worker \
  -Q critical,high_priority,email,reports,maintenance \
  --concurrency=4 \
  --loglevel=warning

# Using systemd service (production)
sudo systemctl start celery-workers
sudo systemctl enable celery-workers
```

### Start Beat Scheduler

```bash
# Development
celery -A intelliwiz_config beat --loglevel=info

# Production (systemd)
sudo systemctl start celery-beat
sudo systemctl enable celery-beat
```

### Stop Services

```bash
# Graceful shutdown
celery -A intelliwiz_config control shutdown

# Force stop (systemd)
sudo systemctl stop celery-workers
sudo systemctl stop celery-beat
```

---

## Health Checks

### Check Worker Status

```bash
# List active workers
celery -A intelliwiz_config inspect active

# Check worker stats
celery -A intelliwiz_config inspect stats

# Check registered tasks
celery -A intelliwiz_config inspect registered
```

### Validate Task Configuration

```bash
# Run task audit
python scripts/audit_celery_tasks.py --generate-report

# Check for orphaned beat tasks
python scripts/audit_celery_tasks.py --orphaned-only

# Validate beat schedule
python manage.py validate_schedules --verbose
python manage.py validate_schedules --check-orphaned-tasks
python manage.py validate_schedules --check-duplicates
```

### Monitor Dashboard

```bash
# Access web dashboard
open http://localhost:8000/admin/monitoring/celery/

# API metrics
curl http://localhost:8000/admin/monitoring/celery/api/metrics/
```

---

## Common Issues & Solutions

### Issue 1: Tasks Not Executing

**Symptoms:**
- Tasks queued but not processing
- Worker shows 0 active tasks

**Diagnosis:**
```bash
# Check worker is running
celery -A intelliwiz_config inspect ping

# Check queue depth
celery -A intelliwiz_config inspect reserved

# Check for errors
tail -f /var/log/celery/worker.log
```

**Solutions:**
1. Restart workers: `sudo systemctl restart celery-workers`
2. Check Redis connection: `redis-cli ping`
3. Verify queue routing in `intelliwiz_config/celery.py`

---

### Issue 2: Beat Tasks Running Twice

**Symptoms:**
- Duplicate emails sent
- Duplicate database records

**Diagnosis:**
```bash
# Check for multiple beat instances
ps aux | grep "celery.*beat"

# Check beat schedule conflicts
python manage.py validate_schedules --check-duplicates
```

**Solutions:**
1. Ensure only ONE beat instance running
2. Verify idempotency enabled on tasks
3. Kill duplicate beat processes:
   ```bash
   pkill -f "celery.*beat"
   celery -A intelliwiz_config beat --loglevel=info
   ```

---

### Issue 3: Tasks Failing with Retries

**Symptoms:**
- High retry rates in dashboard
- Tasks eventually fail after 3 retries

**Diagnosis:**
```bash
# Check retry patterns
python manage.py shell
>>> from apps.core.tasks.base import TaskMetrics
>>> from apps.core.caching.utils import get_cache_invalidation_stats
>>> # Analyze retry reasons
```

**Solutions:**
1. Check external service availability (network, database)
2. Increase retry delay: Edit task `default_retry_delay`
3. Check circuit breaker status in logs

---

### Issue 4: Queue Buildup

**Symptoms:**
- Queue depth >100 tasks
- Tasks delayed by hours

**Diagnosis:**
```bash
# Check queue depths
celery -A intelliwiz_config inspect reserved

# Check worker concurrency
celery -A intelliwiz_config inspect stats | grep concurrency
```

**Solutions:**
1. Scale workers:
   ```bash
   # Increase concurrency
   celery -A intelliwiz_config worker --concurrency=8
   ```
2. Check for stuck tasks:
   ```bash
   celery -A intelliwiz_config inspect active
   ```
3. Purge stuck queues (CAUTION):
   ```bash
   celery -A intelliwiz_config purge -Q maintenance
   ```

---

## Monitoring & Alerts

### Key Metrics to Watch

| Metric | Healthy | Warning | Critical | Action |
|--------|---------|---------|----------|--------|
| Task success rate | >95% | 90-95% | <90% | Investigate failures |
| Queue depth | <50 | 50-100 | >100 | Scale workers |
| Worker count | ≥2 | 1 | 0 | Start workers immediately |
| Retry rate | <5% | 5-10% | >10% | Check external services |

### Alerts to Configure

1. **Worker Down:** Alert when worker count = 0
2. **High Failure Rate:** Alert when success rate <90%
3. **Queue Buildup:** Alert when queue depth >100
4. **Beat Stopped:** Alert when no beat heartbeat for 5 minutes

---

## Scaling Operations

### Horizontal Scaling (Add Workers)

```bash
# Start additional worker on same server
celery -A intelliwiz_config worker -Q critical,high_priority --concurrency=2 &

# Start worker on different server
# 1. Ensure Redis accessible from new server
# 2. Deploy code to new server
# 3. Start worker with same command
```

### Queue-Specific Scaling

```bash
# Scale only critical queue
celery -A intelliwiz_config worker -Q critical --concurrency=4

# Scale reports queue separately
celery -A intelliwiz_config worker -Q reports --concurrency=2
```

---

## Maintenance

### Scheduled Maintenance

**Daily:**
- Check dashboard for failures
- Review retry patterns

**Weekly:**
- Analyze slow tasks (avg execution time)
- Review beat schedule health
- Check for orphaned tasks

**Monthly:**
- Update Celery version (test in staging first)
- Review queue routing efficiency
- Archive old task logs

### Purge Old Results

```bash
# Clear old task results (older than 7 days)
celery -A intelliwiz_config purge

# Clear specific queue
celery -A intelliwiz_config purge -Q maintenance
```

---

## Emergency Procedures

### Stop All Tasks Immediately

```bash
# Terminate all active tasks
celery -A intelliwiz_config control terminate

# Stop workers
sudo systemctl stop celery-workers

# Stop beat
sudo systemctl stop celery-beat
```

### Recover from Redis Failure

```bash
# 1. Verify Redis is down
redis-cli ping  # Should fail

# 2. Restart Redis
sudo systemctl restart redis

# 3. Restart Celery workers
sudo systemctl restart celery-workers

# 4. Verify recovery
celery -A intelliwiz_config inspect ping
```

---

## Performance Tuning

### Worker Concurrency

```bash
# Default concurrency = CPU count
celery -A intelliwiz_config worker --concurrency=4

# High I/O workloads (increase concurrency)
celery -A intelliwiz_config worker --concurrency=16

# CPU-bound tasks (match CPU count)
celery -A intelliwiz_config worker --concurrency=4
```

### Prefetch Multiplier

```python
# In intelliwiz_config/settings/base.py
CELERY_WORKER_PREFETCH_MULTIPLIER = 4  # Default
# Increase for short tasks: 8
# Decrease for long tasks: 1
```

---

## References

- Dashboard: http://localhost:8000/admin/monitoring/celery/
- Configuration: `intelliwiz_config/celery.py`
- Task Audit: `python scripts/audit_celery_tasks.py`
- Documentation: `docs/architecture/BACKGROUND_JOBS_ARCHITECTURE.md`
