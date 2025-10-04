# Cache TTL Magic Number Migration Guide

**Date:** 2025-09-30
**Priority:** 🟠 MEDIUM
**Scope:** 268 files across the codebase
**Effort:** Team-wide gradual migration recommended

---

## 📊 Overview

**Problem:** Widespread use of magic numbers for cache TTL (Time To Live) values:
- **56 files** contain `86400` (seconds in a day)
- **212 files** contain `3600` (seconds in an hour)
- **Total:** 268 files requiring updates

**Solution:** Use centralized constants from `apps.core.constants.datetime_constants`

---

## 🎯 Benefits of Migration

1. **Maintainability:** Change cache TTL policies in one place
2. **Readability:** `SECONDS_IN_DAY` is clearer than `86400`
3. **Consistency:** All cache operations use the same constants
4. **Flexibility:** Easy to adjust TTL values globally
5. **Compliance:** Follows Rule #13 from `.claude/rules.md`

---

## 📋 Available Constants

```python
from apps.core.constants.datetime_constants import (
    SECONDS_IN_MINUTE,   # 60
    SECONDS_IN_HOUR,     # 3600
    SECONDS_IN_DAY,      # 86400
    SECONDS_IN_WEEK,     # 604800
    MINUTES_IN_HOUR,     # 60
    MINUTES_IN_DAY,      # 1440
    HOURS_IN_DAY,        # 24
    DAYS_IN_WEEK,        # 7
)
```

---

## 🔄 Migration Patterns

### Pattern 1: Simple Cache.set() with 86400

```python
# ❌ BEFORE:
cache.set('my_key', value, 86400)

# ✅ AFTER:
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
cache.set('my_key', value, SECONDS_IN_DAY)
```

### Pattern 2: Simple Cache.set() with 3600

```python
# ❌ BEFORE:
cache.set('my_key', value, 3600)

# ✅ AFTER:
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
cache.set('my_key', value, SECONDS_IN_HOUR)
```

### Pattern 3: Multiplied Values

```python
# ❌ BEFORE:
cache.set('my_key', value, 3600 * 24)  # 24 hours

# ✅ AFTER:
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
cache.set('my_key', value, SECONDS_IN_DAY)

# OR if you need custom duration:
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
cache.set('my_key', value, SECONDS_IN_HOUR * 24)
```

### Pattern 4: Custom Cache TTL Classes

```python
# ❌ BEFORE:
class MyCacheService:
    CACHE_TIMEOUT = 86400

    def cache_data(self, key, value):
        cache.set(key, value, self.CACHE_TIMEOUT)

# ✅ AFTER:
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

class MyCacheService:
    CACHE_TIMEOUT = SECONDS_IN_DAY

    def cache_data(self, key, value):
        cache.set(key, value, self.CACHE_TIMEOUT)
```

### Pattern 5: Settings.py Configuration

```python
# ❌ BEFORE (settings/base.py):
SESSION_COOKIE_AGE = 86400  # 24 hours

# ✅ AFTER:
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
SESSION_COOKIE_AGE = SECONDS_IN_DAY
```

### Pattern 6: Celery Task Expiry

```python
# ❌ BEFORE:
@shared_task(expires=3600)
def my_task():
    pass

# ✅ AFTER:
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

@shared_task(expires=SECONDS_IN_HOUR)
def my_task():
    pass
```

---

## 📂 Files by Priority

### 🔴 **High Priority (Core Services)** - 8 files

These should be migrated first as they're used across the application:

1. `apps/core/services/geofence_service.py` ⚠️ **Already refactored** - now uses `geofence_query_service.py`
2. `apps/core/services/task_webhook_service.py`
3. `apps/core/services/log_access_auditing_service.py`
4. `apps/core/services/async_api_service.py`
5. `apps/core/services/async_pdf_service.py`
6. `apps/core/services/sql_injection_monitor.py`
7. `apps/core/services/secure_query_logger.py`
8. `apps/core/services/security_monitoring_service.py`

### 🟠 **Medium Priority (Middleware & Monitoring)** - 11 files

Performance and monitoring code:

9. `apps/core/middleware/database_performance_monitoring.py`
10. `apps/core/middleware/performance_monitoring.py`
11. `apps/core/middleware/static_asset_optimization.py`
12. `apps/core/middleware/navigation_tracking.py`
13. `apps/core/middleware/path_based_rate_limiting.py`
14. `apps/core/middleware/error_response_validation.py`
15. `apps/core/middleware/slow_query_detection.py`
16. `apps/core/middleware/query_performance_monitoring.py`
17. `apps/core/monitoring/google_maps_monitor.py`
18. `apps/core/monitoring/graphql_security_monitor.py`
19. `apps/core/caching/ttl_monitor.py`

### 🟡 **Low Priority (Views, Tests, Utils)** - 12 files

Less critical but should be migrated eventually:

20. `apps/core/views/realtime_views.py`
21. `apps/core/views/monitoring_views.py`
22. `apps/core/cache_strategies.py`
23. `apps/core/cache_manager.py`
24. `apps/core/url_router_optimized.py`
25. `apps/core/consumers.py`
26. `apps/core/management/commands/optimize_database.py`
27. `apps/core/management/commands/warm_caches.py`
28. `apps/core/tests/test_monitoring_api_auth.py`
29. `apps/core/tests/test_rate_limiting_penetration.py`
30. `apps/core/tests/test_rate_limiting_comprehensive.py`
31. `apps/core/tests/test_async_operations_comprehensive.py`

### 🟢 **Remaining Files** - 237 files

Across other apps:
- Activity module: ~40 files
- Peoples module: ~35 files
- Attendance module: ~30 files
- Scheduler module: ~25 files
- Onboarding module: ~20 files
- Reports module: ~15 files
- Other modules: ~72 files

---

## 🚀 Migration Strategy

### Phase 1: Critical Services (Week 1)
**Target:** 8 core service files
**Owner:** Backend team lead
**Estimated Time:** 2-3 hours

### Phase 2: Middleware & Monitoring (Week 2)
**Target:** 11 middleware/monitoring files
**Owner:** Performance team
**Estimated Time:** 3-4 hours

### Phase 3: Module-by-Module Migration (Weeks 3-6)
**Target:** Remaining 249 files
**Owner:** Module owners
**Estimated Time:** 1-2 hours per module
**Approach:** Each team updates their own modules

---

## ✅ Testing Checklist

After migration, verify:

- [ ] All cache operations still work correctly
- [ ] Cache expiry times haven't changed unintentionally
- [ ] No performance regressions
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Load testing shows consistent performance

---

## 🛡️ Safety Guidelines

### DO:
- ✅ Migrate one file at a time and test
- ✅ Use version control (commit after each file)
- ✅ Add imports at the top of the file
- ✅ Keep the same TTL values (just use constants)
- ✅ Update tests if they verify specific TTL values

### DON'T:
- ❌ Change TTL values during migration
- ❌ Batch-replace without testing
- ❌ Skip imports (will cause NameError at runtime)
- ❌ Migrate test files before production code

---

## 📝 Example Pull Request Template

```markdown
## Cache TTL Magic Number Migration - [Module Name]

### Summary
Replaced magic numbers (86400, 3600) with constants from `datetime_constants`.

### Files Changed
- `apps/[module]/[file1].py` - Replaced `86400` with `SECONDS_IN_DAY`
- `apps/[module]/[file2].py` - Replaced `3600` with `SECONDS_IN_HOUR`

### Testing
- [x] Unit tests pass
- [x] Manual testing completed
- [x] Cache behavior unchanged

### Breaking Changes
None - TTL values remain identical

### Compliance
Follows Rule #13 from `.claude/rules.md` - Use constants instead of magic numbers
```

---

## 🔍 Finding Magic Numbers in Your Module

Use grep to find files in your module:

```bash
# Find files with 86400 (seconds in day)
grep -r "86400" apps/[your_module]/ --include="*.py"

# Find files with 3600 (seconds in hour)
grep -r "3600" apps/[your_module]/ --include="*.py"

# Find cache.set calls with magic numbers
grep -r "cache\.set.*[0-9]\{4,\}" apps/[your_module]/ --include="*.py"
```

---

## 📊 Progress Tracking

**Overall Progress:**
- **Total Files:** 268
- **Migrated:** 0 (as of 2025-09-30)
- **Remaining:** 268
- **Target Completion:** 6 weeks from project start

**Module Progress:**
- [ ] Core Services (8 files)
- [ ] Core Middleware (11 files)
- [ ] Core Views/Utils (12 files)
- [ ] Activity Module (~40 files)
- [ ] Peoples Module (~35 files)
- [ ] Attendance Module (~30 files)
- [ ] Scheduler Module (~25 files)
- [ ] Onboarding Module (~20 files)
- [ ] Reports Module (~15 files)
- [ ] Other Modules (~72 files)

---

## 🤝 Support

**Questions?** Contact:
- Backend Team Lead for core services
- Module owners for specific modules
- Architecture team for design decisions

**Resources:**
- [DateTime Standards Doc](docs/DATETIME_FIELD_STANDARDS.md)
- [DateTime Constants API](apps/core/constants/datetime_constants.py)
- [Code Quality Rules](.claude/rules.md)

---

**Created:** 2025-09-30
**Last Updated:** 2025-09-30
**Status:** 🟠 Migration Not Started - Guide Complete
**Next Action:** Begin Phase 1 (8 core service files)