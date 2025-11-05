# Constants Quick Reference - Phase 6

## Import Patterns

```python
# Option 1: Import specific constants (PREFERRED)
from apps.core.constants.timeouts import REQUEST_TIMEOUT_SHORT
from apps.core.constants.cache_ttl import HELPBOT_CACHE_TIMEOUT
from apps.core.constants.retry import MAX_RETRIES_STANDARD

# Option 2: Import from main constants package
from apps.core.constants import (
    REQUEST_TIMEOUT_SHORT,
    HELPBOT_CACHE_TIMEOUT,
    MAX_RETRIES_STANDARD
)

# Option 3: Direct module import (less common)
from apps.core.constants import timeouts, cache_ttl, retry
timeout_val = timeouts.REQUEST_TIMEOUT_SHORT
```

## Common Timeout Values

| Constant | Value | Use Case |
|----------|-------|----------|
| `REQUEST_TIMEOUT_SHORT` | (5, 15) | Quick API calls, metadata |
| `REQUEST_TIMEOUT_MEDIUM` | (5, 30) | File downloads, moderate operations |
| `REQUEST_TIMEOUT_LONG` | (5, 60) | Long operations, report generation |
| `CELERY_SOFT_TIMEOUT_SHORT` | 300s | 5 min task deadline |
| `CELERY_SOFT_TIMEOUT_MEDIUM` | 600s | 10 min task deadline |
| `CELERY_HARD_TIMEOUT_LONG` | 3600s | 1 hour hard limit |
| `TASK_EXPIRES_STANDARD` | 3600s | Task valid for 1 hour |
| `TASK_EXPIRES_LONG` | 7200s | Task valid for 2 hours |
| `WEBSOCKET_PRESENCE_TIMEOUT` | 300s | WebSocket presence heartbeat |

## Common Cache TTL Values

| Constant | Value | Use Case |
|----------|-------|----------|
| `CACHE_TTL_SHORT` | 300s | Volatile data (5 min) |
| `CACHE_TTL_MEDIUM` | 900s | Standard data (15 min) |
| `CACHE_TTL_DEFAULT` | 1800s | Default cache (30 min) |
| `CACHE_TTL_LONG` | 3600s | Stable data (1 hour) |
| `CACHE_TTL_DAILY` | 86400s | Daily cache (24 hours) |
| `HELPBOT_CACHE_TIMEOUT` | 3600s | HelpBot results |
| `REPORT_GENERATION_CACHE_TIMEOUT` | 3600s | Report results |
| `HOT_CACHE_TTL` | 300s | Frequently accessed |
| `WARM_CACHE_TTL` | 1800s | Moderately accessed |
| `COLD_CACHE_TTL` | 3600s | Rarely accessed |

## Common Retry Values

| Constant | Value | Use Case |
|----------|-------|----------|
| `MAX_RETRIES_SHORT` | 3 | Quick operations |
| `MAX_RETRIES_STANDARD` | 5 | Normal operations |
| `MAX_RETRIES_LONG` | 10 | Critical operations |
| `DATABASE_RETRY_COUNT` | 3 | Database contention |
| `NETWORK_RETRY_COUNT` | 5 | HTTP/API calls |
| `RETRY_BACKOFF_MULTIPLIER` | 2.0 | Exponential backoff |
| `RETRY_MAX_DELAY_SHORT` | 60s | 1 minute cap |
| `RETRY_MAX_DELAY_LONG` | 900s | 15 minute cap |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 5 | Failures before open |

## Real-World Examples

### HTTP Request with Timeout
```python
from apps.core.constants.timeouts import REQUEST_TIMEOUT_MEDIUM

response = requests.get(
    'https://api.example.com/data',
    timeout=REQUEST_TIMEOUT_MEDIUM  # (5, 30)
)
```

### Cache Set Operation
```python
from apps.core.constants.cache_ttl import REPORT_GENERATION_CACHE_TIMEOUT
from django.core.cache import cache

report_data = generate_report()
cache.set('report_key', report_data, timeout=REPORT_GENERATION_CACHE_TIMEOUT)
```

### Celery Task Definition
```python
from apps.core.constants.timeouts import (
    CELERY_SOFT_TIMEOUT_SHORT,
    CELERY_HARD_TIMEOUT_MEDIUM,
    TASK_EXPIRES_STANDARD
)
from celery import shared_task

@shared_task(
    soft_time_limit=CELERY_SOFT_TIMEOUT_SHORT,
    time_limit=CELERY_HARD_TIMEOUT_MEDIUM,
    expires=TASK_EXPIRES_STANDARD
)
def my_task():
    pass
```

### Idempotency Configuration
```python
from apps.core.constants.cache_ttl import IDEMPOTENCY_TTL_STANDARD

# Register idempotency key with TTL
idempotency_service.register(
    key=idempotency_key,
    ttl=IDEMPOTENCY_TTL_STANDARD  # 2 hours
)
```

### Rate Limiting Window
```python
from apps.core.constants.cache_ttl import RATE_LIMIT_WINDOW_SHORT
from apps.core.decorators import rate_limit

@rate_limit(
    max_requests=10,
    window_seconds=RATE_LIMIT_WINDOW_SHORT  # 5 minutes
)
def create_report(request):
    pass
```

### Retry Policy
```python
from apps.core.constants.retry import DATABASE_OPERATION_RETRY
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(
    exceptions=(IntegrityError, OperationalError),
    retry_policy=DATABASE_OPERATION_RETRY
)
def save_critical_data(user):
    user.save()
```

## Finding the Right Constant

### Is it a network timeout?
→ Use `apps/core/constants/timeouts.py`
- `REQUEST_TIMEOUT_*` for HTTP calls
- `WEBSOCKET_*_TIMEOUT` for WebSocket operations
- `DATABASE_TIMEOUT` for DB connections

### Is it a cache expiration?
→ Use `apps/core/constants/cache_ttl.py`
- `CACHE_TTL_*` for general caching
- Application-specific: `HELPBOT_CACHE_TIMEOUT`, `REPORT_GENERATION_CACHE_TIMEOUT`
- `IDEMPOTENCY_TTL_*` for idempotency keys
- `RATE_LIMIT_WINDOW_*` for rate limiting

### Is it about retries?
→ Use `apps/core/constants/retry.py`
- `MAX_RETRIES_*` for retry counts
- `RETRY_*_DELAY` for initial/max delays
- `RETRY_BACKOFF_MULTIPLIER` for exponential backoff
- Pre-configured policies: `DATABASE_OPERATION_RETRY`, `NETWORK_OPERATION_RETRY`

## Constants Organization

```
apps/core/constants/
├── __init__.py                 # Main exports (142 constants)
├── datetime_constants.py       # Time units, formats, timedeltas
├── sentinel_constants.py       # Sentinel/NONE object factories
├── error_codes.py              # Error code mappings
├── spatial_constants.py        # Geographic constants
├── timeouts.py                 # NEW: Network/task timeouts (39)
├── cache_ttl.py                # NEW: Cache TTL values (49)
└── retry.py                    # NEW: Retry strategies (54)
```

## Total Constants Added

- **timeouts.py**: 39 constants
- **cache_ttl.py**: 49 constants
- **retry.py**: 54 constants
- **Total new**: 142 constants
- **Exported from __init__.py**: All 142

## Best Practices

1. **Always use the constant** instead of hardcoding the value
2. **Use the specific constant** (e.g., `HELPBOT_CACHE_TIMEOUT` not `CACHE_TTL_LONG`)
3. **Group related imports** at the top of the module
4. **Use operation-specific policies** when available (e.g., `NETWORK_OPERATION_RETRY`)
5. **Document the purpose** in comments when non-obvious
6. **Don't create local magic numbers** - add to constants first

## Anti-Patterns to Avoid

```python
# ❌ WRONG: Hardcoded magic number
timeout = 3600

# ✅ CORRECT: Named constant
from apps.core.constants.timeouts import TASK_EXPIRES_STANDARD
timeout = TASK_EXPIRES_STANDARD

# ❌ WRONG: Loose semantic
cache.set('key', value, 300)

# ✅ CORRECT: Intent is clear
from apps.core.constants.cache_ttl import CACHE_TTL_SHORT
cache.set('key', value, timeout=CACHE_TTL_SHORT)

# ❌ WRONG: Embedded calculations
time_limit = 300 + (300 * 5)  # Not immediately clear

# ✅ CORRECT: Use constants for composition
from apps.core.constants.cache_ttl import CACHE_TTL_MEDIUM, RATE_LIMIT_WINDOW_MEDIUM
window = RATE_LIMIT_WINDOW_MEDIUM  # Intent: 15 min rate limit window
```

## Integration Checklist

When adding new timeout/cache/retry code:

- [ ] Does this value appear in settings? → Create setting + constant mapping
- [ ] Is this a network timeout? → Use `REQUEST_TIMEOUT_*` or service-specific
- [ ] Is this a cache TTL? → Check if application-specific constant exists
- [ ] Is this a retry count? → Use `MAX_RETRIES_*` or operation-specific policy
- [ ] Is the constant already exported from `__init__.py`?
- [ ] Did you add documentation in docstring?
- [ ] Can this value be overridden by settings (for dev/prod differences)?

## Troubleshooting

### "Cannot import name 'XXX_TIMEOUT' from apps.core.constants"

**Solution**: Check the constant is:
1. Defined in the appropriate module (timeout, cache_ttl, or retry)
2. Listed in the module's `__all__` export
3. Listed in `apps/core/constants/__init__.py`

```python
# Check available constants
from apps.core import constants
print(dir(constants))  # Lists all exported constants
```

### Need a timeout that doesn't exist?

**Add it to the appropriate module**:

```python
# In apps/core/constants/timeouts.py or cache_ttl.py
MY_CUSTOM_TIMEOUT: Final[int] = 1200  # 20 minutes

# Then add to __all__ in that module
__all__ = [
    # ... existing
    'MY_CUSTOM_TIMEOUT',
]

# Then add to apps/core/constants/__init__.py
from .timeouts import MY_CUSTOM_TIMEOUT
```

Then submit PR with the new constant and its usage.

---

**Last Updated**: November 5, 2025
**Created By**: Agent 32: Magic Number Extraction Phase 6
**Status**: Constants created and ready for integration
