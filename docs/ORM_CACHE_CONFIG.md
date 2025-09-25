# Django ORM Cache Configuration

## Redis Setup

### 1. Install Redis

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis
sudo systemctl enable redis
```

### 2. Install Django Redis

```bash
pip install django-redis
```

### 3. Configure Django Settings

Add to your `settings.py` or `settings/local.py`:

```python
# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'KEY_PREFIX': 'youtility',
            'VERSION': 1,
            'TIMEOUT': 300,  # Default timeout (5 minutes)
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'PICKLE_VERSION': -1,
        }
    }
}

# Session Configuration (optional - for better performance)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Cache key patterns
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_KEY_PREFIX = 'youtility'
CACHE_MIDDLEWARE_SECONDS = 300
```

### 4. Environment Variables

Add to `.env` file:

```env
# Cache Configuration
REDIS_URL=redis://127.0.0.1:6379/1
USE_CACHE_FOR_ORM=true
CACHE_TTL_PERSON_GROUPS=3600
CACHE_TTL_JOB_NEEDS=300
CACHE_TTL_EXTERNAL_TOURS=300
```

### 5. Update Job Manager

Modify `apps/activity/managers/job_manager.py` to use cached version:

```python
import os

class JobneedManager(TenantAwareManager):
    # ... existing code ...
    
    def get_job_needs(self, people_id, bu_id, client_id):
        """Get job needs using ORM with optional caching"""
        use_cache = os.environ.get('USE_CACHE_FOR_ORM', 'false').lower() == 'true'
        
        if use_cache:
            from .job_manager_orm_cached import CachedJobneedManagerORM
            return CachedJobneedManagerORM.get_job_needs(
                self, people_id, bu_id, client_id
            )
        else:
            from .job_manager_orm import JobneedManagerORM
            return JobneedManagerORM.get_job_needs(
                self, people_id, bu_id, client_id
            )
```

## Cache Management

### Clear Cache Commands

```python
# Django shell commands
from django.core.cache import cache

# Clear all cache
cache.clear()

# Clear specific key
cache.delete('job_needs:...')

# Clear pattern (if using django-redis)
from django_redis import get_redis_connection
redis_conn = get_redis_connection("default")
redis_conn.delete(*redis_conn.keys("job_needs:*"))
```

### Management Command

Create `apps/core/management/commands/clear_orm_cache.py`:

```python
from django.core.management.base import BaseCommand
from django.core.cache import cache
from apps.activity.managers.job_manager_orm_cached import CachedJobneedManagerORM

class Command(BaseCommand):
    help = 'Clear ORM cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--person',
            type=int,
            help='Clear cache for specific person ID'
        )

    def handle(self, *args, **options):
        if options['person']:
            CachedJobneedManagerORM.clear_cache_for_person(options['person'])
            self.stdout.write(f"Cleared cache for person {options['person']}")
        else:
            cache.clear()
            self.stdout.write("Cleared all cache")
```

Usage:
```bash
# Clear all cache
python manage.py clear_orm_cache

# Clear cache for specific person
python manage.py clear_orm_cache --person 123
```

## Cache Warming

### Celery Task

Create `apps/activity/tasks.py`:

```python
from celery import shared_task
from apps.activity.managers.job_manager_orm_cached import CachedJobneedManagerORM

@shared_task
def warm_job_cache(people_ids, bu_id, client_id):
    """Pre-warm cache for multiple people"""
    CachedJobneedManagerORM.warm_cache(people_ids, bu_id, client_id)
    return f"Warmed cache for {len(people_ids)} people"
```

### Daily Cache Warming

Add to your celery beat schedule:

```python
CELERY_BEAT_SCHEDULE = {
    'warm-job-cache': {
        'task': 'apps.activity.tasks.warm_job_cache',
        'schedule': crontab(hour=6, minute=0),  # 6 AM daily
        'args': ([1, 2, 3, 4, 5], 1, 1),  # Active people IDs
    },
}
```

## Monitoring

### Cache Hit Rate

```python
# Add to your monitoring
import logging
from django.core.cache import cache

logger = logging.getLogger('cache_monitor')

def log_cache_stats():
    """Log cache statistics"""
    # For django-redis
    from django_redis import get_redis_connection
    conn = get_redis_connection("default")
    info = conn.info()
    
    hits = info.get('keyspace_hits', 0)
    misses = info.get('keyspace_misses', 0)
    hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0
    
    logger.info(f"Cache hit rate: {hit_rate:.2f}% (hits: {hits}, misses: {misses})")
```

### Django Debug Toolbar

Add cache panel to see cache queries:

```python
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.cache.CachePanel',
        # ... other panels
    ]
```

## Performance Testing

### Test Cache Performance

```python
# test_cache_performance.py
import time
from django.core.cache import cache
from apps.activity.managers.job_manager_orm_cached import CachedJobneedManagerORM
from apps.activity.models.job_model import Jobneed

def test_cache_performance():
    people_id, bu_id, client_id = 1, 1, 1
    
    # Clear cache
    cache.clear()
    
    # First call (cache miss)
    start = time.time()
    result1 = CachedJobneedManagerORM.get_job_needs(
        Jobneed.objects, people_id, bu_id, client_id
    )
    time1 = time.time() - start
    
    # Second call (cache hit)
    start = time.time()
    result2 = CachedJobneedManagerORM.get_job_needs(
        Jobneed.objects, people_id, bu_id, client_id
    )
    time2 = time.time() - start
    
    print(f"Cache miss: {time1:.4f}s")
    print(f"Cache hit: {time2:.4f}s")
    print(f"Speed improvement: {time1/time2:.2f}x")
```

## Expected Performance Improvements

With caching enabled:

1. **First request**: Same as non-cached (cache miss)
2. **Subsequent requests**: 50-100x faster (cache hit)
3. **Overall improvement**: 10-50x depending on cache hit rate

### Typical Response Times

- Without cache: 250ms (job queries)
- With cache (miss): 250ms
- With cache (hit): 2-5ms

### Cache Hit Rates

- Person groups: 90%+ (changes rarely)
- Job needs: 70-80% (5-minute TTL)
- External tours: 70-80% (5-minute TTL)

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```
   redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
   ```
   Solution: Ensure Redis is running: `sudo systemctl start redis`

2. **Cache Not Working**
   - Check Redis is running: `redis-cli ping`
   - Verify Django settings
   - Check cache key generation

3. **High Memory Usage**
   - Reduce cache TTL
   - Implement cache eviction
   - Monitor Redis memory: `redis-cli info memory`

### Debug Cache

```python
# Check if caching is working
from django.core.cache import cache

# Test set/get
cache.set('test_key', 'test_value', 60)
print(cache.get('test_key'))  # Should print 'test_value'

# Check cache backend
from django.core.cache import caches
print(caches['default']._cache)  # Should show Redis client
```