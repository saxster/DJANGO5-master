# Decision Matrix: Which Cache Backend?

**Quick guide for choosing the right caching strategy**

---

## Decision Matrix

| Use Case | Backend | Database | Why | Trade-offs |
|----------|---------|----------|-----|-----------|
| **Dropdown autocomplete (Select2)** | PostgreSQL | Materialized views | Fast enough (~20ms), no Redis dependency | 4x slower than Redis, acceptable for dropdowns |
| **Session storage** | PostgreSQL | django_session table | Architectural simplicity, 20ms acceptable | Could be faster with Redis |
| **General caching** | Redis | DB 1 (default) | Fast (<1ms), distributed, persistent | Requires Redis service |
| **Celery results** | Redis | DB 1 (shared) | Consistent with default cache | Shared with general cache |

## Configuration Examples

### Select2 Cache (PostgreSQL)

```python
# intelliwiz_config/settings/redis_optimized.py
CACHES['select2'] = {
    'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache',
    'LOCATION': '',  # No Redis needed
    'OPTIONS': {
        'MAX_ENTRIES': 10000,
        'CULL_FREQUENCY': 3,
    },
}
```

**Materialized views:**
- `mv_people_dropdown` (users)
- `mv_location_dropdown` (locations)
- `mv_asset_dropdown` (assets)

### Default Cache (Redis)

```python
CACHES['default'] = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
    'OPTIONS': {
        'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        'CONNECTION_POOL_KWARGS': {
            'max_connections': 100,
        },
        'PASSWORD': os.getenv('REDIS_PASSWORD'),
        'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',  # JSON (compliance)
    }
}
```

### Sessions (PostgreSQL)

```python
# Use database sessions (not Redis)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Trade-off: 20ms latency acceptable for architectural simplicity
```

## Performance Comparison

| Operation | Redis | PostgreSQL | Difference |
|-----------|-------|------------|------------|
| **Get (cache hit)** | <1ms | ~5ms | 5x slower |
| **Set** | <1ms | ~8ms | 8x slower |
| **Select2 lookup** | <5ms | ~20ms | 4x slower, acceptable |
| **Session load** | <3ms | ~20ms | 6x slower, acceptable |

## When to Use Each

### Use Redis When:
- ✅ Need <5ms response time
- ✅ High read/write frequency (>1000 req/s)
- ✅ Distributed caching across multiple servers
- ✅ Celery task results storage

### Use PostgreSQL When:
- ✅ Data already in database (materialized views)
- ✅ 20ms latency acceptable (UI dropdowns, sessions)
- ✅ Want to reduce infrastructure dependencies
- ✅ Easier debugging (SQL queries visible)

## Verification Commands

```bash
# Verify Redis configuration
python scripts/verify_redis_cache_config.py

# Test specific cache backend
python manage.py shell
>>> from django.core.cache import caches
>>> caches['default'].set('test', 'value', 60)
>>> caches['default'].get('test')
'value'

# Check Redis connection
redis-cli ping  # Should return "PONG"

# Check PostgreSQL materialized views
python manage.py shell
>>> from django.db import connection
>>> with connection.cursor() as cursor:
...     cursor.execute("SELECT COUNT(*) FROM mv_people_dropdown")
...     print(cursor.fetchone())
```

---

**See also:** [REFERENCE.md](../REFERENCE.md#configuration-files) - Complete Redis configuration
