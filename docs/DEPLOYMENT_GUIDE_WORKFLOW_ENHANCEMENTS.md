# Deployment Guide: Workflow Enhancements

**Version:** 1.0
**Release Date:** October 2025
**Target Django Version:** 5.2.1+

## Overview

This guide covers the deployment of the Workflow Enhancements release, which includes:

- ✅ **Search Enhancements** - Rate limiting, caching, typo tolerance
- ✅ **Optimistic Locking** - Concurrency control with django-concurrency
- ✅ **State Machines** - Unified state transition framework
- ✅ **Audit Logging** - Comprehensive audit trail with PII redaction
- ✅ **Bulk Operations** - Efficient multi-entity operations
- ✅ **Automatic Audit Signals** - Signal-based audit logging

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Dependency Installation](#dependency-installation)
3. [Database Migrations](#database-migrations)
4. [Redis Configuration](#redis-configuration)
5. [PostgreSQL Extensions](#postgresql-extensions)
6. [Configuration Updates](#configuration-updates)
7. [Testing Deployment](#testing-deployment)
8. [Rollback Procedures](#rollback-procedures)
9. [Monitoring & Alerts](#monitoring--alerts)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

| Component | Minimum Version | Recommended |
|-----------|----------------|-------------|
| Python | 3.10 | 3.12+ |
| Django | 5.2.1 | 5.2.1 |
| PostgreSQL | 14.2 | 15.0+ |
| Redis | 6.0 | 7.0+ |
| PostGIS | 3.1 | 3.4+ |

### Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `django-concurrency` | 2.5+ | Optimistic locking |
| `redis` | 4.5+ | Rate limiting & caching |
| `pg_trgm` (PostgreSQL) | Built-in | Trigram search |
| `freezegun` | 1.2+ | Testing (dev only) |

### Pre-Deployment Checklist

- [ ] Database backup completed
- [ ] Redis instance available and accessible
- [ ] PostgreSQL extensions installable (superuser access)
- [ ] Staging environment tested successfully
- [ ] Rollback plan documented
- [ ] Team notified of deployment window
- [ ] Monitoring dashboards prepared

---

## Dependency Installation

### 1. Update requirements.txt

Add the following to `requirements/base.txt`:

```txt
# Workflow Enhancements - October 2025
django-concurrency>=2.5,<3.0  # Optimistic locking
redis>=4.5,<5.0               # Rate limiting & caching
hiredis>=2.0,<3.0            # Redis performance optimization
```

Add to `requirements/test.txt`:

```txt
# Testing utilities
freezegun>=1.2,<2.0          # Time-based testing
pytest-django>=4.5,<5.0      # Django test integration
pytest-xdist>=3.0,<4.0       # Parallel test execution
```

### 2. Install Dependencies

```bash
# Production
pip install -r requirements/base.txt

# Development/Testing
pip install -r requirements/test.txt
```

### 3. Verify Installation

```bash
python -c "import concurrency; print(f'django-concurrency: {concurrency.__version__}')"
python -c "import redis; print(f'redis-py: {redis.__version__}')"
```

---

## Database Migrations

### Migration Order

The following migrations must be applied in order:

1. **Version Fields** (all apps)
2. **Audit Models** (core app)
3. **Search Indexes** (PostgreSQL extensions)

### 1. Review Migrations

```bash
# Check pending migrations
python manage.py showmigrations

# Expected output:
# work_order_management
#   [ ] 0001_add_version_fields
# activity
#   [ ] 0001_add_version_fields
# attendance
#   [ ] 0001_add_version_fields
# y_helpdesk
#   [ ] 0001_add_version_fields
# core
#   [ ] 0001_add_audit_models
```

### 2. Test Migrations in Development

```bash
# Dry-run migrations (check for issues)
python manage.py migrate --plan

# Apply migrations to dev database
python manage.py migrate

# Verify no errors
python manage.py check
```

### 3. Apply Migrations in Staging

```bash
# Staging environment
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.staging python manage.py migrate

# Verify migration status
python manage.py showmigrations | grep '\[X\]'
```

### 4. Apply Migrations in Production

**⚠️ CRITICAL: Take database backup first!**

```bash
# Backup database
pg_dump -U postgres -d intelliwiz_prod -F c -f backup_pre_workflow_enhancements.dump

# Apply migrations
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.production python manage.py migrate

# Verify
python manage.py showmigrations --check
```

### Expected Migration Time

| Database Size | Estimated Time |
|--------------|----------------|
| < 1 GB | 30 seconds |
| 1-10 GB | 2-5 minutes |
| 10-100 GB | 10-30 minutes |
| > 100 GB | 1+ hours |

---

## Redis Configuration

### 1. Redis Instance Setup

**Option A: Local Redis (Development)**

```bash
# Install Redis
brew install redis  # macOS
sudo apt install redis-server  # Ubuntu

# Start Redis
redis-server

# Verify
redis-cli ping  # Should return PONG
```

**Option B: Redis Cloud (Production)**

Configure connection in `.env.production`:

```env
REDIS_HOST=your-redis-instance.cloud.redislabs.com
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-password
REDIS_DB=0
REDIS_SSL=True
```

### 2. Django Settings Configuration

Update `intelliwiz_config/settings/base.py`:

```python
# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_SSL = os.getenv('REDIS_SSL', 'False').lower() == 'true'

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"{'rediss' if REDIS_SSL else 'redis'}://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PASSWORD': REDIS_PASSWORD,
            'PARSER_CLASS': 'redis.connection.HiredisParser',  # Performance optimization
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        },
        'KEY_PREFIX': 'intelliwiz',
        'TIMEOUT': 300,  # 5 minutes default
    }
}
```

### 3. Test Redis Connection

```bash
python manage.py shell

>>> from django.core.cache import cache
>>> cache.set('test', 'hello')
>>> cache.get('test')
'hello'
>>> cache.delete('test')
```

### 4. Redis Persistence Configuration

For production, ensure Redis persistence is enabled:

```conf
# /etc/redis/redis.conf

# RDB persistence (snapshot)
save 900 1      # Save if 1 key changed in 15 min
save 300 10     # Save if 10 keys changed in 5 min
save 60 10000   # Save if 10k keys changed in 1 min

# AOF persistence (append-only file)
appendonly yes
appendfsync everysec
```

---

## PostgreSQL Extensions

### 1. Enable pg_trgm Extension

```sql
-- Connect to database
psql -U postgres -d intelliwiz_prod

-- Enable extension (requires superuser)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify
\dx pg_trgm

-- Expected output:
--  Name   | Version |   Schema   |          Description
-- --------+---------+------------+-------------------------------
--  pg_trgm | 1.6     | public     | text similarity measurement
```

### 2. Create Trigram Indexes (Optional - for better performance)

These are created automatically by migrations, but can be created manually if needed:

```sql
-- For Asset search
CREATE INDEX IF NOT EXISTS idx_asset_name_trgm ON activity_asset USING GIN (name gin_trgm_ops);

-- For Job search
CREATE INDEX IF NOT EXISTS idx_job_description_trgm ON activity_job USING GIN (description gin_trgm_ops);

-- For Ticket search
CREATE INDEX IF NOT EXISTS idx_ticket_subject_trgm ON y_helpdesk_ticket USING GIN (subject gin_trgm_ops);
```

### 3. Verify Index Creation

```sql
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE indexname LIKE '%trgm%'
ORDER BY tablename, indexname;
```

---

## Configuration Updates

### 1. Middleware Configuration

Update `MIDDLEWARE` in `intelliwiz_config/settings/base.py`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Security middleware
    'apps.core.middleware.sql_injection_protection.SQLInjectionProtectionMiddleware',
    'apps.core.middleware.xss_protection.XSSProtectionMiddleware',
    'apps.core.middleware.correlation_id.CorrelationIDMiddleware',

    # NEW: Concurrency middleware
    'apps.core.middleware.concurrency_middleware.ConcurrencyMiddleware',

    # NEW: Search rate limiting
    'apps.search.middleware.rate_limiting.SearchRateLimitMiddleware',
]
```

### 2. URL Configuration

Add bulk operation URLs to `intelliwiz_config/urls_optimized.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...

    # NEW: Bulk Operations
    path('api/v1/work-orders/bulk/', include('apps.work_order_management.urls.bulk')),
    path('api/v1/tasks/bulk/', include('apps.activity.urls.bulk')),
    path('api/v1/attendance/bulk/', include('apps.attendance.urls.bulk')),
    path('api/v1/tickets/bulk/', include('apps.y_helpdesk.urls.bulk')),
]
```

### 3. Logging Configuration

Add audit logging configuration:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'audit': {
            'format': '[{asctime}] AUDIT {correlation_id} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/audit.log',
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 90,     # 90 days retention
            'formatter': 'audit',
        },
    },
    'loggers': {
        'apps.core.signals.audit_signals': {
            'handlers': ['audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.core.services.unified_audit_service': {
            'handlers': ['audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

---

## Testing Deployment

### 1. Run Test Suite

```bash
# Run all workflow enhancement tests
python -m pytest apps/core/tests/test_state_machines_comprehensive.py -v
python -m pytest apps/core/tests/test_bulk_operations_comprehensive.py -v
python -m pytest apps/core/tests/test_audit_logging_comprehensive.py -v
python -m pytest apps/search/tests/test_rate_limiting.py -v
python -m pytest apps/search/tests/test_caching.py -v
python -m pytest apps/search/tests/test_sanitization.py -v

# Run full test suite
python -m pytest --cov=apps --cov-report=html -v
```

### 2. Manual Testing Checklist

- [ ] **Bulk Approve** - Approve 10 work orders via API
- [ ] **Bulk Reject** - Reject 5 tasks with required comments
- [ ] **State Transitions** - Test all valid state machine transitions
- [ ] **Concurrency** - Simulate concurrent edits (should get 409 Conflict)
- [ ] **Audit Trail** - Verify audit logs created with PII redaction
- [ ] **Rate Limiting** - Exceed rate limit (should get 429 Too Many Requests)
- [ ] **Search** - Test fuzzy search with typos
- [ ] **Cache** - Verify search results cached (check Redis)

### 3. Performance Benchmarks

```bash
# Run performance tests
python -m pytest apps/core/tests/test_bulk_operations_comprehensive.py::BulkOperationsIntegrationTest::test_bulk_operation_performance -v

# Expected benchmarks:
# - 100 bulk transitions: < 5 seconds
# - 1000 search results: < 100ms (cached)
# - State validation: < 10ms per entity
```

---

## Rollback Procedures

### Emergency Rollback Steps

**If critical issues are discovered after deployment:**

1. **Stop Application**
   ```bash
   # Stop application servers
   sudo systemctl stop gunicorn
   sudo systemctl stop celery
   ```

2. **Restore Database Backup**
   ```bash
   # Drop current database (⚠️ CRITICAL - ensure backup exists)
   dropdb intelliwiz_prod

   # Restore from backup
   pg_restore -U postgres -d intelliwiz_prod -v backup_pre_workflow_enhancements.dump
   ```

3. **Revert Code Changes**
   ```bash
   # Checkout previous stable tag
   git checkout v1.9.0  # Replace with your previous version
   ```

4. **Restart Application**
   ```bash
   # Restart with previous version
   sudo systemctl start gunicorn
   sudo systemctl start celery
   ```

5. **Verify Rollback**
   ```bash
   # Check migration status (should show rolled back)
   python manage.py showmigrations

   # Smoke test critical endpoints
   curl https://api.example.com/health
   ```

### Partial Rollback (Disable Features)

If only specific features are problematic:

```python
# In settings/production.py

# Disable audit signals
ENABLE_AUDIT_SIGNALS = False

# Disable bulk operations
ENABLE_BULK_OPERATIONS = False

# Disable search rate limiting
ENABLE_SEARCH_RATE_LIMITING = False
```

---

## Monitoring & Alerts

### Key Metrics to Monitor

| Metric | Threshold | Alert Level |
|--------|-----------|-------------|
| Bulk operation success rate | < 95% | Warning |
| State transition failures | > 100/hour | Warning |
| Concurrency conflicts (409) | > 50/hour | Info |
| Rate limit hits (429) | > 1000/hour | Warning |
| Audit log write failures | > 10/hour | Critical |
| Redis connection errors | > 5/minute | Critical |
| Search response time | > 500ms | Warning |

### Grafana Dashboard Queries

```promql
# Bulk operation success rate
rate(bulk_operation_success_total[5m]) / rate(bulk_operation_total[5m])

# State transition errors
rate(state_transition_error_total[5m])

# Redis cache hit rate
rate(redis_cache_hits[5m]) / rate(redis_cache_requests[5m])

# Audit log write rate
rate(audit_log_writes[5m])
```

### Logging Queries

```bash
# Check audit log volume
tail -f logs/audit.log | grep -c "AUDIT"

# Monitor bulk operations
tail -f logs/django.log | grep "bulk_operation"

# Track concurrency conflicts
tail -f logs/django.log | grep "RecordModifiedError"

# Check rate limit hits
tail -f logs/access.log | grep "429"
```

---

## Troubleshooting

### Common Issues

#### 1. Migration Fails: "relation already exists"

**Cause:** Migration previously partially applied

**Solution:**
```bash
# Mark migration as applied without running
python manage.py migrate --fake work_order_management 0001_add_version_fields

# Or drop and recreate table (⚠️ only in development)
```

#### 2. Redis Connection Refused

**Cause:** Redis not running or wrong configuration

**Solution:**
```bash
# Check Redis status
redis-cli ping

# Check configuration
python manage.py shell
>>> from django.conf import settings
>>> print(settings.CACHES['default']['LOCATION'])

# Verify network connectivity
telnet $REDIS_HOST $REDIS_PORT
```

#### 3. Concurrency Errors on Every Edit

**Cause:** Version field not initialized

**Solution:**
```sql
-- Reset all version fields to 0
UPDATE work_order_management_wom SET version = 0 WHERE version IS NULL;
UPDATE activity_job SET version = 0 WHERE version IS NULL;
-- Repeat for all tables
```

#### 4. Audit Logs Not Being Created

**Cause:** Signals not registered

**Solution:**
```bash
# Check if signals are registered
python manage.py shell

>>> from apps.core.signals import audit_signals
>>> # If ImportError, signals module has issues

# Check logs for signal registration
grep "Audit logging signals registered" logs/django.log
```

#### 5. Bulk Operations Timeout

**Cause:** Too many items in single request

**Solution:**
- Reduce batch size from 1000 to 100-500
- Increase timeout settings:
  ```python
  # settings/production.py
  GUNICORN_TIMEOUT = 120  # 2 minutes
  ```

---

## Post-Deployment Verification

### Checklist

- [ ] All migrations applied successfully
- [ ] Redis cache working (check with test key)
- [ ] Audit logs being created
- [ ] Bulk operations functional (test with 10 items)
- [ ] State machines enforcing transitions
- [ ] Rate limiting active (test with 25 rapid requests)
- [ ] Search returning results with typo tolerance
- [ ] Concurrency conflicts handled gracefully
- [ ] No errors in application logs
- [ ] Monitoring dashboards updated

### Success Criteria

- ✅ **Zero downtime** during deployment
- ✅ **< 5% error rate** in first 24 hours
- ✅ **All tests passing** (unit, integration, performance)
- ✅ **Audit trail complete** for all operations
- ✅ **No data loss** or corruption
- ✅ **Performance maintained** (P95 latency < 500ms)

---

## Support

**Deployment Issues:** Contact DevOps team
**Database Issues:** Contact Database Administrator
**Application Errors:** Check application logs and audit trail

**Documentation:**
- [API Documentation](./API_BULK_OPERATIONS.md)
- [State Machine Guide](./STATE_MACHINE_DEVELOPER_GUIDE.md)
- [Audit Logging](./AUDIT_LOGGING_GUIDE.md)

**Last Updated:** October 2025
**Next Review:** January 2026
