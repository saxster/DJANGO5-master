# Best Practices: Database Query Optimization

**ID:** BP-PERF-001  
**Category:** Performance Best Practices  
**Difficulty:** Intermediate  
**Last Updated:** November 6, 2025

---

## Overview

Efficient database queries are critical for application performance. Poorly optimized queries cause slow page loads, high CPU usage, and poor user experience.

**Key Principle:** Minimize database queries and transfer only necessary data.

---

## Decision Tree: Choose Optimization Strategy

```mermaid
graph TD
    A[Database Query] --> B{Related objects?}
    
    B -->|No| C[Use .only() or .values()]
    B -->|Yes| D{Relationship type?}
    
    D -->|ForeignKey<br/>OneToOne| E[select_related]
    D -->|ManyToMany<br/>Reverse ForeignKey| F[prefetch_related]
    
    E --> G{Need all fields?}
    F --> H{Need all fields?}
    
    G -->|No| I[select_related + only]
    G -->|Yes| J[select_related]
    
    H -->|No| K[Prefetch + queryset]
    H -->|Yes| L[prefetch_related]
    
    C --> M[Optimized Query]
    I --> M
    J --> M
    K --> M
    L --> M
```

---

## Pattern 1: select_related (Forward Relationships)

### When to Use
- **ForeignKey** relationships
- **OneToOne** relationships
- Accessing related object in loop
- Need to JOIN tables

### ❌ Anti-Pattern: N+1 Query Problem

```python
# ❌ GENERATES N+1 QUERIES
tasks = Task.objects.all()  # 1 query
for task in tasks:
    print(task.site.name)  # N queries (1 per task)
    print(task.created_by.username)  # N more queries
```

**Performance Impact:**
```
Query 1: SELECT * FROM tasks (50 tasks)
Query 2: SELECT * FROM sites WHERE id=1
Query 3: SELECT * FROM sites WHERE id=2
...
Query 51: SELECT * FROM sites WHERE id=50
Query 52: SELECT * FROM users WHERE id=1
...
Query 102: SELECT * FROM users WHERE id=50

Total: 102 queries for 50 tasks ⚠️
```

### ✅ Required Pattern

```python
# ✅ GENERATES 1 QUERY with JOIN
tasks = Task.objects.select_related('site', 'created_by').all()
for task in tasks:
    print(task.site.name)  # No query - already loaded
    print(task.created_by.username)  # No query - already loaded
```

**SQL Generated:**
```sql
SELECT tasks.*, sites.*, users.*
FROM tasks
INNER JOIN sites ON tasks.site_id = sites.id
INNER JOIN users ON tasks.created_by_id = users.id
```

**Performance:**
- **Queries:** 1 (vs 102)
- **Speed:** 50x faster
- **Database load:** 98% reduction

---

## Pattern 2: prefetch_related (Reverse/M2M Relationships)

### When to Use
- **ManyToMany** relationships
- **Reverse ForeignKey** (e.g., `user.tasks.all()`)
- Cannot use JOIN (separate queries more efficient)

### ❌ Anti-Pattern

```python
# ❌ N+1 QUERIES
users = People.objects.all()  # 1 query
for user in users:
    tasks = user.tasks.all()  # N queries
    print(f"{user.username}: {tasks.count()} tasks")
```

### ✅ Required Pattern

```python
# ✅ 2 QUERIES TOTAL
users = People.objects.prefetch_related('tasks').all()
for user in users:
    tasks = user.tasks.all()  # No query - cached
    print(f"{user.username}: {tasks.count()} tasks")
```

**SQL Generated:**
```sql
-- Query 1: Get users
SELECT * FROM users

-- Query 2: Get all related tasks
SELECT * FROM tasks WHERE assigned_to_id IN (1, 2, 3, ...)
```

---

## Pattern 3: Combining Optimizations

```python
# ✅ OPTIMAL: Combine select_related + prefetch_related
tasks = Task.objects.select_related(
    'site',           # ForeignKey
    'created_by'      # ForeignKey
).prefetch_related(
    'assigned_people',  # ManyToMany
    'attachments'       # Reverse ForeignKey
).filter(
    status='ACTIVE'
).only(
    'id', 'title', 'status',  # Only needed fields
    'site__name',              # Related field
    'created_by__username'
)
```

**Queries Generated:** 3 total
1. Tasks with sites and users (JOIN)
2. Assigned people (separate query)
3. Attachments (separate query)

---

## Pattern 4: Custom Prefetch for Filtered Related Objects

```python
from django.db.models import Prefetch

# ✅ Prefetch only active attachments
tasks = Task.objects.prefetch_related(
    Prefetch(
        'attachments',
        queryset=Attachment.objects.filter(is_active=True).select_related('uploaded_by'),
        to_attr='active_attachments'
    )
).all()

for task in tasks:
    # Use custom attribute
    for attachment in task.active_attachments:
        print(attachment.filename)
```

---

## Pattern 5: Custom Manager Methods

```python
# apps/activity/managers.py

from django.db import models

class TaskQuerySet(models.QuerySet):
    """Optimized queries for common patterns."""
    
    def with_full_details(self):
        """Load all related data for detail view."""
        return self.select_related(
            'site',
            'created_by',
            'updated_by'
        ).prefetch_related(
            'assigned_people__profile',
            'attachments',
            'comments__author'
        )
    
    def with_list_details(self):
        """Minimal data for list view."""
        return self.select_related(
            'site',
            'created_by'
        ).only(
            'id', 'title', 'status', 'priority', 'due_date',
            'site__name',
            'created_by__username'
        )

class TaskManager(models.Manager):
    def get_queryset(self):
        return TaskQuerySet(self.model, using=self._db)
    
    def with_full_details(self):
        return self.get_queryset().with_full_details()
    
    def with_list_details(self):
        return self.get_queryset().with_list_details()

# Usage in views
def task_detail(request, task_id):
    task = Task.objects.with_full_details().get(id=task_id)
    return render(request, 'task_detail.html', {'task': task})

def task_list(request):
    tasks = Task.objects.with_list_details().filter(status='ACTIVE')
    return render(request, 'task_list.html', {'tasks': tasks})
```

---

## Pattern 6: Annotation for Aggregates

```python
from django.db.models import Count, Avg, Q

# ✅ Compute aggregates in database, not Python
tasks = Task.objects.annotate(
    comment_count=Count('comments'),
    active_comment_count=Count('comments', filter=Q(comments__is_active=True)),
    avg_rating=Avg('ratings__score')
).select_related('site')

for task in tasks:
    # No additional queries
    print(f"{task.title}: {task.comment_count} comments, {task.avg_rating} rating")
```

---

## Measuring Query Performance

### Enable Query Logging

```python
# settings/development.py

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
            'level': 'DEBUG',  # Shows all SQL queries
        },
    },
}
```

### Use Django Debug Toolbar

```python
# Shows query count and duplicates
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
```

### Assert Query Count in Tests

```python
from django.test import TestCase
from django.test.utils import override_settings

class QueryOptimizationTests(TestCase):
    """Verify query counts don't regress."""
    
    def test_task_list_query_count(self):
        """Task list should use exactly 2 queries."""
        # Create test data
        for i in range(10):
            Task.objects.create(title=f'Task {i}')
        
        # Assert query count
        with self.assertNumQueries(2):  # Enforce query limit
            tasks = Task.objects.with_list_details().all()
            list(tasks)  # Force evaluation
```

---

## Common Mistakes

### Mistake 1: Prefetch Inside Loop

```python
# ❌ WRONG: Optimization inside loop does nothing
for user in People.objects.all():
    tasks = user.tasks.prefetch_related('attachments').all()  # Too late!
```

**Fix:** Apply optimization to initial queryset.

### Mistake 2: Over-fetching Data

```python
# ❌ WRONG: Fetch all fields when only need title
tasks = Task.objects.select_related('site', 'created_by').all()
return [task.title for task in tasks]  # Transferred unnecessary data
```

**Fix:** Use `.only()` or `.values()`.

```python
# ✅ CORRECT
tasks = Task.objects.only('title').all()
return [task.title for task in tasks]
```

### Mistake 3: Not Testing Query Count

```python
# ❌ WRONG: No query validation
def get_tasks(request):
    return Task.objects.all()  # Could be N+1 problem
```

**Fix:** Write tests with `assertNumQueries`.

---

## Performance Checklist

- [ ] **All list views use `select_related` for ForeignKeys**
- [ ] **All list views use `prefetch_related` for M2M/reverse FK**
- [ ] **Custom manager methods for common patterns**
- [ ] **`.only()` used when fetching subset of fields**
- [ ] **Aggregates computed in database, not Python loops**
- [ ] **Query count assertions in tests**
- [ ] **Django Debug Toolbar enabled in development**
- [ ] **No queries inside loops**

---

## References

- **[Query Optimization Architecture](../../docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md)** - Complete guide
- **[N+1 Fixes Summary](../../N_PLUS_ONE_FIXES_SUMMARY.md)** - All fixes implemented
- **[BP-PERF-002: N+1 Prevention](BP-PERF-002-N1-Prevention.md)** - Detailed N+1 guide
- **[Performance Analytics](../../PERFORMANCE_ANALYTICS_IMPLEMENTATION_COMPLETE.md)** - Monitoring

---

**Questions?** Submit a Help Desk ticket with tag `best-practices-performance`
