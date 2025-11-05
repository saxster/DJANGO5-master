# Phase 6: Magic Number Extraction - Complete Reference

## Overview

This document tracks the extraction of 50+ hardcoded magic numbers into centralized named constants, eliminating scattered numeric literals across the codebase.

## Created Constant Modules

### 1. `apps/core/constants/timeouts.py` (NEW)
**Purpose**: Centralize all network, task, and operation timeouts.

**Key Constants**:
- HTTP request timeouts: `REQUEST_TIMEOUT_SHORT` (5, 15), `REQUEST_TIMEOUT_MEDIUM` (5, 30), `REQUEST_TIMEOUT_LONG` (5, 60)
- Task execution timeouts: `CELERY_SOFT_TIMEOUT_SHORT` (300s), `CELERY_HARD_TIMEOUT_LONG` (3600s)
- Task expiration: `TASK_EXPIRES_STANDARD` (3600s), `TASK_EXPIRES_LONG` (7200s)
- WebSocket timeouts: `WEBSOCKET_JWT_CACHE_TIMEOUT` (300s), `WEBSOCKET_PRESENCE_TIMEOUT` (300s)
- Service timeouts: `GOOGLE_MAPS_TIMEOUT`, `FRAPPE_TIMEOUT`, `GEOFENCE_VALIDATION_TIMEOUT`

**Total Constants**: 39

### 2. `apps/core/constants/cache_ttl.py` (NEW)
**Purpose**: Centralize all cache Time-To-Live and expiration values.

**Key Constants**:
- General TTL: `CACHE_TTL_SHORT` (300s), `CACHE_TTL_DEFAULT` (1800s), `CACHE_TTL_DAILY` (86400s)
- Application-specific: `HELPBOT_CACHE_TIMEOUT` (3600s), `REPORT_GENERATION_CACHE_TIMEOUT` (3600s)
- Idempotency: `IDEMPOTENCY_TTL_STANDARD` (7200s), `SITE_AUDIT_IDEMPOTENCY_TTL` (300s)
- Rate limiting windows: `RATE_LIMIT_WINDOW_SHORT` (300s), `REPORT_GENERATION_RATE_LIMIT_WINDOW` (300s)
- Temperature-based: `HOT_CACHE_TTL` (300s), `WARM_CACHE_TTL` (1800s), `COLD_CACHE_TTL` (3600s)

**Total Constants**: 49

### 3. `apps/core/constants/retry.py` (NEW)
**Purpose**: Centralize all retry counts, backoff strategies, and circuit breaker configuration.

**Key Constants**:
- Retry counts: `MAX_RETRIES_SHORT` (3), `MAX_RETRIES_STANDARD` (5), `MAX_RETRIES_LONG` (10)
- Database retries: `DATABASE_RETRY_COUNT` (3), `DATABASE_CONNECTION_RETRY_COUNT` (5)
- Network retries: `NETWORK_RETRY_COUNT` (5), `WEBHOOK_RETRY_COUNT` (3)
- Backoff: `RETRY_BACKOFF_MULTIPLIER` (2.0), `RETRY_BACKOFF_MULTIPLIER_GENTLE` (1.5)
- Initial delays: `RETRY_INITIAL_DELAY_SHORT` (1s), `RETRY_INITIAL_DELAY_MEDIUM` (2s)
- Max delays: `RETRY_MAX_DELAY_SHORT` (60s), `RETRY_MAX_DELAY_LONG` (900s)
- Jitter: `RETRY_JITTER_RANGE_SMALL` (0, 1), `RETRY_JITTER_RANGE_LARGE` (0, 30)
- Operation-specific policies: `DATABASE_OPERATION_RETRY`, `NETWORK_OPERATION_RETRY`, `CELERY_TASK_RETRY`
- Circuit breaker: `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (5), `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` (60s)

**Total Constants**: 54

### 4. `apps/core/constants/datetime_constants.py` (EXISTING - UPDATED)
**Previous**: Had core datetime/timedelta constants
**New additions**: Already contains `TIMEZONE_OFFSETS` with IST (330 minutes) offset mapping

## Files Analyzed for Magic Numbers

### Settings Files (Highest Concentration)
- `intelliwiz_config/settings/base.py`: HELPBOT_CACHE_TIMEOUT (3600), HELPBOT_ANALYTICS_CACHE_TIMEOUT (1800)
- `intelliwiz_config/settings_ia.py`: IA_CACHE_TIMEOUT (3600), NAV_MENU_CACHE_TIMEOUT (1800)
- `intelliwiz_config/settings/websocket.py`: WEBSOCKET_JWT_CACHE_TIMEOUT (300), WEBSOCKET_PRESENCE_TIMEOUT (300)
- `intelliwiz_config/settings/database.py`: TIMEOUT (300)
- `intelliwiz_config/settings/attendance.py`: MAX_FLYING_SPEED_KMH (900), cache options (3600)
- `intelliwiz_config/settings/ml_config.py`: RETRAINING_TIMEOUT (1800), ROLLBACK_CHECK_TIMEOUT (300)
- `intelliwiz_config/settings/onboarding.py`: LEARNING_FEATURE_CACHE_TIMEOUT (300), RERANK_CACHE_TIMEOUT (300)
- `intelliwiz_config/settings/performance.py`: p95/p50 thresholds (300)
- `intelliwiz_config/settings/redis/cache.py`: TIMEOUT (300/60), GROUP_EXPIRY (86400)
- `intelliwiz_config/settings/redis/sentinel.py`: TIMEOUT (900/SECONDS_IN_HOUR), visibility_timeout (3600)
- `intelliwiz_config/settings/redis/failover.py`: visibility_timeout (3600), group_expiry (86400)
- `intelliwiz_config/settings/celery_config.py`: visibility_timeout (3600), CELERY_TASK_SOFT_TIME_LIMIT (1800)
- `intelliwiz_config/settings/observability.py`: WEBSOCKET_PRESENCE_TIMEOUT (300)
- `intelliwiz_config/settings/llm.py`: daily_budget_cents (1800)
- `intelliwiz_config/settings/security/rate_limiting.py`: window_seconds (300, 900)
- `intelliwiz_config/celery.py`: expires (7200, 3600, 1800), soft_time_limit (300), time_limit (3600)

### Celery/Task Files
- `background_tasks/mental_health_intervention_tasks.py`: countdown (300, 3600, 1800, 86400)
- `background_tasks/media_tasks.py`: default_retry_delay (300)
- `background_tasks/report_tasks.py`: default_retry_delay (300), idempotency_ttl (900)
- `background_tasks/site_audit_tasks.py`: idempotency_ttl (300, 900, 3600)
- `background_tasks/onboarding_retry_strategies.py`: max_delay (300)
- `background_tasks/agent_tasks.py`: cache timeout (300), soft_time_limit (300)
- `background_tasks/rest_api_tasks.py`: timeout (3600)
- `scripts/migrate_to_idempotent_tasks.py`: ttl (7200, 3600)
- `scripts/test_performance_optimizations.py`: timeout (300, 1800)

### Service Files
- `apps/reports/services/frappe_service.py`: CONNECTION_CACHE_TIMEOUT (300)
- `apps/reports/services/report_generation_service.py`: rate_limit window_seconds (300)
- `apps/core/services/cache_warming_service.py`: cache timeouts
- `apps/core/services/redis_backup_service.py`: Various cache TTLs
- `apps/y_helpdesk/services/ticket_cache_service.py`: Cache operations

### Monitoring & Health Check Files
- `apps/core/health_checks/sentinel.py`: Health check timeouts
- `apps/core/health_checks/cache.py`: Cache operation timeouts
- `monitoring/real_time_alerts.py`: Alert timeout windows
- `monitoring/performance_monitor_enhanced.py`: Performance monitoring intervals

### Test Files
- Multiple test files using time.sleep(3600), time.sleep(300), etc.
- Cache test fixtures using hardcoded TTL values

## Migration Guide

### Before (Using Magic Numbers)
```python
# In apps/helpbot/services/conversation_service.py
self.cache_timeout = getattr(settings, 'HELPBOT_CACHE_TIMEOUT', 3600)

# In apps/reports/services/frappe_service.py
CONNECTION_CACHE_TIMEOUT = 300

# In background_tasks/report_tasks.py
idempotency_ttl = 900

# In intelliwiz_config/celery.py
'soft_time_limit': 300,
'expires': 7200,

# In any retry logic
for attempt in range(5):
    try:
        operation()
        break
    except Exception:
        if attempt < 4:
            time.sleep(2 * (2 ** attempt))  # Exponential backoff
```

### After (Using Named Constants)
```python
# In apps/helpbot/services/conversation_service.py
from apps.core.constants.cache_ttl import HELPBOT_CACHE_TIMEOUT
self.cache_timeout = getattr(settings, 'HELPBOT_CACHE_TIMEOUT', HELPBOT_CACHE_TIMEOUT)

# In apps/reports/services/frappe_service.py
from apps.core.constants.cache_ttl import FRAPPE_CONNECTION_CACHE_TIMEOUT
CONNECTION_CACHE_TIMEOUT = FRAPPE_CONNECTION_CACHE_TIMEOUT

# In background_tasks/report_tasks.py
from apps.core.constants.cache_ttl import REPORT_IDEMPOTENCY_TTL
idempotency_ttl = REPORT_IDEMPOTENCY_TTL

# In intelliwiz_config/celery.py
from apps.core.constants.timeouts import (
    CELERY_SOFT_TIMEOUT_SHORT,
    TASK_EXPIRES_VERY_LONG
)
'soft_time_limit': CELERY_SOFT_TIMEOUT_SHORT,
'expires': TASK_EXPIRES_VERY_LONG,

# In any retry logic
from apps.core.constants.retry import (
    MAX_RETRIES_STANDARD,
    RETRY_BACKOFF_MULTIPLIER,
    RETRY_MAX_DELAY_MEDIUM
)

@with_retry(
    max_retries=MAX_RETRIES_STANDARD,
    retry_policy='DATABASE_OPERATION'
)
def safe_operation():
    operation()
```

## Key Characteristics of Constants

### Timeout Constants
- **Pattern**: All in seconds (int or tuple)
- **Tuple format**: (connect_timeout, read_timeout) for HTTP operations
- **Range**: 1 second to 1 hour (bounded to prevent hangs)
- **Categories**: HTTP requests, database ops, task execution, WebSocket, API services

### Cache TTL Constants
- **Pattern**: All in seconds (int)
- **Range**: 60 seconds (very short) to 365 days (retention)
- **Categories**: General cache, application-specific, idempotency, rate limiting
- **Strategy**: Temperature-based (hot/warm/cold) for different use cases

### Retry Constants
- **Retry counts**: 1-15 attempts (bounded)
- **Backoff multipliers**: 1.0 (linear) to 2.0 (exponential)
- **Initial delays**: 1-5 seconds
- **Max delays**: 60s (short) to 3600s (1 hour)
- **Jitter ranges**: (0, 1) to (0, 30) for thundering herd prevention
- **Operation-specific policies**: Pre-configured for common use cases

## Benefits

1. **Maintainability**: Single source of truth for all timeout/cache/retry values
2. **Consistency**: Ensures same timeouts across different layers
3. **Debugging**: Named constants are self-documenting in logs/errors
4. **Performance**: Easy to adjust policies without code changes (settings override support)
5. **Security**: Prevents accidental timeout vulnerabilities
6. **Testing**: Easy to mock different timeout scenarios
7. **Compliance**: Enforces timeout best practices (prevents hangs, bounds max delays)

## Integration Checklist

- [x] Create `apps/core/constants/timeouts.py` (39 constants)
- [x] Create `apps/core/constants/cache_ttl.py` (49 constants)
- [x] Create `apps/core/constants/retry.py` (54 constants)
- [x] Update `apps/core/constants/__init__.py` (export all 142 constants)
- [x] Validate syntax of all new modules
- [ ] Replace magic numbers in settings files (Priority: HIGH)
- [ ] Replace magic numbers in Celery/task files (Priority: HIGH)
- [ ] Replace magic numbers in service files (Priority: MEDIUM)
- [ ] Replace magic numbers in monitoring/health check files (Priority: MEDIUM)
- [ ] Update tests to use constants instead of hardcoded values
- [ ] Create PR with all replacements
- [ ] Run full test suite to ensure no regressions

## Statistics

- **Total magic numbers extracted**: 142 constants across 3 new modules
- **Files analyzed**: 60+
- **Timeout values found**: 39 (range: 60s to 2 hours)
- **Cache TTL values found**: 49 (range: 60s to 365 days)
- **Retry configuration values found**: 54 (retry counts, backoff, jitter, circuit breaker)
- **Highest concentration**: Settings files and Celery configuration
- **Removed dependencies on magic numbers**: All new code paths

## Usage Examples

### Example 1: HTTP Request with Proper Timeout
```python
from apps.core.constants.timeouts import REQUEST_TIMEOUT_LONG

# Before: No timeout (worker can hang)
response = requests.get(frappe_url, json=data)

# After: With named constant
response = requests.get(
    frappe_url,
    json=data,
    timeout=REQUEST_TIMEOUT_LONG  # (5, 60) - clear intent
)
```

### Example 2: Cache with Appropriate TTL
```python
from apps.core.constants.cache_ttl import (
    REPORT_GENERATION_CACHE_TIMEOUT,
    HOT_CACHE_TTL
)

# Before: Magic number scattered across code
cache.set('report_result', result, timeout=3600)

# After: Intent is clear
cache.set('report_result', result, timeout=REPORT_GENERATION_CACHE_TIMEOUT)
cache.set('hot_data', data, timeout=HOT_CACHE_TTL)
```

### Example 3: Resilient Database Operations
```python
from apps.core.constants.retry import DATABASE_OPERATION_RETRY
from apps.core.utils_new.retry_mechanism import with_retry

# Before: Hardcoded retry logic with magic numbers
for attempt in range(3):
    try:
        user.save()
        break
    except Exception:
        if attempt < 2:
            time.sleep(1 * (2 ** attempt))

# After: Declarative, reusable policy
@with_retry(
    exceptions=(IntegrityError, OperationalError),
    max_retries=DATABASE_OPERATION_RETRY['max_retries'],
    retry_policy='DATABASE_OPERATION'
)
def save_user(user):
    user.save()
```

## Next Steps

1. Replace hardcoded timeouts in `intelliwiz_config/celery.py`
2. Update settings files to reference constants instead of magic numbers
3. Migrate task files to use `TASK_EXPIRES_*` and `CELERY_SOFT_TIMEOUT_*`
4. Update service layer cache operations to use application-specific TTL constants
5. Migrate test files to use constants for fixtures
6. Create automated linting rule to detect new hardcoded timeout/cache/retry values

---

**Phase 6 Status**: Constants created and exported - ready for migration across codebase
**Last Updated**: November 5, 2025
**Remaining Work**: Replace hardcoded values in 60+ files with constant references
