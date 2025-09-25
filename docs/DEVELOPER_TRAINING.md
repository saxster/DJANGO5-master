# Django ORM Migration: Developer Training Guide

## Introduction

Welcome to the Django ORM migration training guide. This document will help you understand the new query system and how to use it effectively.

## Training Modules

### Module 1: Understanding the Migration

#### Why We Migrated
1. **Security**: Eliminate SQL injection risks
2. **Maintainability**: Easier to understand and modify
3. **Performance**: 2-3x improvement through optimization
4. **Consistency**: Standardized query patterns

#### Key Principle
> "Just because you CAN use advanced SQL doesn't mean you SHOULD"

The recursive CTEs we were using were solving simple problems with complex tools. Python tree traversal is simpler and faster.

### Module 2: Basic ORM Usage

#### 1. Simple Queries

**Old Way (Raw SQL):**
```python
cursor.execute("SELECT * FROM bt WHERE active = 1")
results = cursor.fetchall()
```

**New Way (Django ORM):**
```python
from apps.models import BT

results = BT.objects.filter(active=True)
```

#### 2. Queries with Joins

**Old Way:**
```python
cursor.execute("""
    SELECT b.*, p.name as parent_name 
    FROM bt b 
    LEFT JOIN bt p ON b.parent_id = p.id 
    WHERE b.active = 1
""")
```

**New Way:**
```python
results = BT.objects.filter(active=True).select_related('parent')

# Access parent without additional query
for item in results:
    print(f"{item.name} - Parent: {item.parent.name if item.parent else 'None'}")
```

#### 3. Aggregation Queries

**Old Way:**
```python
cursor.execute("""
    SELECT category, COUNT(*) as count 
    FROM tickets 
    WHERE status = 'open' 
    GROUP BY category
""")
```

**New Way:**
```python
from django.db.models import Count

results = Ticket.objects.filter(
    status='open'
).values('category').annotate(
    count=Count('id')
)
```

### Module 3: Advanced Patterns

#### 1. Tree Traversal

**Using TreeTraversal class:**
```python
from apps.core.queries import TreeTraversal

# Get all nodes
all_nodes = BT.objects.filter(active=True).values(
    'id', 'code', 'name', 'parent_id'
)

# Build tree structure
tree = TreeTraversal.build_tree(list(all_nodes), root_id=1)

# Result includes level information
for node in tree:
    print("  " * node['level'] + node['name'])
```

#### 2. Efficient Prefetching

**Avoid N+1 queries:**
```python
# Bad: N+1 queries
for ticket in Ticket.objects.all():
    print(ticket.assigned_to.username)  # Queries database each time

# Good: 2 queries total
tickets = Ticket.objects.select_related('assigned_to')
for ticket in tickets:
    print(ticket.assigned_to.username)  # No additional queries

# For reverse foreign keys
users = User.objects.prefetch_related('assigned_tickets')
for user in users:
    print(f"{user.username}: {user.assigned_tickets.count()} tickets")
```

#### 3. Query Optimization

**Use only() for specific fields:**
```python
# Load only necessary fields
users = User.objects.only('id', 'username', 'email')

# Defer expensive fields
articles = Article.objects.defer('content', 'full_text')
```

### Module 4: Caching Strategies

#### 1. Using Cache Decorators

```python
from apps.core.cache_manager import cache_decorator

@cache_decorator(timeout=3600, key_prefix='user_stats')
def get_user_statistics(user_id):
    return {
        'tickets': Ticket.objects.filter(user_id=user_id).count(),
        'resolved': Ticket.objects.filter(user_id=user_id, status='resolved').count(),
    }

# First call: hits database
stats = get_user_statistics(123)  # ~50ms

# Second call: from cache
stats = get_user_statistics(123)  # ~1ms
```

#### 2. Tree Cache Usage

```python
from apps.core.cache_manager import TreeCache

# Get cached tree (auto-caches on first call)
tree = TreeCache.get_full_tree(root_id=1)

# Invalidate when data changes
def update_bt_node(node_id, **kwargs):
    BT.objects.filter(id=node_id).update(**kwargs)
    TreeCache.invalidate_tree_cache(node_id)
```

### Module 5: Common Patterns

#### 1. Report Queries

```python
from apps.core.queries import ReportQueryRepository

# Get report data with all optimizations
data = ReportQueryRepository.get_attendance_summary(
    start_date='2024-01-01',
    end_date='2024-01-31'
)
```

#### 2. Search Queries

```python
from django.db.models import Q

# Complex search
results = Ticket.objects.filter(
    Q(title__icontains=search_term) |
    Q(description__icontains=search_term) |
    Q(assigned_to__username__icontains=search_term)
).select_related('assigned_to').distinct()
```

#### 3. Bulk Operations

```python
# Bulk create
tickets = [
    Ticket(title=f"Ticket {i}", status='open')
    for i in range(100)
]
Ticket.objects.bulk_create(tickets)

# Bulk update
Ticket.objects.filter(status='open', created__lt=cutoff_date).update(
    status='expired'
)
```

### Module 6: Monitoring & Performance

#### 1. Query Monitoring

```python
# Check query count in development
from django.db import connection

initial = len(connection.queries)
# Your code here
print(f"Queries executed: {len(connection.queries) - initial}")

# View actual SQL
queryset = Ticket.objects.filter(status='open')
print(queryset.query)
```

#### 2. Using Monitoring Endpoints

```bash
# Check current performance
curl http://localhost:8000/monitoring/performance/queries/

# View slow queries
curl http://localhost:8000/monitoring/performance/queries/?min_time=100
```

### Module 7: Hands-On Exercises

#### Exercise 1: Basic Queries
Convert this raw SQL to Django ORM:
```sql
SELECT * FROM users 
WHERE active = true 
  AND created_date >= '2024-01-01' 
ORDER BY username;
```

**Solution:**
```python
User.objects.filter(
    active=True,
    created_date__gte='2024-01-01'
).order_by('username')
```

#### Exercise 2: Joins and Aggregation
Convert this query:
```sql
SELECT d.name, COUNT(t.id) as ticket_count
FROM departments d
LEFT JOIN tickets t ON t.department_id = d.id
WHERE t.status = 'open'
GROUP BY d.id, d.name
HAVING COUNT(t.id) > 5;
```

**Solution:**
```python
from django.db.models import Count

Department.objects.annotate(
    ticket_count=Count('tickets', filter=Q(tickets__status='open'))
).filter(ticket_count__gt=5).values('name', 'ticket_count')
```

#### Exercise 3: Tree Operations
Write a function to get all descendants of a node:

**Solution:**
```python
def get_all_descendants(node_id):
    from apps.core.queries import TreeTraversal
    
    # Get all nodes
    all_nodes = BT.objects.filter(active=True).values()
    
    # Build tree starting from our node
    tree = TreeTraversal.build_tree(list(all_nodes), root_id=node_id)
    
    # Remove the root node itself
    return tree[1:] if tree else []
```

### Module 8: Best Practices Checklist

#### Before Writing a Query:
- [ ] Can I use an existing query from `queries.py`?
- [ ] Do I need all fields or can I use `only()`?
- [ ] Will this cause N+1 queries?
- [ ] Should this be cached?

#### Query Checklist:
- [ ] Used `select_related()` for foreign keys
- [ ] Used `prefetch_related()` for reverse foreign keys
- [ ] Limited fields with `only()` or `defer()`
- [ ] Added appropriate filters early
- [ ] Considered adding an index

#### After Writing a Query:
- [ ] Checked the generated SQL
- [ ] Tested performance with real data
- [ ] Added caching if appropriate
- [ ] Documented complex queries

### Module 9: Common Mistakes to Avoid

#### 1. N+1 Queries
```python
# ❌ Bad
for user in User.objects.all():
    print(user.profile.bio)  # Hits DB each time

# ✅ Good
for user in User.objects.select_related('profile'):
    print(user.profile.bio)  # Single query
```

#### 2. Loading Unnecessary Data
```python
# ❌ Bad
users = User.objects.all()  # Loads all fields
for user in users:
    print(user.username)

# ✅ Good
users = User.objects.only('username')
for user in users:
    print(user.username)
```

#### 3. Inefficient Filtering
```python
# ❌ Bad
all_tickets = Ticket.objects.all()
open_tickets = [t for t in all_tickets if t.status == 'open']

# ✅ Good
open_tickets = Ticket.objects.filter(status='open')
```

#### 4. Not Using Bulk Operations
```python
# ❌ Bad
for data in ticket_data:
    Ticket.objects.create(**data)  # Multiple queries

# ✅ Good
tickets = [Ticket(**data) for data in ticket_data]
Ticket.objects.bulk_create(tickets)  # Single query
```

### Module 10: Resources and Help

#### Documentation
- [Django ORM Migration Guide](/docs/DJANGO_ORM_MIGRATION_GUIDE.md)
- [Django QuerySet API](https://docs.djangoproject.com/en/5.0/ref/models/querysets/)
- [Query Optimization Guide](https://docs.djangoproject.com/en/5.0/topics/db/optimization/)

#### Getting Help
1. Check existing queries in `apps/core/queries.py`
2. Use monitoring to identify slow queries
3. Ask in #dev-help Slack channel
4. Review query performance in monitoring dashboard

#### Quick Reference
```python
# Import commonly used items
from apps.core.queries import (
    TreeTraversal,
    QueryRepository, 
    ReportQueryRepository
)
from apps.core.cache_manager import cache_decorator, TreeCache
from django.db.models import Count, Sum, Avg, Q, F

# Common patterns
Model.objects.filter(active=True)
Model.objects.select_related('foreign_key')
Model.objects.prefetch_related('reverse_foreign_key')
Model.objects.only('field1', 'field2')
Model.objects.annotate(total=Count('related'))
Model.objects.aggregate(total=Sum('amount'))
```

### Assessment Questions

1. What's the main advantage of using `select_related()`?
2. When should you use `prefetch_related()` instead of `select_related()`?
3. How do you check if your query is causing N+1 problems?
4. What's the performance difference between cached and uncached tree queries?
5. When should you NOT use caching?

### Next Steps

1. Review the codebase examples in `apps/core/queries.py`
2. Practice converting raw SQL queries to ORM
3. Monitor your queries using the dashboard
4. Optimize queries showing in slow query log
5. Share your learnings with the team

Remember: The goal is not just to replace SQL with ORM, but to write efficient, maintainable queries that perform better than the original implementation.