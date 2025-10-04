# Raw SQL to Django ORM Migration Guide

**Purpose:** Comprehensive guide for migrating raw SQL queries to Django ORM patterns
**Target Audience:** Backend developers working on Django 5 enterprise platform
**Difficulty:** Intermediate to Advanced
**Estimated Time:** 2-4 hours to master patterns

---

## 📋 Table of Contents

1. [Why Migrate to ORM](#why-migrate-to-orm)
2. [When to Keep Raw SQL](#when-to-keep-raw-sql)
3. [Migration Patterns by Category](#migration-patterns-by-category)
4. [Real-World Examples from Codebase](#real-world-examples)
5. [Performance Optimization Techniques](#performance-optimization)
6. [Testing Migrated Queries](#testing-strategies)
7. [Common Pitfalls and Solutions](#common-pitfalls)

---

## 🎯 Why Migrate to ORM

### Benefits

**1. Security**
- ✅ **Automatic SQL injection prevention** via parameterization
- ✅ **Type safety** - Python type hints enforced
- ✅ **No string concatenation** vulnerabilities

**2. Maintainability**
- ✅ **Readable code** - Python syntax vs. SQL strings
- ✅ **IDE support** - Autocomplete, refactoring, go-to-definition
- ✅ **Version control friendly** - Better diffs

**3. Database Portability**
- ✅ **Database-agnostic** - Works with PostgreSQL, MySQL, SQLite
- ✅ **Automatic schema migrations** via Django migrations
- ✅ **Consistent behavior** across database backends

**4. Django Integration**
- ✅ **Works with signals** - pre_save, post_save hooks
- ✅ **Queryset chaining** - Composable queries
- ✅ **Built-in pagination** and caching

### Drawbacks

**When ORM is Slower:**
- ❌ Complex aggregations with multiple CTEs
- ❌ Window functions (though Django 4.2+ supports them)
- ❌ Recursive queries (though django-cte library helps)
- ❌ PostgreSQL-specific features (pgvector, full-text search)

**Our Approach:** Use ORM for 80% of queries, keep raw SQL for the remaining 20% with proper wrappers.

---

## 🚫 When to Keep Raw SQL

**Keep raw SQL for:**

1. **PostgreSQL-Specific Features**
   - pgvector semantic search
   - PostGIS spatial functions (though GeoDjango helps)
   - Advisory locks (`pg_try_advisory_lock`)
   - Custom extensions

2. **Performance-Critical Queries**
   - Queries with >5 table joins
   - Recursive CTEs (Common Table Expressions)
   - Queries optimized with specific indexes

3. **System Monitoring**
   - `pg_stat_statements` queries
   - Database health checks
   - Performance analytics

4. **Legacy Stored Procedures**
   - Complex business logic in database
   - Stored functions called by triggers
   - When rewriting in Python would be risky

**Rule of Thumb:** If query is >100 lines or uses 3+ CTEs, evaluate cost/benefit of migration.

---

## 📊 Migration Patterns by Category

### Pattern 1: Simple SELECT with WHERE

**❌ Raw SQL:**
```python
from django.db import connection

def get_active_users(client_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, email, peoplename, cdtz
            FROM people
            WHERE client_id = %s AND enable = TRUE
            ORDER BY cdtz DESC
        """, [client_id])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

**✅ Django ORM:**
```python
from apps.peoples.models import People

def get_active_users(client_id):
    return People.objects.filter(
        client_id=client_id,
        enable=True
    ).values(
        'id', 'email', 'peoplename', 'cdtz'
    ).order_by('-cdtz')
```

**Benefits:**
- 50% fewer lines of code
- Type-safe (People model enforces schema)
- Returns queryset (can chain additional filters)
- Automatic SQL injection prevention

**Performance:** ⚡ Identical (both generate same SQL)

---

### Pattern 2: JOIN with Related Tables

**❌ Raw SQL:**
```python
def get_users_with_bu(client_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.peoplename, p.email,
                   b.buname, b.bucode
            FROM people p
            INNER JOIN bt b ON p.bu_id = b.id
            WHERE p.client_id = %s
        """, [client_id])
        return cursor.fetchall()
```

**✅ Django ORM:**
```python
def get_users_with_bu(client_id):
    return People.objects.filter(
        client_id=client_id
    ).select_related(
        'bu'  # Efficient JOIN instead of N+1 queries
    ).values(
        'id', 'peoplename', 'email',
        'bu__buname', 'bu__bucode'  # Double underscore for related fields
    )
```

**Key Concepts:**
- `select_related()` for ForeignKey/OneToOne (SQL JOIN)
- `prefetch_related()` for ManyToMany/Reverse FK (separate queries)
- Double underscore `__` traverses relationships

**Performance:** ⚡ **ORM is faster** (one query vs. potential N+1)

---

### Pattern 3: Aggregation (COUNT, SUM, AVG)

**❌ Raw SQL:**
```python
def get_client_stats(client_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) as total_users,
                COUNT(CASE WHEN enable = TRUE THEN 1 END) as active_users,
                COUNT(CASE WHEN isadmin = TRUE THEN 1 END) as admins
            FROM people
            WHERE client_id = %s
        """, [client_id])
        return cursor.fetchone()
```

**✅ Django ORM:**
```python
from django.db.models import Count, Q

def get_client_stats(client_id):
    return People.objects.filter(
        client_id=client_id
    ).aggregate(
        total_users=Count('id'),
        active_users=Count('id', filter=Q(enable=True)),
        admins=Count('id', filter=Q(isadmin=True))
    )
    # Returns: {'total_users': 150, 'active_users': 120, 'admins': 5}
```

**Key Concepts:**
- `aggregate()` for single-row results (dict)
- `annotate()` for per-row aggregations (queryset)
- `filter=Q(...)` for conditional aggregation (Django 2.0+)

**Performance:** ⚡ Identical

---

### Pattern 4: Subqueries

**❌ Raw SQL:**
```python
def get_users_with_recent_attendance(days=7):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.peoplename,
                   (SELECT COUNT(*) FROM peopleeventlog
                    WHERE people_id = p.id
                    AND datefor >= CURRENT_DATE - INTERVAL '%s days') as attendance_count
            FROM people p
            WHERE p.enable = TRUE
        """, [days])
        return cursor.fetchall()
```

**✅ Django ORM:**
```python
from django.db.models import Count, Q, OuterRef, Subquery
from datetime import date, timedelta

def get_users_with_recent_attendance(days=7):
    cutoff_date = date.today() - timedelta(days=days)

    return People.objects.filter(
        enable=True
    ).annotate(
        attendance_count=Count(
            'peopleeventlog',
            filter=Q(peopleeventlog__datefor__gte=cutoff_date)
        )
    ).values('id', 'peoplename', 'attendance_count')
```

**Alternative (Explicit Subquery):**
```python
from django.db.models import Subquery, OuterRef

attendance_subquery = PeopleEventlog.objects.filter(
    people_id=OuterRef('pk'),
    datefor__gte=cutoff_date
).values('people_id').annotate(
    count=Count('id')
).values('count')

return People.objects.filter(enable=True).annotate(
    attendance_count=Subquery(attendance_subquery)
).values('id', 'peoplename', 'attendance_count')
```

**Key Concepts:**
- `OuterRef('pk')` references outer query
- `Subquery()` for explicit subqueries
- `annotate()` adds computed fields

---

### Pattern 5: Common Table Expressions (CTEs)

**❌ Raw SQL:**
```python
def get_hierarchical_bu(root_bu_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH RECURSIVE bu_tree AS (
                SELECT id, buname, parent_id, 1 AS depth
                FROM bt
                WHERE id = %s
                UNION ALL
                SELECT b.id, b.buname, b.parent_id, bt.depth + 1
                FROM bt b
                INNER JOIN bu_tree bt ON b.parent_id = bt.id
            )
            SELECT * FROM bu_tree ORDER BY depth
        """, [root_bu_id])
        return cursor.fetchall()
```

**✅ Django ORM (using django-cte):**
```python
from django_cte import With
from apps.onboarding.models import Bt

def get_hierarchical_bu(root_bu_id):
    # Define base case
    cte = With.recursive(lambda cte:
        Bt.objects.filter(id=root_bu_id).annotate(
            depth=Value(1)
        ).union(
            cte.join(Bt, parent_id=cte.col.id).annotate(
                depth=cte.col.depth + Value(1)
            )
        )
    )

    return cte.queryset().with_cte(cte).order_by('depth')
```

**Installation:**
```bash
pip install django-cte
```

**Key Concepts:**
- `django-cte` library for recursive CTEs
- `With.recursive()` for recursive definitions
- Still complex - keep raw SQL for very complex CTEs

**Performance:** ⚡ Similar, but django-cte adds abstraction overhead

**Recommendation:** For hierarchical queries, consider using `django-mptt` or `django-treebeard` libraries instead of recursive CTEs.

---

### Pattern 6: Window Functions (Django 4.2+)

**❌ Raw SQL:**
```python
def get_ranked_attendance(client_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                people_id,
                datefor,
                distance,
                ROW_NUMBER() OVER (PARTITION BY people_id ORDER BY datefor DESC) as rn
            FROM peopleeventlog
            WHERE client_id = %s
        """, [client_id])
        return cursor.fetchall()
```

**✅ Django ORM (Django 4.2+):**
```python
from django.db.models import Window, F, RowNumber
from django.db.models.functions import PartitionBy

def get_ranked_attendance(client_id):
    return PeopleEventlog.objects.filter(
        client_id=client_id
    ).annotate(
        rn=Window(
            expression=RowNumber(),
            partition_by=[F('people_id')],
            order_by=F('datefor').desc()
        )
    ).values('people_id', 'datefor', 'distance', 'rn')
```

**Supported Window Functions:**
- `RowNumber()`, `Rank()`, `DenseRank()`
- `FirstValue()`, `LastValue()`, `Lag()`, `Lead()`
- `Ntile()`, `PercentRank()`, `CumeDist()`

**Performance:** ⚡ Identical

---

## 🔧 Real-World Examples from Codebase

### Example 1: Migrate `get_schedule_task_for_adhoc`

**Location:** `apps/activity/managers/asset_manager.py:66-67`

**Current (Raw SQL):**
```python
def get_schedule_task_for_adhoc(self, params):
    qset = self.raw("select * from fn_get_schedule_for_adhoc")
```

**Migrated (ORM with Stored Function Wrapper):**
```python
from apps.core.db import execute_stored_function

def get_schedule_task_for_adhoc(self, params):
    result = execute_stored_function(
        'fn_get_schedule_for_adhoc',
        params=[
            params['plandatetime'],
            params['buid'],
            params['peopleid'],
            params['assetid'],
            params['questionsetid']
        ],
        return_type='TABLE'
    )

    if not result.success:
        logger.error(f"Stored function failed: {result.errors}")
        return self.none()

    # Convert QueryResult to queryset-like structure
    return result.data
```

**Benefits:**
- ✅ Type-safe parameter handling
- ✅ Error handling and logging
- ✅ Transaction safety
- ✅ Tenant routing support

**Performance:** ⚡ Identical (still calls stored function)

---

### Example 2: Migrate Ticket Escalation Query

**Location:** `apps/core/raw_queries.py` - `get_ticketlist_for_escalation`

**Current (99 lines of complex CTE):**
```sql
SELECT DISTINCT *,
    ticket.cdtz + INTERVAL '1 minute' * esclation.calcminute as exp_time
FROM
    (SELECT ticket.id, ticket.ticketno, ...
     FROM ticket
     WHERE NOT (status IN ('CLOSE', 'CANCEL'))) AS ticket,
    (SELECT escalationmatrix.id, ...
     FROM escalationmatrix ...) AS esclation
WHERE (ticket.level+1) = esclation.eslevel
```

**Migrated (Django ORM):**
```python
from django.db.models import F, Q, Case, When, Value, ExpressionWrapper
from django.db.models.functions import Cast
from datetime import timedelta

def get_ticketlist_for_escalation():
    # Annotate tickets with calculated escalation times
    tickets = Ticket.objects.filter(
        ~Q(status__in=['CLOSE', 'CANCEL'])
    ).select_related(
        'assignedtopeople',
        'assignedtogroup',
        'cuser'
    ).annotate(
        # Calculate escalation minutes based on frequency
        escalation_minutes=Case(
            When(
                ticketcategory__escalationmatrix__frequency='MINUTE',
                then=F('ticketcategory__escalationmatrix__frequencyvalue')
            ),
            When(
                ticketcategory__escalationmatrix__frequency='HOUR',
                then=F('ticketcategory__escalationmatrix__frequencyvalue') * 60
            ),
            When(
                ticketcategory__escalationmatrix__frequency='DAY',
                then=F('ticketcategory__escalationmatrix__frequencyvalue') * 24 * 60
            ),
            When(
                ticketcategory__escalationmatrix__frequency='WEEK',
                then=F('ticketcategory__escalationmatrix__frequencyvalue') * 7 * 24 * 60
            ),
            default=Value(0),
            output_field=models.IntegerField()
        ),
        # Calculate expiration time
        exp_time=ExpressionWrapper(
            F('cdtz') + timedelta(minutes=1) * F('escalation_minutes'),
            output_field=models.DateTimeField()
        )
    ).filter(
        # Join condition: next escalation level matches
        ticketcategory__escalationmatrix__level=F('level') + 1,
        # Check if escalation time has passed
        exp_time__lt=timezone.now()
    )

    return tickets.values(
        'id', 'ticketno', 'ticketdesc', 'comments',
        'cdtz', 'mdtz', 'status', 'level',
        'assignedtopeople__peoplename',
        'assignedtogroup__groupname',
        'exp_time'
    )
```

**Benefits:**
- ✅ Type-safe with model definitions
- ✅ Readable Python code (vs. 99 lines of SQL)
- ✅ Works with Django signals
- ✅ Easier to test

**Drawbacks:**
- ⚠️ May be slower (complex query)
- ⚠️ Requires careful index optimization

**Recommendation:** Benchmark both versions. If ORM is >20% slower, keep raw SQL with new wrapper.

---

## ⚡ Performance Optimization Techniques

### 1. Use `select_related()` and `prefetch_related()`

**❌ Bad (N+1 queries):**
```python
users = People.objects.filter(client_id=1)
for user in users:
    print(user.bu.buname)  # Each iteration hits database!
```

**✅ Good (Single JOIN):**
```python
users = People.objects.filter(client_id=1).select_related('bu')
for user in users:
    print(user.bu.buname)  # Already loaded in memory
```

**Result:** 1 query instead of N+1 queries.

---

### 2. Use `only()` and `defer()` to Load Specific Fields

**❌ Bad (loads all fields):**
```python
users = People.objects.all()  # Loads 30+ fields per user
```

**✅ Good (only needed fields):**
```python
users = People.objects.only('id', 'email', 'peoplename')
# Or exclude heavy fields:
users = People.objects.defer('people_extras', 'mobilecapability')
```

**Result:** Reduces memory usage and transfer time.

---

### 3. Use `iterator()` for Large Querysets

**❌ Bad (loads all 100K rows into memory):**
```python
for user in People.objects.all():
    process_user(user)
```

**✅ Good (streams rows):**
```python
for user in People.objects.all().iterator(chunk_size=1000):
    process_user(user)
```

**Result:** Constant memory usage regardless of dataset size.

---

### 4. Use `bulk_create()` for Batch Inserts

**❌ Bad (1000 queries):**
```python
for data in user_data:
    People.objects.create(**data)
```

**✅ Good (1 query):**
```python
People.objects.bulk_create([
    People(**data) for data in user_data
], batch_size=1000)
```

**Result:** 100-1000x faster for bulk inserts.

---

### 5. Use Database Indexes

**Check Current Indexes:**
```python
# In Django shell
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'people'
    """)
    for row in cursor.fetchall():
        print(row)
```

**Add Index in Model:**
```python
class People(models.Model):
    email = models.EmailField()
    client_id = models.BigIntegerField(db_index=True)  # Add index

    class Meta:
        indexes = [
            models.Index(fields=['client_id', 'enable']),  # Composite index
            models.Index(fields=['-cdtz']),  # Descending index
        ]
```

---

## 🧪 Testing Migrated Queries

### Strategy 1: Compare Results

```python
# tests/test_orm_migration.py
import pytest
from django.db import connection
from apps.peoples.models import People

def test_get_active_users_migration():
    """Compare raw SQL vs ORM results"""
    client_id = 1

    # Raw SQL (old way)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, email FROM people
            WHERE client_id = %s AND enable = TRUE
            ORDER BY id
        """, [client_id])
        raw_results = cursor.fetchall()

    # ORM (new way)
    orm_results = list(
        People.objects.filter(
            client_id=client_id, enable=True
        ).values_list('id', 'email').order_by('id')
    )

    # Compare
    assert raw_results == orm_results, "Results don't match!"
```

---

### Strategy 2: Benchmark Performance

```python
import time
from django.test import TestCase

class QueryPerformanceTest(TestCase):
    def test_query_performance(self):
        """Ensure ORM query is not >20% slower"""

        # Warm up database
        People.objects.count()

        # Benchmark raw SQL
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM people WHERE client_id = 1")
            cursor.fetchall()
        raw_time = time.time() - start

        # Benchmark ORM
        start = time.time()
        list(People.objects.filter(client_id=1))
        orm_time = time.time() - start

        # Assert ORM is not significantly slower
        slowdown_pct = ((orm_time - raw_time) / raw_time) * 100
        assert slowdown_pct < 20, f"ORM is {slowdown_pct:.1f}% slower!"

        print(f"Raw SQL: {raw_time:.3f}s, ORM: {orm_time:.3f}s")
```

---

### Strategy 3: Use Django Debug Toolbar

```python
# settings/development.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# Shows:
# - Number of queries
# - Query execution time
# - Duplicated queries (N+1 problem)
# - Query EXPLAIN plans
```

---

## 🚨 Common Pitfalls and Solutions

### Pitfall 1: N+1 Query Problem

**Symptom:** 1 query becomes 1000+ queries
```python
users = People.objects.all()
for user in users:
    print(user.bu.buname)  # 1000 queries if 1000 users!
```

**Solution:** Use `select_related()`
```python
users = People.objects.all().select_related('bu')
for user in users:
    print(user.bu.buname)  # Still just 1 query!
```

---

### Pitfall 2: Forgetting Timezone Awareness

**Problem:**
```python
from datetime import datetime
# ❌ Naive datetime (no timezone)
cutoff = datetime(2025, 1, 1)
People.objects.filter(cdtz__gte=cutoff)  # RuntimeWarning!
```

**Solution:**
```python
from django.utils import timezone
# ✅ Timezone-aware
cutoff = timezone.make_aware(datetime(2025, 1, 1))
People.objects.filter(cdtz__gte=cutoff)
```

---

### Pitfall 3: Misunderstanding `values()` vs `values_list()`

```python
# values() returns list of dicts
People.objects.values('id', 'email')
# [{'id': 1, 'email': 'user@example.com'}, ...]

# values_list() returns list of tuples
People.objects.values_list('id', 'email')
# [(1, 'user@example.com'), ...]

# values_list(flat=True) for single field
People.objects.values_list('id', flat=True)
# [1, 2, 3, 4, ...]
```

---

### Pitfall 4: Using `len()` Instead of `count()`

**❌ Bad (fetches all rows):**
```python
users = People.objects.filter(client_id=1)
total = len(users)  # Loads all users into memory!
```

**✅ Good (COUNT query):**
```python
total = People.objects.filter(client_id=1).count()
```

---

### Pitfall 5: Modifying QuerySet in Loop

**❌ Bad:**
```python
users = People.objects.filter(enable=True)
for user in users:
    user.enable = False
    user.save()  # 1000 UPDATE queries!
```

**✅ Good:**
```python
People.objects.filter(enable=True).update(enable=False)  # 1 UPDATE query!
```

---

## 📚 Additional Resources

### Documentation
- [Django QuerySet API](https://docs.djangoproject.com/en/5.0/ref/models/querysets/)
- [Django Aggregation](https://docs.djangoproject.com/en/5.0/topics/db/aggregation/)
- [Django Window Functions](https://docs.djangoproject.com/en/5.0/ref/models/database-functions/#window-functions)

### Libraries
- `django-cte` - Common Table Expressions support
- `django-query-inspector` - Analyze query performance
- `django-silk` - Live profiling and inspection

### Internal Docs
- `RAW_SQL_SECURITY_AUDIT_REPORT.md` - Current raw SQL usage
- `apps/core/db/raw_query_utils.py` - Secure wrappers for raw SQL
- `CLAUDE.md` - Database strategy and architecture

---

## ✅ Migration Checklist

**For Each Raw SQL Query:**

1. **Assess Complexity**
   - [ ] Simple SELECT → Migrate to ORM
   - [ ] Complex JOINs (3+) → Evaluate performance
   - [ ] Recursive CTEs → Use django-cte or keep raw SQL
   - [ ] PostgreSQL-specific → Keep raw SQL with wrapper

2. **Write ORM Equivalent**
   - [ ] Write ORM query
   - [ ] Test results match raw SQL
   - [ ] Benchmark performance (<20% slowdown acceptable)

3. **Add Tests**
   - [ ] Unit test with mocked data
   - [ ] Integration test comparing results
   - [ ] Performance test (optional for critical queries)

4. **Update Documentation**
   - [ ] Add docstring explaining query logic
   - [ ] Update `RAW_SQL_SECURITY_AUDIT_REPORT.md`
   - [ ] Document any performance considerations

5. **Deploy Safely**
   - [ ] Deploy to staging first
   - [ ] Monitor query performance
   - [ ] Keep raw SQL commented out for quick rollback

---

## 🎯 Summary

**Golden Rules:**
1. ✅ **Use ORM by default** - More secure, maintainable
2. ⚠️ **Keep raw SQL for**: PostgreSQL-specific features, complex CTEs, performance-critical queries
3. 🔒 **Always use secure wrappers** from `apps/core/db` for raw SQL
4. ⚡ **Benchmark before migrating** - Don't sacrifice >20% performance
5. 🧪 **Test thoroughly** - Ensure results match exactly

**Migration Priority:**
1. **High**: Simple SELECT/INSERT/UPDATE queries
2. **Medium**: Queries with 1-2 JOINs
3. **Low**: Complex aggregations, CTEs
4. **Keep Raw**: PostgreSQL extensions, stored procedures

---

**Next Steps:** Start with high-priority migrations. Track progress in `RAW_SQL_SECURITY_AUDIT_REPORT.md`.

**Questions?** Consult this guide or review Django's excellent documentation.