# N+1 Query Optimization - Quick Reference

## 🚀 Using Optimized Managers

### NOC Incidents

```python
# Export (minimal data + counts)
incidents = NOCIncident.objects.for_export()

# Detail view (all relations)
incident = NOCIncident.objects.with_full_details().get(id=123)

# List view (with counts)
incidents = NOCIncident.objects.with_counts()

# Active only
active = NOCIncident.objects.active_incidents()
```

---

## 🔧 Common Patterns Fixed

### Pattern 1: Count in Loop

```python
# ❌ BEFORE (N+1 queries)
for incident in queryset:
    count = incident.alerts.count()

# ✅ AFTER (1 query)
queryset = queryset.annotate(alert_count=Count('alerts'))
for incident in queryset:
    count = incident.alert_count
```

### Pattern 2: Aggregation in Loop

```python
# ❌ BEFORE (N queries)
for client in clients:
    avg = Alert.objects.filter(client=client).aggregate(Avg('duration'))

# ✅ AFTER (1 query)
results = Alert.objects.filter(
    client__in=clients
).values('client').annotate(avg_duration=Avg('duration'))
```

### Pattern 3: Calculation in Python

```python
# ❌ BEFORE (fetches all, calculates in Python)
total = 0
for record in records:
    total += (record.end - record.start).seconds

# ✅ AFTER (database aggregation)
total = records.annotate(
    duration=F('end') - F('start')
).aggregate(
    total=Sum(Extract('duration', 'epoch'))
)['total']
```

### Pattern 4: Nested Prefetch

```python
# ❌ BEFORE
templates = Template.objects.all()
for t in templates:
    for q in t.questions.all():
        for o in q.options.all():  # N+1+1 queries

# ✅ AFTER
templates = Template.objects.prefetch_related(
    Prefetch('questions',
        queryset=Question.objects.prefetch_related('options')
    )
)
```

---

## 📊 Performance Benchmarks

| Operation | Queries Before | Queries After | Improvement |
|-----------|----------------|---------------|-------------|
| Export 5000 incidents | 5,003 | 5 | 99.9% |
| MTTR 10 clients | 22 | 2 | 91% |
| DAR 50 records | 52 | 3 | 94% |

---

## ✅ Testing

```python
from django.test import TestCase
from django.db import connection

def test_query_count(self):
    """Verify optimized queries."""
    connection.force_debug_cursor = True
    query_count_before = len(connection.queries)
    
    # Your operation here
    incidents = NOCIncident.objects.for_export()[:100]
    list(incidents)
    
    query_count_after = len(connection.queries)
    queries_used = query_count_after - query_count_before
    
    # Should use constant queries
    self.assertLessEqual(queries_used, 5)
```

---

## 🔍 Finding N+1 Patterns

```bash
# Search for potential N+1 in loops
grep -rn "for .* in .*:" apps/ | grep -E "\.(count|all|filter)\(\)"

# Check views
grep -rn "\.count()" apps/*/views/

# Check templates
grep -rn "\.count" templates/
```

---

## 📝 Files Modified

### Core Changes
- `apps/noc/models/incident.py` - Added OptimizedIncidentManager
- `apps/noc/views/export_views.py` - Lines 113-149
- `apps/noc/views/analytics_views.py` - Lines 174-200
- `apps/reports/services/dar_service.py` - Lines 213-228

### Tests
- `apps/noc/tests/test_performance/test_n1_optimizations.py`
- `apps/reports/tests/test_performance/test_dar_service.py`

---

## 🎯 Quick Wins Checklist

- [ ] Replace `.count()` in loops with `Count()` annotation
- [ ] Use `values()` + `annotate()` instead of loop aggregations
- [ ] Move calculations from Python to database (Sum, Avg, Extract)
- [ ] Add `select_related()` for all FK access
- [ ] Use `prefetch_related()` with `Prefetch()` for complex queries
- [ ] Create manager methods for common query patterns
- [ ] Add performance tests with `assertNumQueries()`

---

**Last Updated**: November 6, 2025  
**See Also**: 
- `N1_OPTIMIZATION_PART2_SUMMARY.md` - Complete summary
- `N1_QUERY_OPTIMIZATION_PART2_IMPLEMENTATION.md` - Detailed guide
