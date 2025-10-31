# Common Issues & Troubleshooting

> **Solutions to frequently encountered problems**

---

## Pre-Commit Hooks Failing

### Problem
Git commit is blocked by pre-commit hook validation.

### Solution

1. Review specific rule violation in error message
2. Check `.claude/rules.md` for correct pattern
3. Fix violation before attempting commit
4. Contact team lead if rule clarification needed

### Example

```bash
# Error message
[ERROR] Bare except block found in apps/core/utils.py:42

# Fix
# Before (❌)
try:
    operation()
except:
    pass

# After (✅)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
try:
    operation()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Error: {e}", exc_info=True)
    raise
```

---

## CI/CD Pipeline Failing

### Problem
Pull request checks failing in CI/CD pipeline.

### Solution

1. Check quality report in PR comments
2. Fix all identified violations locally
3. Re-run tests to ensure compliance: `python -m pytest`
4. Request code review only after all checks pass

### Common Causes

- Flake8 violations (E722, T001, C901)
- Test failures
- Code smell detection issues
- Missing documentation

---

## Idempotency Issues

### Duplicate Tasks Still Running

**Check current state:**

```bash
# Analyze tasks
python scripts/migrate_to_idempotent_tasks.py --analyze

# Check schedule conflicts
python manage.py validate_schedules --check-duplicates
```

### Check Idempotency Logs

Visit dashboard: `/admin/tasks/idempotency-analysis`

### Redis Connectivity Issues

Framework automatically falls back to PostgreSQL with <7ms latency. Check logs for fallback warnings.

---

## Orphaned Celery Beat Tasks

### Problem
Beat schedule references tasks that don't exist → silent failures.

### Detection

```bash
# Check beat schedule → task registration mapping
python manage.py validate_schedules --check-orphaned-tasks --verbose

# Full task inventory (duplicates + orphaned)
python scripts/audit_celery_tasks.py --generate-report
```

### Prevention

Pre-commit hook automatically blocks commits with orphaned tasks:

```bash
# Located at: .githooks/pre-commit-celery-beat-validation
```

---

## Flake8 Validation Failures

### Print Statement Detected (T001)

**Problem:**
```python
print("Debug output")  # ❌ T001: print found
```

**Solution:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Debug output")  # ✅ Use logger
```

**Exception (CLI scripts only):**
```python
print("Output")  # noqa: T001
```

### Bare Except Detected (E722)

**Problem:**
```python
try:
    operation()
except:  # ❌ E722: bare except
    pass
```

**Solution:**
```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
try:
    operation()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise
```

### Cyclomatic Complexity (C901)

**Problem:**
Function/method too complex (>10 complexity).

**Solution:**
Break into smaller functions:

```python
# Before (❌)
def complex_function(data):
    if condition1:
        if condition2:
            if condition3:
                # ... nested logic
                pass

# After (✅)
def complex_function(data):
    if not validate_data(data):
        return None
    return process_validated_data(data)

def validate_data(data):
    return condition1 and condition2 and condition3

def process_validated_data(data):
    # Simple logic
    pass
```

---

## Database Migration Issues

### Migration Conflicts

```bash
# Identify conflicts
python manage.py showmigrations

# Resolve conflicts
python manage.py makemigrations --merge
```

### Rollback Migration

```bash
# Rollback to specific migration
python manage.py migrate app_name 0004_previous_migration

# Rollback all migrations for app
python manage.py migrate app_name zero
```

### Fake Migration (Development Only)

```bash
# Mark migration as applied without running
python manage.py migrate --fake app_name 0005_migration_name
```

---

## Redis Connection Issues

### Connection Refused

**Cause:** Redis server not running

**Solution:**
```bash
# Check Redis status
redis-cli ping  # Should return PONG

# Start Redis (macOS)
brew services start redis

# Start Redis (Linux)
sudo systemctl start redis
```

### Authentication Failed

**Cause:** Missing or incorrect `REDIS_PASSWORD`

**Solution:**
```bash
# Set in environment
export REDIS_PASSWORD=your_secure_password

# Or in .env file
REDIS_PASSWORD=your_secure_password
```

### Verify Configuration

```bash
python scripts/verify_redis_cache_config.py
```

---

## Celery Worker Issues

### Workers Not Starting

```bash
# Check worker status
./scripts/celery_workers.sh status

# View logs
tail -f logs/celery_worker.log

# Restart workers
./scripts/celery_workers.sh restart
```

### Tasks Not Being Processed

**Check queue depth:**
```bash
celery -A intelliwiz_config inspect active
celery -A intelliwiz_config inspect reserved
```

**Purge queue (development only):**
```bash
celery -A intelliwiz_config purge
```

### Memory Issues

**Restart workers periodically:**
```bash
# Add to cron
0 */6 * * * /path/to/scripts/celery_workers.sh restart
```

---

## Test Failures

### Database Locked Error

**Cause:** SQLite concurrent access (testing)

**Solution:**
Use PostgreSQL for tests:

```python
# pytest.ini or conftest.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_db',
    }
}
```

### Fixtures Not Loading

```bash
# Load fixtures explicitly
python manage.py loaddata fixture_name

# Check fixture path
python manage.py loaddata --list
```

### Flaky Tests

Use idempotency and proper cleanup:

```python
@pytest.fixture(autouse=True)
def cleanup_after_test():
    yield
    # Cleanup code here
    Model.objects.all().delete()
```

---

## Performance Issues

### Slow Queries

**Enable query logging:**
```python
# settings.py
LOGGING['loggers']['django.db.backends'] = {
    'level': 'DEBUG',
    'handlers': ['console'],
}
```

**Analyze queries:**
```bash
# Django Debug Toolbar (development)
pip install django-debug-toolbar

# Or use django-extensions
python manage.py show_urls | grep slow_endpoint
```

**Optimize with select_related/prefetch_related:**
```python
# Before (❌ N+1 queries)
users = People.objects.all()
for user in users:
    print(user.profile.gender)  # Additional query per user

# After (✅ 2 queries)
users = People.objects.select_related('profile').all()
for user in users:
    print(user.profile.gender)
```

### High Memory Usage

**Check Celery workers:**
```bash
# Monitor memory
./scripts/celery_workers.sh monitor

# Reduce concurrency
# In celery settings
CELERYD_CONCURRENCY = 4  # Lower if needed
```

---

## WebSocket Connection Issues

### Connection Refused

**Cause:** ASGI server not running

**Solution:**
```bash
# Start ASGI server
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

### Authentication Failed

**Cause:** Missing JWT token in WebSocket connection

**Solution:**
```javascript
// Pass token in query string
const ws = new WebSocket(
    `ws://localhost:8000/ws/sync/?token=${authToken}`
);
```

---

## Import Errors

### Module Not Found

```bash
# Verify virtual environment
which python  # Should be in venv

# Reinstall requirements
pip install -r requirements/base-macos.txt
```

### Circular Import

**Symptom:** `ImportError: cannot import name 'X' from partially initialized module`

**Solution:**
- Move imports inside functions
- Use `from __future__ import annotations`
- Restructure dependencies

---

## Static Files Not Loading

### Development

```bash
# Ensure runserver is serving static files
python manage.py runserver
# Static files served automatically
```

### Production

```bash
# Collect static files
python manage.py collectstatic --no-input

# Verify STATIC_ROOT
ls -la staticfiles/
```

---

## Getting Help

### Check Logs

```bash
# Application logs
tail -f logs/intelliwiz.log

# Error logs
tail -f logs/errors.log

# Celery logs
tail -f logs/celery_worker.log
```

### Run Health Checks

```bash
# Django checks
python manage.py check

# Schedule validation
python manage.py validate_schedules --verbose

# Code quality
python scripts/validate_code_quality.py --verbose
```

### Contact Support

- **Security issues**: Contact security team immediately
- **Architecture questions**: Review documentation first
- **Quality violations**: Run validation tools before asking
- **Bug reports**: Include logs and reproduction steps

---

**Last Updated**: October 29, 2025
**Maintainer**: Support Team
**Related**: [Testing Guide](../testing/TESTING_AND_QUALITY_GUIDE.md), [Configuration](../configuration/SETTINGS_AND_CONFIG.md)
