# Caching Quick Reference Guide

Fast reference for implementing caching in the application.

---

## 🚀 Quick Start

### 1. Cache a Function Result

```python
from apps.core.utils_new.cache_utils import cache_result

@cache_result(timeout=300, key_prefix='my_function')
def expensive_operation(param1, param2):
    # Your expensive code here
    return result
```

### 2. Cache Dashboard Metrics

```python
from apps.reports.services.dashboard_cache_service import DashboardCacheService

metrics = DashboardCacheService.get_dashboard_metrics(
    site_id=123,
    date_range=(start_date, end_date)
)
```

### 3. Cache User Permissions

```python
from apps.peoples.services.permission_cache_service import PermissionCacheService

permissions = PermissionCacheService.get_user_permissions(user)
if permissions['can_create_tasks']:
    # User can create tasks
```

### 4. Manual Cache Management

```python
from django.core.cache import cache

# Set
cache.set('my_key', my_value, timeout=300)

# Get
value = cache.get('my_key')

# Delete
cache.delete('my_key')
```

---

## ⏱️ Cache Timeouts

| Use Case | TTL | Code |
|----------|-----|------|
| Dashboard metrics | 5 min | `timeout=300` |
| Chart data | 10 min | `timeout=600` |
| Site summaries | 15 min | `timeout=900` |
| User permissions | 15 min | `timeout=900` |
| ML results | 1 hour | `timeout=3600` |

---

## 🔄 Cache Invalidation

### Invalidate Specific Key

```python
from apps.core.utils_new.cache_utils import invalidate_cache

invalidate_cache('function_name', arg1, arg2, prefix='my_prefix')
```

### Invalidate Pattern

```python
from apps.core.utils_new.cache_utils import invalidate_pattern

invalidate_pattern('user_perms_*')
```

### Invalidate Site Cache

```python
from apps.reports.services.dashboard_cache_service import DashboardCacheService

DashboardCacheService.invalidate_site_cache(site_id)
```

---

## 📊 Monitoring

### Get Cache Statistics

```python
from apps.core.utils_new.cache_utils import get_cache_stats

stats = get_cache_stats()
# {'hits': 1500, 'misses': 500, 'hit_rate': 75.0}
```

### Enable Monitoring Middleware

In settings:
```python
MIDDLEWARE = [
    # ...
    'apps.core.middleware.cache_monitoring.CacheMonitoringMiddleware',
]
```

---

## 🔍 Query Optimization

### Replace count() > 0

❌ **Bad:**
```python
if queryset.count() > 0:
    do_something()
```

✅ **Good:**
```python
if queryset.exists():
    do_something()
```

### Automated Fix

```bash
python scripts/optimize_count_to_exists.py --dry-run  # Preview
python scripts/optimize_count_to_exists.py            # Apply
```

---

## 🎯 When to Cache?

✅ **Cache these:**
- Expensive database aggregations
- Complex calculations
- API responses
- ML inference results
- User permissions
- Dashboard metrics

❌ **Don't cache these:**
- User-specific sensitive data
- Real-time data
- Data that changes frequently (< 1 min)
- Small, fast queries

---

## 🛠️ Common Patterns

### Pattern 1: View-Level Cache

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # 5 minutes
def my_view(request):
    return render(request, 'template.html')
```

### Pattern 2: Data-Level Cache

```python
@cache_result(timeout=300)
def get_data(param):
    return expensive_query()

def my_view(request):
    data = get_data(request.GET['param'])
    return render(request, 'template.html', {'data': data})
```

### Pattern 3: Conditional Cache

```python
def my_view(request):
    if request.user.is_staff:
        # Real-time for admins
        data = get_fresh_data()
    else:
        # Cached for users
        data = get_cached_data()
```

---

## 🚨 Troubleshooting

### Cache Not Working?

1. **Check Redis:**
   ```bash
   redis-cli ping  # Should return PONG
   ```

2. **Check Cache Key:**
   ```python
   from django.core.cache import cache
   cache.set('test', 'value', 60)
   print(cache.get('test'))  # Should print 'value'
   ```

3. **Check Logs:**
   ```bash
   tail -f logs/cache.log
   ```

### Low Hit Rate?

1. TTL too short → Increase timeout
2. Cache keys not stable → Review key generation
3. Not enough caching → Add more @cache_result decorators

---

## 📝 Cheat Sheet

```python
# Import everything you need
from django.core.cache import cache
from apps.core.utils_new.cache_utils import (
    cache_result,
    invalidate_cache,
    get_cache_stats
)
from apps.reports.services.dashboard_cache_service import DashboardCacheService
from apps.peoples.services.permission_cache_service import PermissionCacheService

# Cache function
@cache_result(timeout=300)
def my_func(): ...

# Get cached data
data = cache.get('key')

# Set cached data
cache.set('key', value, 300)

# Invalidate
cache.delete('key')
invalidate_cache('func_name', args)

# Stats
stats = get_cache_stats()
```

---

## ✅ Checklist for New Features

When adding a new view/API:

- [ ] Identify expensive operations (>100ms)
- [ ] Add caching decorator or service call
- [ ] Set appropriate TTL
- [ ] Implement cache invalidation
- [ ] Add monitoring/logging
- [ ] Test cache hit/miss scenarios
- [ ] Document cache keys and TTLs

---

**Last Updated:** 2025-11-07  
**See Also:** [CACHING_OPTIMIZATION_IMPLEMENTATION.md](./CACHING_OPTIMIZATION_IMPLEMENTATION.md)
