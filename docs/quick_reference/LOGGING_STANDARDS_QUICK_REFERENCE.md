# Logging Standards Quick Reference

**Last Updated**: November 6, 2025  
**Status**: Enforced via pre-commit hooks and Flake8

---

## ⛔ FORBIDDEN

```python
# ❌ NEVER use print() in production code
print("Debug info")
print(f"User: {user.loginid}")
```

**Violation**: Flake8 T001/T002 errors, pre-commit hook rejection

---

## ✅ REQUIRED PATTERN

### Basic Setup

```python
import logging
logger = logging.getLogger(__name__)
```

### Log Levels

```python
# 🔍 DEBUG - Development/troubleshooting only
logger.debug(f"Query count: {len(queries)}")
logger.debug(f"Processing {user.loginid}")

# ℹ️ INFO - Important operations
logger.info(f"User created: {user.loginid}")
logger.info(f"Migration completed: {count} records updated")

# ⚠️ WARNING - Unexpected but handled
logger.warning(f"Rate limit approaching for {user.loginid}")
logger.warning("Geofence check failed, allowing attendance")

# ❌ ERROR - Errors that need attention
logger.error(f"Database error: {e}")
logger.error("Payment processing failed", exc_info=True)

# 🚨 CRITICAL - System-level failures
logger.critical("Database connection lost")
```

---

## Common Patterns

### Exception Logging

```python
# ✅ CORRECT: Include stack trace
try:
    user.save()
except IntegrityError as e:
    logger.error(f"Failed to save user {user.loginid}", exc_info=True)
    raise

# ❌ WRONG: No context
except Exception as e:
    logger.error(str(e))
```

### Performance Logging

```python
import time

start = time.time()
# ... operation ...
elapsed = time.time() - start

logger.info(f"Query completed in {elapsed:.2f}s", extra={
    'operation': 'user_list',
    'duration_ms': elapsed * 1000,
    'record_count': count
})
```

### Structured Logging (Production)

```python
# ✅ BEST: Structured data for log aggregation
logger.info("User login", extra={
    'user_id': user.id,
    'login_id': user.loginid,
    'tenant': request.tenant.tenant_slug,
    'ip_address': request.META['REMOTE_ADDR']
})
```

---

## Migration Files

```python
import logging
logger = logging.getLogger(__name__)

def forwards(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    count = Model.objects.filter(...).update(...)
    logger.info(f"Updated {count} records")
```

---

## Management Commands

```python
from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Use self.stdout for user-visible output
        self.stdout.write(self.style.SUCCESS('Operation started'))
        
        # Use logger for debugging
        logger.debug(f"Processing {count} items")
        
        # Use logger for errors
        logger.error(f"Failed: {error}")
```

---

## Test Files (Exception)

Test files MAY use `print()` for test debugging:

```python
# ✅ ALLOWED in test files
def test_performance():
    print(f"\n✅ Query count: {query_count}")
    print(f"   Performance: {elapsed:.2f}ms")
```

---

## Configuration

### Development (`settings/development.py`)

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Production (`settings/production.py`)

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/intelliwiz/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'json',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/intelliwiz/errors.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
        },
        # Reduce middleware noise
        'apps.core.middleware': {
            'level': 'WARNING',
        },
    },
}
```

---

## Pre-Commit Hook

In `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/pre-commit/pygrep-hooks
  rev: v1.10.0
  hooks:
    - id: python-check-print
      name: Check for print statements
      exclude: |
        (?x)^(
          .*tests/.*|
          .*migrations/.*|
          .*examples/.*|
          scripts/.*
        )$
```

---

## Flake8 Enforcement

In `.flake8`:

```ini
[flake8]
# T001: Print statement found
# T002: Print function with sep argument
select = ...,T001,T002

exclude = 
    migrations,
    tests,
    examples,
    scripts
```

---

## Common Mistakes

### ❌ WRONG: Print in production

```python
def create_user(request):
    user = User.objects.create(...)
    print(f"Created user: {user.loginid}")  # Flake8 violation
    return Response(...)
```

### ✅ CORRECT: Logger

```python
import logging
logger = logging.getLogger(__name__)

def create_user(request):
    user = User.objects.create(...)
    logger.info(f"User created", extra={
        'user_id': user.id,
        'login_id': user.loginid,
        'tenant': request.tenant.tenant_slug
    })
    return Response(...)
```

### ❌ WRONG: Generic exception

```python
try:
    process()
except Exception as e:
    logger.error(str(e))  # No stack trace, no context
```

### ✅ CORRECT: Specific exception with context

```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

try:
    process()
except DATABASE_EXCEPTIONS as e:
    logger.error(
        f"Database operation failed for user {user.loginid}",
        exc_info=True,
        extra={'user_id': user.id, 'operation': 'update'}
    )
    raise
```

---

## Log Level Decision Tree

```
Is this for debugging/development only?
├─ YES → logger.debug()
└─ NO → Is this an error/exception?
    ├─ YES → Is it recoverable?
    │   ├─ YES → logger.warning() with context
    │   └─ NO → logger.error() with exc_info=True
    └─ NO → Is it important for operations?
        ├─ YES → logger.info()
        └─ NO → logger.debug()
```

---

## Integration Examples

### Sentry (Error Tracking)

```python
# settings/production.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(),
        LoggingIntegration(
            level=logging.INFO,        # Capture info and above
            event_level=logging.ERROR  # Send errors to Sentry
        ),
    ],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
)
```

### CloudWatch Logs (AWS)

```python
# requirements/production.txt
boto3==1.34.0
watchtower==3.0.1

# settings/production.py
import boto3
import watchtower

LOGGING = {
    'handlers': {
        'cloudwatch': {
            'class': 'watchtower.CloudWatchLogHandler',
            'boto3_client': boto3.client('logs', region_name='us-east-1'),
            'log_group_name': '/intelliwiz/production',
            'stream_name': '{machine_name}/{logger_name}',
        },
    },
    'loggers': {
        'apps': {
            'handlers': ['cloudwatch'],
            'level': 'INFO',
        },
    },
}
```

---

## Verification Commands

```bash
# Check for remaining print statements in production code
find apps -name "*.py" -type f \
  ! -path "*/migrations/*" \
  ! -path "*/tests/*" \
  ! -path "*/examples/*" \
  -exec grep -l "^\s*print(" {} \;

# Run Flake8 check
flake8 apps/ --select=T001,T002

# Run pre-commit hooks
pre-commit run python-check-print --all-files
```

---

## References

- **Django Logging Docs**: https://docs.djangoproject.com/en/5.2/topics/logging/
- **Python Logging HOWTO**: https://docs.python.org/3/howto/logging.html
- **Structured Logging**: https://www.structlog.org/
- **Complete Report**: `PRINT_STATEMENT_REMEDIATION_COMPLETE.md`

---

**Enforcement**: Pre-commit hooks + Flake8 + Code review  
**Exceptions**: Tests, migrations, management commands (with justification)
