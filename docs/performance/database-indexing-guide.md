# Database Indexing Strategy Guide

**Purpose:** Comprehensive guide for database index strategy and optimization
**Addresses:** Issue #18 - Missing Database Indexes
**Compliance:** .claude/rules.md Rule #12 (Database Query Optimization)

---

## 🎯 Overview

This guide provides standards for database indexing in the Django 5 enterprise platform. Proper indexing is critical for performance at scale, reducing query times by 50-80%.

### Key Principles

1. **Index frequently filtered fields** - Status, priority, dates
2. **Use composite indexes** for common query combinations
3. **Leverage PostgreSQL-specific indexes** - GIN, BRIN, GIST
4. **Monitor index usage** - Remove unused indexes
5. **Balance write vs read performance** - Indexes slow writes

---

## 📊 Index Types and When to Use Them

### B-Tree Index (Default)

**Use for:**
- Equality comparisons (`WHERE status = 'NEW'`)
- Range queries (`WHERE date BETWEEN x AND y`)
- Sorting (`ORDER BY created_at`)
- LIKE queries with prefix (`WHERE name LIKE 'John%'`)

**Example:**
```python
class Ticket(models.Model):
    status = models.CharField(max_length=50, db_index=True)
    priority = models.CharField(max_length=50, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'priority']),
        ]
```

**Performance:** O(log n) lookup, excellent for most queries

---

### GIN Index (Generalized Inverted Index)

**Use for:**
- JSON field containment queries
- Full-text search
- Array containment
- JSONB path queries

**Example:**
```python
from django.contrib.postgres.indexes import GinIndex

class Ticket(models.Model):
    ticketlog = models.JSONField(default=dict)

    class Meta:
        indexes = [
            GinIndex(fields=['ticketlog'], name='ticket_log_gin_idx'),
        ]
```

**Query patterns:**
```python
Ticket.objects.filter(ticketlog__has_key='ticket_history')
Ticket.objects.filter(ticketlog__ticket_history__contains=[{'status': 'NEW'}])
```

**Performance:** Fast containment checks, slower updates

---

### BRIN Index (Block Range Index)

**Use for:**
- Time-series data (timestamps, dates)
- Monotonically increasing values
- Large tables with natural ordering
- Data with high correlation to physical storage order

**Example:**
```python
from django.contrib.postgres.indexes import BrinIndex

class PeopleEventlog(models.Model):
    punchintime = models.DateTimeField()
    punchouttime = models.DateTimeField()

    class Meta:
        indexes = [
            BrinIndex(fields=['punchintime'], name='pel_punchin_brin_idx'),
            BrinIndex(fields=['punchouttime'], name='pel_punchout_brin_idx'),
        ]
```

**When to use:**
- Data inserted in chronological order
- Range queries on date/time fields
- Tables with >100k rows

**Performance:** Very compact (100x smaller than B-Tree), excellent for ranges

---

### GIST Index (Generalized Search Tree)

**Use for:**
- Geometric/spatial data (PostGIS)
- Range types
- Custom data types
- Full-text search (with tsvector)

**Example:**
```python
from django.contrib.postgres.indexes import GistIndex
from django.contrib.gis.db.models import PointField

class PeopleEventlog(models.Model):
    startlocation = PointField(geography=True, null=True)
    endlocation = PointField(geography=True, null=True)

    class Meta:
        indexes = [
            GistIndex(fields=['startlocation'], name='pel_startloc_gist_idx'),
        ]
```

**Performance:** Excellent for spatial queries, supports KNN searches

---

## 🏗️ Composite Index Patterns

### Common Query Combinations

#### Status + Priority Filtering
```python
class Ticket(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['status', 'priority']),
        ]

Ticket.objects.filter(status='NEW', priority='HIGH')
```

#### Tenant + Status Filtering
```python
class Ticket(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['bu', 'status']),
        ]

Ticket.objects.filter(bu=business_unit, status='NEW')
```

#### User + Date Filtering (Attendance)
```python
class PeopleEventlog(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['people', 'datefor']),
        ]

PeopleEventlog.objects.filter(people=user, datefor__gte=start_date)
```

### Field Order Matters!

```python
models.Index(fields=['status', 'priority'])
```

✅ Optimizes: `filter(status=x, priority=y)` or `filter(status=x)`
❌ Does NOT optimize: `filter(priority=y)` alone

**Rule:** Put the most selective field first!

---

## 🚀 Partial Indexes (Filtered Indexes)

**Use for:** Boolean fields or specific value filtering

```python
class Ticket(models.Model):
    isescalated = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(
                fields=['isescalated'],
                name='ticket_escalated_idx',
                condition=models.Q(isescalated=True)
            ),
        ]
```

**Benefits:**
- Smaller index size (only indexes True values)
- Faster queries for active/enabled records
- Reduced write overhead

---

## 📋 Index Strategy Checklist

### For Every Model, Consider:

- [ ] **Status/Priority fields** - Add `db_index=True` or composite index
- [ ] **Foreign keys** - Verify auto-created indexes exist
- [ ] **Date/DateTime fields** - Use BRIN for time-series, B-Tree for lookups
- [ ] **JSON fields** - Add GIN if querying contents
- [ ] **Boolean filters** - Use partial indexes for `True` cases
- [ ] **Common query patterns** - Add composite indexes
- [ ] **Ordering fields** - Index fields used in `order_by()`

### Migration Pattern

```python
from django.db import migrations, models
from django.contrib.postgres.indexes import GinIndex, BrinIndex

class Migration(migrations.Migration):
    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(..., db_index=True),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(
                fields=['status', 'priority'],
                name='ticket_status_priority_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=BrinIndex(
                fields=['modifieddatetime'],
                name='ticket_modified_brin_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=GinIndex(
                fields=['ticketlog'],
                name='ticket_log_gin_idx'
            ),
        ),
    ]
```

---

## 🔍 Monitoring and Maintenance

### Audit Indexes
```bash
python manage.py audit_database_indexes
python manage.py audit_database_indexes --app y_helpdesk
python manage.py audit_database_indexes --generate-migrations
```

### Check Index Usage
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Identify Missing Indexes
```sql
SELECT
    schemaname,
    tablename,
    seq_scan,
    idx_scan,
    seq_scan / (idx_scan + seq_scan + 0.0001) AS seq_scan_ratio
FROM pg_stat_user_tables
WHERE schemaname = 'public'
    AND seq_scan > 100
ORDER BY seq_scan DESC;
```

---

## ⚠️ Common Pitfalls

### 1. Over-Indexing
❌ **Don't:** Create indexes on every field
✅ **Do:** Index based on actual query patterns

### 2. Ignoring Write Performance
❌ **Don't:** Add 10 indexes to frequently updated tables
✅ **Do:** Balance read vs write performance

### 3. Wrong Index Type
❌ **Don't:** Use B-Tree for JSON containment queries
✅ **Do:** Use GIN for JSON, BRIN for time-series

### 4. Missing Composite Indexes
❌ **Don't:** Create separate indexes on `status` and `priority`
✅ **Do:** Create composite index on `['status', 'priority']`

### 5. Unused Indexes
❌ **Don't:** Keep indexes that are never used
✅ **Do:** Monitor and remove unused indexes

---

## 🎯 Performance Targets

| Query Type | Without Index | With Index | Target |
|------------|---------------|------------|--------|
| Status filter | 500-1000ms | 10-50ms | <100ms |
| Date range | 1000-2000ms | 50-150ms | <200ms |
| JSON containment | 2000-5000ms | 100-300ms | <500ms |
| Composite filter | 800-1500ms | 15-80ms | <100ms |

---

## 📚 Additional Resources

- [PostgreSQL Index Types](https://www.postgresql.org/docs/current/indexes-types.html)
- [Django Index Reference](https://docs.djangoproject.com/en/5.0/ref/models/indexes/)
- Internal: `apps/core/management/commands/audit_database_indexes.py`
- Internal: `apps/core/services/index_recommendation_service.py`