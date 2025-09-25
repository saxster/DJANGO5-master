# Production Runbooks: Django ORM System

## Table of Contents
1. [System Overview](#system-overview)
2. [Alert Response Procedures](#alert-response-procedures)
3. [Common Issues](#common-issues)
4. [Performance Troubleshooting](#performance-troubleshooting)
5. [Emergency Procedures](#emergency-procedures)
6. [Rollback Procedures](#rollback-procedures)
7. [Monitoring Procedures](#monitoring-procedures)
8. [Maintenance Tasks](#maintenance-tasks)

## System Overview

### Architecture Components
- **Django Application**: YOUTILITY3
- **Query System**: Django 5 ORM (migrated from raw SQL)
- **Cache Layer**: Redis/Django Cache
- **Monitoring**: Custom monitoring package with Prometheus/Grafana
- **Database**: PostgreSQL with 25+ optimized indexes

### Key Metrics
- Response time p95: < 1 second
- Database query p95: < 100ms
- Cache hit rate: > 70%
- Error rate: < 1%

## Alert Response Procedures

### ALERT: High Response Time (>1s p95)

**Severity**: Warning/Critical
**Notification**: Email, Slack, PagerDuty (if >2s)

**Steps:**
1. **Verify Alert**
   ```bash
   curl http://app-server:8000/monitoring/metrics/
   # Check response_time_p95
   ```

2. **Check Database Performance**
   ```bash
   curl http://app-server:8000/monitoring/performance/queries/
   # Look for slow queries
   ```

3. **Check Cache Performance**
   ```bash
   curl http://app-server:8000/monitoring/performance/cache/
   # Verify hit rate > 70%
   ```

4. **Identify Slow Endpoints**
   ```python
   # Django shell
   from monitoring.views import get_performance_summary
   summary = get_performance_summary()
   for endpoint in summary['slow_endpoints']:
       print(f"{endpoint['path']}: {endpoint['p95_time']}ms")
   ```

5. **Immediate Mitigation**
   ```bash
   # Increase cache timeout for slow queries
   export CACHE_TIMEOUT=7200  # 2 hours
   
   # Restart application
   sudo systemctl restart youtility3
   ```

6. **Root Cause Analysis**
   - Review slow query log
   - Check for missing indexes
   - Analyze query patterns

### ALERT: Database Query Slow (>100ms p95)

**Severity**: Warning
**Notification**: Email, Slack

**Steps:**
1. **Identify Slow Queries**
   ```bash
   # View current slow queries
   curl http://app-server:8000/monitoring/performance/queries/?min_time=100
   ```

2. **Analyze Query Plan**
   ```sql
   -- In PostgreSQL
   EXPLAIN ANALYZE 
   SELECT ... -- paste slow query here
   ```

3. **Quick Fixes**
   ```python
   # Add select_related/prefetch_related
   # Before
   tickets = Ticket.objects.filter(status='open')
   
   # After
   tickets = Ticket.objects.filter(
       status='open'
   ).select_related('user', 'department')
   ```

4. **Cache Slow Queries**
   ```python
   from apps.core.cache_manager import cache_decorator
   
   @cache_decorator(timeout=3600, key_prefix='slow_query')
   def get_complex_report():
       # Slow query here
       pass
   ```

5. **Create Missing Index**
   ```sql
   -- Check if index would help
   CREATE INDEX CONCURRENTLY idx_table_column 
   ON table_name(column_name) 
   WHERE active = true;
   ```

### ALERT: High Error Rate (>5%)

**Severity**: Critical
**Notification**: Email, Slack, PagerDuty

**Steps:**
1. **Check Error Logs**
   ```bash
   tail -f /var/log/youtility3/error.log
   grep ERROR /var/log/youtility3/application.log | tail -50
   ```

2. **Identify Error Pattern**
   ```python
   # Django shell
   from monitoring.django_monitoring import metrics_collector
   errors = metrics_collector.get_metrics('errors', minutes=10)
   # Group by error type
   ```

3. **Common Error Fixes**
   - **Database Connection**: Check connection pool
   - **ORM Errors**: Verify model fields match database
   - **Cache Errors**: Check Redis connection

4. **Rollback if Needed**
   ```bash
   # See Rollback Procedures section
   ./rollback_to_previous.sh
   ```

### ALERT: Low Cache Hit Rate (<50%)

**Severity**: Warning
**Notification**: Email, Slack

**Steps:**
1. **Check Cache Stats**
   ```python
   from django.core.cache import cache
   # Get cache statistics
   stats = cache._cache.get_stats()
   print(f"Hit Rate: {stats['hit_rate']}%")
   ```

2. **Identify Cache Misses**
   ```python
   from monitoring.views import get_cache_performance
   perf = get_cache_performance()
   for key_prefix in perf['miss_patterns']:
       print(f"{key_prefix}: {perf['miss_patterns'][key_prefix]} misses")
   ```

3. **Warm Cache**
   ```python
   from apps.core.cache_manager import TreeCache
   
   # Warm tree cache
   TreeCache.warm_cache()
   
   # Warm report cache
   from apps.core.queries import ReportQueryRepository
   ReportQueryRepository.warm_report_cache()
   ```

## Common Issues

### Issue 1: Sudden Performance Degradation

**Symptoms:**
- Response times increase across all endpoints
- Database CPU high
- No code changes

**Resolution:**
1. **Check Database Statistics**
   ```sql
   -- PostgreSQL
   ANALYZE;  -- Update statistics
   
   -- Check table bloat
   SELECT schemaname, tablename, 
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
   FROM pg_tables 
   WHERE schemaname = 'public' 
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

2. **Run Maintenance**
   ```sql
   VACUUM ANALYZE;  -- Clean up and update stats
   REINDEX DATABASE youtility3;  -- Rebuild indexes
   ```

### Issue 2: Memory Usage Growing

**Symptoms:**
- Application memory increases over time
- Eventually leads to OOM errors

**Resolution:**
1. **Check Metrics Retention**
   ```bash
   # Reduce metrics retention
   export METRICS_RETENTION_HOURS=6  # From 24 to 6
   ```

2. **Clear Old Metrics**
   ```python
   from monitoring.django_monitoring import metrics_collector
   metrics_collector.cleanup_old_metrics(hours=6)
   ```

3. **Restart Application**
   ```bash
   sudo systemctl restart youtility3
   ```

### Issue 3: Cache Invalidation Not Working

**Symptoms:**
- Stale data shown to users
- Updates not reflected

**Resolution:**
1. **Manual Cache Clear**
   ```python
   from django.core.cache import cache
   
   # Clear all cache
   cache.clear()
   
   # Clear specific pattern
   cache.delete_pattern('tree:*')
   ```

2. **Verify Cache Backend**
   ```python
   from django.conf import settings
   print(settings.CACHES)
   
   # Test cache
   cache.set('test_key', 'test_value', 30)
   print(cache.get('test_key'))
   ```

## Performance Troubleshooting

### Step 1: Identify Bottleneck

```python
# Performance profiling script
from monitoring.views import get_performance_summary
import json

summary = get_performance_summary()
print(json.dumps(summary, indent=2))

# Focus on:
# - Slowest endpoints
# - Highest query count
# - Lowest cache hit rate
```

### Step 2: Database Analysis

```sql
-- Find missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 100
  AND correlation < 0.1
ORDER BY n_distinct DESC;

-- Check query performance
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### Step 3: ORM Optimization

```python
# Debug toolbar for query analysis
from django.db import connection

# Enable query logging
connection.force_debug_cursor = True

# Run suspicious code
result = YourView.as_view()(request)

# Check queries
for query in connection.queries:
    print(f"{query['time']}ms: {query['sql'][:100]}")
```

## Emergency Procedures

### Database Overload

**Immediate Actions:**
1. **Enable Read-Only Mode**
   ```python
   # settings.py
   MAINTENANCE_MODE = True
   ```

2. **Kill Long Queries**
   ```sql
   -- PostgreSQL
   SELECT pg_cancel_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'active'
     AND query_start < NOW() - INTERVAL '5 minutes';
   ```

3. **Scale Database**
   ```bash
   # Add read replica
   # Update DATABASE_ROUTERS in settings
   ```

### Application Crash Loop

**Steps:**
1. **Check Logs**
   ```bash
   journalctl -u youtility3 -n 100
   ```

2. **Start in Safe Mode**
   ```bash
   # Disable monitoring temporarily
   export MONITOR_QUERIES=false
   python manage.py runserver --nothreading
   ```

3. **Debug Issue**
   ```python
   # Test imports
   python manage.py shell
   from apps.core.queries import QueryRepository
   ```

## Rollback Procedures

### Code Rollback

```bash
#!/bin/bash
# rollback_to_previous.sh

# Get previous deployment tag
PREVIOUS_TAG=$(git describe --tags --abbrev=0 HEAD^)

echo "Rolling back to $PREVIOUS_TAG"

# Checkout previous version
git checkout $PREVIOUS_TAG

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Clear cache
python manage.py shell -c "from django.core.cache import cache; cache.clear()"

# Restart services
sudo systemctl restart youtility3
sudo systemctl restart nginx
```

### Database Rollback

```sql
-- If ORM changes caused issues
-- Restore from backup
pg_restore -h localhost -U postgres -d youtility3 /backups/youtility3_backup.sql

-- Or revert specific migration
python manage.py migrate app_name previous_migration_number
```

## Monitoring Procedures

### Daily Checks

```bash
#!/bin/bash
# daily_health_check.sh

echo "=== Daily Health Check ==="
echo "Date: $(date)"

# Check system health
curl -s http://localhost:8000/monitoring/health/ | jq .

# Performance summary
curl -s http://localhost:8000/monitoring/dashboard/ | jq .

# Active alerts
curl -s http://localhost:8000/monitoring/alerts/ | jq .

# Slow queries
curl -s http://localhost:8000/monitoring/performance/queries/?min_time=200 | jq .
```

### Weekly Analysis

```python
# weekly_performance_report.py
from datetime import datetime, timedelta
from monitoring.views import get_performance_trends

# Get week's data
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

trends = get_performance_trends(start_date, end_date)

print(f"Weekly Performance Report ({start_date} to {end_date})")
print(f"Average Response Time: {trends['avg_response_time']}ms")
print(f"Query Performance: {trends['avg_query_time']}ms")
print(f"Cache Hit Rate: {trends['cache_hit_rate']}%")
print(f"Error Rate: {trends['error_rate']}%")

# Identify degradation
if trends['response_time_trend'] > 0.1:
    print("WARNING: Response time increasing")
```

## Maintenance Tasks

### Daily Maintenance

```bash
# Cron: 0 2 * * *
#!/bin/bash

# Update database statistics
psql -U postgres -d youtility3 -c "ANALYZE;"

# Clean old logs
find /var/log/youtility3 -name "*.log" -mtime +7 -delete

# Check disk space
df -h | grep -E "/$|/var"
```

### Weekly Maintenance

```bash
# Cron: 0 3 * * 0
#!/bin/bash

# Full vacuum (during maintenance window)
psql -U postgres -d youtility3 -c "VACUUM FULL ANALYZE;"

# Reindex if needed
psql -U postgres -d youtility3 -c "REINDEX DATABASE youtility3;"

# Backup database
pg_dump -U postgres youtility3 > /backups/youtility3_$(date +%Y%m%d).sql

# Archive old metrics
python manage.py archive_metrics --days 30
```

### Monthly Maintenance

```bash
# Review and update indexes
python scripts/analyze_index_usage.py

# Performance baseline update
python scripts/update_performance_baseline.py

# Capacity planning review
python scripts/capacity_report.py
```

## Contact Information

### Escalation Path
1. **L1 Support**: monitoring-alerts@youtility.com
2. **L2 Engineering**: dev-oncall@youtility.com
3. **L3 Architecture**: arch-team@youtility.com

### External Support
- **Database**: dba-team@youtility.com
- **Infrastructure**: infra@youtility.com
- **Security**: security@youtility.com

### Documentation
- [Django ORM Migration Guide](./DJANGO_ORM_MIGRATION_GUIDE.md)
- [Monitoring Setup Guide](./MONITORING_SETUP_GUIDE.md)
- [Developer Training](./DEVELOPER_TRAINING.md)

---

Remember: Always announce maintenance in #ops channel and update status page before performing any production changes.