# Django ORM Performance Optimization Guide

## Overview

This guide provides strategies to optimize the Django ORM implementations that replace PostgreSQL functions.

## Current Performance Status

Based on test results:
- ✅ All tests passing (100% data integrity)
- ⚠️ Performance slower than PostgreSQL functions (expected)
- 🎯 Key areas for optimization: Job functions (95-143x slower)

## Optimization Strategies

### 1. Query Optimization

#### Already Implemented
- ✅ Reduced `select_related()` to only necessary relationships
- ✅ Added `only()` to fetch specific fields
- ✅ Used `distinct()` to avoid duplicates

#### Additional Optimizations

```python
# Use prefetch_related for many-to-many or reverse foreign keys
queryset = manager.prefetch_related(
    Prefetch('jobdetails_set', queryset=JobDetails.objects.only('id', 'answer'))
)

# Use values() for read-only data
queryset = manager.values('id', 'jobdesc', 'plandatetime')

# Use iterator() for large datasets
for job in queryset.iterator(chunk_size=1000):
    # Process job
```

### 2. Database Indexes

Add indexes to frequently queried fields:

```python
# In your model
class Meta:
    indexes = [
        models.Index(fields=['bu_id', 'client_id', 'people_id']),
        models.Index(fields=['plandatetime', 'expirydatetime']),
        models.Index(fields=['identifier', 'jobstatus']),
    ]
```

Create migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Caching Implementation

#### Redis Caching (Recommended)

```python
from django.core.cache import cache

@staticmethod
def get_job_needs(manager, people_id, bu_id, client_id):
    # Create cache key
    cache_key = f"job_needs_{people_id}_{bu_id}_{client_id}"
    
    # Try cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Run query
    result = # ... existing implementation
    
    # Cache for 5 minutes
    cache.set(cache_key, result, 300)
    
    return result
```

#### Query Result Caching

```python
from django.core.cache import cache
from django.db.models import Q

class CachedJobneedManagerORM:
    @staticmethod
    def get_person_groups(people_id):
        """Cache person's group memberships"""
        cache_key = f"person_groups_{people_id}"
        groups = cache.get(cache_key)
        
        if groups is None:
            groups = list(
                Pgbelonging.objects
                .filter(people_id=people_id)
                .exclude(pgroup_id=-1)
                .values_list('pgroup_id', flat=True)
            )
            cache.set(cache_key, groups, 3600)  # 1 hour
            
        return groups
```

### 4. Query Batching

For multiple queries, use batching:

```python
# Instead of multiple individual queries
for person_id in person_ids:
    jobs = get_job_needs(manager, person_id, bu_id, client_id)
    
# Use single query with IN clause
all_jobs = manager.filter(
    people_id__in=person_ids,
    bu_id=bu_id,
    client_id=client_id
)
```

### 5. Connection Pooling

Configure database connection pooling:

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',  # 30 seconds
        },
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}
```

### 6. Query Analysis

Use Django Debug Toolbar or query logging:

```python
# Enable query logging in development
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### 7. Asynchronous Processing

For heavy queries, consider async:

```python
from asgiref.sync import sync_to_async

@sync_to_async
def get_job_needs_async(manager, people_id, bu_id, client_id):
    return JobneedManagerORM.get_job_needs(
        manager, people_id, bu_id, client_id
    )

# Usage in async view
jobs = await get_job_needs_async(manager, people_id, bu_id, client_id)
```

## Implementation Priority

1. **High Priority** (Immediate impact)
   - Add database indexes
   - Implement Redis caching for job functions
   - Cache person group memberships

2. **Medium Priority** (Good improvement)
   - Query batching for bulk operations
   - Connection pooling configuration
   - Use `values()` for read-only operations

3. **Low Priority** (Nice to have)
   - Async processing for heavy queries
   - Query result pagination
   - Background job processing

## Monitoring Performance

### Django Silk

Install and configure Django Silk for profiling:

```bash
pip install django-silk
```

```python
# settings.py
MIDDLEWARE = [
    # ...
    'silk.middleware.SilkyMiddleware',
    # ...
]

INSTALLED_APPS = [
    # ...
    'silk',
    # ...
]
```

### Custom Performance Logging

```python
import time
import logging

logger = logging.getLogger('performance')

def log_performance(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        logger.info(f"{func.__name__} took {duration:.3f}s")
        
        if duration > 1.0:  # Log slow queries
            logger.warning(f"Slow query: {func.__name__} took {duration:.3f}s")
            
        return result
    return wrapper

# Usage
@log_performance
def get_job_needs(manager, people_id, bu_id, client_id):
    # ... implementation
```

## Expected Performance Improvements

With these optimizations:

1. **Caching**: 50-90% reduction in response time for cached queries
2. **Indexes**: 30-70% improvement for filtered queries
3. **Query optimization**: 20-40% improvement
4. **Connection pooling**: 10-20% improvement

Target performance ratios after optimization:
- Asset functions: 2-3x slower than PostgreSQL (acceptable)
- Job functions: 5-10x slower than PostgreSQL (from 95-143x)
- Business unit functions: Already optimal (0.15x - faster than PostgreSQL)

## Testing Performance

After implementing optimizations:

```bash
# Run benchmark with more iterations
python benchmark_orm_performance.py --iterations 100 --warmup 10

# Compare before/after results
python validate_orm_migrations.py
```

## Gradual Rollout Strategy

1. Implement caching in staging
2. Monitor cache hit rates
3. Add indexes and test
4. Enable for subset of users
5. Monitor performance metrics
6. Full rollout if metrics are acceptable

Remember: The goal is not to match PostgreSQL function speed exactly, but to achieve acceptable performance with the benefits of Django ORM (maintainability, security, portability).