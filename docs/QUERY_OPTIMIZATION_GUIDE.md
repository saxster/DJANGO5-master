# Django ORM Query Optimization Guide

## Overview

This guide provides best practices for writing efficient Django ORM queries in the YOUTILITY3 project. Following these guidelines will help maintain the 2-3x performance improvement achieved during the raw SQL to Django ORM migration.

## Table of Contents

1. [Key Principles](#key-principles)
2. [Common Optimization Techniques](#common-optimization-techniques)
3. [Caching Strategy](#caching-strategy)
4. [Query Patterns](#query-patterns)
5. [Performance Monitoring](#performance-monitoring)
6. [Troubleshooting](#troubleshooting)

## Key Principles

### 1. Avoid N+1 Queries

**Bad:**
```python
# This creates N+1 queries
tickets = Ticket.objects.all()
for ticket in tickets:
    print(ticket.site.name)  # Additional query for each ticket
```

**Good:**
```python
# This creates 1 query with JOIN
tickets = Ticket.objects.select_related('site').all()
for ticket in tickets:
    print(ticket.site.name)  # No additional query
```

### 2. Use select_related() for Forward ForeignKey and OneToOne

```python
# Optimize single-valued relationships
people = People.objects.select_related('client', 'bu').all()
```

### 3. Use prefetch_related() for Reverse ForeignKey and ManyToMany

```python
# Optimize multi-valued relationships
sites = Bt.objects.prefetch_related('ticket_set', 'task_set').all()
```

### 4. Use only() and defer() for Large Models

```python
# Fetch only required fields
tickets = Ticket.objects.only('id', 'ticketcode', 'status_id').all()

# Defer large fields
people = People.objects.defer('photo', 'bio').all()
```

## Common Optimization Techniques

### 1. Bulk Operations

**Creating Multiple Objects:**
```python
# Bad - Multiple INSERT queries
for data in items:
    Model.objects.create(**data)

# Good - Single INSERT query
Model.objects.bulk_create([
    Model(**data) for data in items
])
```

**Updating Multiple Objects:**
```python
# Bad - Multiple UPDATE queries
for obj in objects:
    obj.field = value
    obj.save()

# Good - Single UPDATE query
Model.objects.filter(condition).update(field=value)
```

### 2. Aggregations and Annotations

```python
# Use database aggregations instead of Python
from django.db.models import Count, Sum, Avg

# Bad - Fetches all records to Python
total = sum([t.amount for t in transactions])

# Good - Aggregation in database
total = Transaction.objects.aggregate(total=Sum('amount'))['total']

# Annotate with computed fields
sites = Bt.objects.annotate(
    ticket_count=Count('ticket'),
    open_tickets=Count('ticket', filter=Q(ticket__status__tacode='OPEN'))
)
```

### 3. Use Indexes Effectively

```python
# Queries that benefit from indexes:
# 1. Filtering by foreign keys
tickets = Ticket.objects.filter(site_id=1)

# 2. Filtering by frequently queried fields
tickets = Ticket.objects.filter(status__tacode='OPEN')

# 3. Date range queries
attendance = Attendance.objects.filter(
    checkin_time__gte=start_date,
    checkin_time__lt=end_date
)
```

## Caching Strategy

### 1. Using Cache Decorators

```python
from apps.core.cache_manager import cache_capability_tree, cache_bt_hierarchy

class QueryRepository:
    @staticmethod
    @cache_capability_tree()
    def get_web_caps_for_client():
        # Automatically cached for 1 hour
        return capabilities
    
    @staticmethod
    @cache_bt_hierarchy()
    def get_childrens_of_bt(bt_id: int):
        # Automatically cached for 30 minutes
        return children
```

### 2. Manual Cache Management

```python
from django.core.cache import cache

def get_expensive_data(param):
    cache_key = f'expensive_data_{param}'
    result = cache.get(cache_key)
    
    if result is None:
        result = expensive_computation(param)
        cache.set(cache_key, result, 3600)  # Cache for 1 hour
    
    return result
```

### 3. Cache Invalidation

```python
from apps.core.cache_manager import invalidate_site_cache, invalidate_user_cache

# Invalidate caches when data changes
def update_site(site_id, data):
    site = Bt.objects.get(id=site_id)
    site.update(**data)
    invalidate_site_cache(site_id)  # Clear related caches
```

## Query Patterns

### 1. Tree/Hierarchy Traversal

Instead of recursive CTEs, use Python tree traversal:

```python
from apps.core.queries import TreeTraversal

# Build tree structure efficiently
nodes = Model.objects.all()
tree = TreeTraversal.build_tree(
    nodes,
    root_id=1,
    parent_field='parent_id'
)
```

### 2. Complex Filtering with Q Objects

```python
from django.db.models import Q

# Complex OR conditions
tickets = Ticket.objects.filter(
    Q(status__tacode='OPEN') | Q(priority__tacode='HIGH'),
    site_id=site_id
)

# Dynamic query building
conditions = Q()
if status:
    conditions &= Q(status=status)
if assigned_to:
    conditions &= Q(assignedto=assigned_to)

tickets = Ticket.objects.filter(conditions)
```

### 3. Window Functions

```python
from django.db.models import Window, F
from django.db.models.functions import RowNumber, Lead

# Add row numbers
tickets = Ticket.objects.annotate(
    row_num=Window(
        expression=RowNumber(),
        partition_by=[F('site_id')],
        order_by=F('createdon').desc()
    )
)

# Get next value
activities = Activity.objects.annotate(
    next_activity=Window(
        expression=Lead('id'),
        partition_by=[F('site_id')],
        order_by=F('createdon')
    )
)
```

## Performance Monitoring

### 1. Django Debug Toolbar

```python
# In development settings
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

### 2. Query Logging

```python
# Log slow queries
LOGGING = {
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'slow_queries.log',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

### 3. Custom Query Analysis

```python
from django.db import connection
from django.test.utils import override_settings
import time

@override_settings(DEBUG=True)
def analyze_query(queryset):
    start_time = time.time()
    list(queryset)  # Execute query
    execution_time = time.time() - start_time
    
    queries = connection.queries[-1]
    print(f"Execution time: {execution_time:.3f}s")
    print(f"SQL: {queries['sql']}")
    print(f"Time: {queries['time']}")
```

## Troubleshooting

### Common Performance Issues

1. **Slow Tree Traversal**
   - Use `TreeCache` for frequently accessed hierarchies
   - Prefetch all nodes in one query
   - Build tree in Python instead of recursive SQL

2. **Large Result Sets**
   - Use pagination: `Model.objects.all()[:100]`
   - Use `iterator()` for large datasets
   - Consider using `values()` or `values_list()`

3. **Complex Aggregations**
   - Use database views for very complex queries
   - Consider denormalization for reporting tables
   - Use raw SQL only as last resort

### Query Optimization Checklist

- [ ] Are you using `select_related()` for foreign keys?
- [ ] Are you using `prefetch_related()` for reverse relations?
- [ ] Are you filtering in the database, not in Python?
- [ ] Are you using appropriate indexes?
- [ ] Are you caching expensive queries?
- [ ] Are you avoiding N+1 queries?
- [ ] Are you using bulk operations where possible?
- [ ] Are you limiting result sets with slicing?

## Best Practices Summary

1. **Always use select_related() and prefetch_related()** when accessing related objects
2. **Cache hierarchical data** that changes infrequently
3. **Use database aggregations** instead of Python calculations
4. **Create appropriate indexes** for frequently filtered fields
5. **Monitor query performance** in development and staging
6. **Use bulk operations** for creating/updating multiple objects
7. **Limit result sets** with filtering and slicing
8. **Avoid recursive CTEs** - use Python tree traversal instead

## Migration from Raw SQL

When migrating from raw SQL to Django ORM:

1. **Identify the query pattern** (filtering, aggregation, hierarchy, etc.)
2. **Use appropriate Django ORM methods** (filter, annotate, aggregate, etc.)
3. **Add necessary select_related/prefetch_related**
4. **Implement caching** for expensive queries
5. **Test performance** and compare with raw SQL
6. **Create indexes** if needed
7. **Document** any complex query logic

Remember: Simple Python code with proper caching often outperforms complex SQL!