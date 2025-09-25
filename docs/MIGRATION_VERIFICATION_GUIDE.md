# Django ORM Migration - Step-by-Step Verification Guide

## Prerequisites
Before starting, ensure you have:
- Django shell access: `python manage.py shell`
- Database access
- Application running locally or in test environment

## Step 1: Verify Basic ORM Functionality

### 1.1 Test Django Shell Access
```bash
python manage.py shell
```

### 1.2 Import and Test Core Components
```python
# In Django shell
from apps.core.queries import QueryRepository, TreeTraversal, ReportQueryRepository
from apps.core.cache_manager import cache_decorator, TreeCache

# Should import without errors
print("✓ Core modules imported successfully")
```

### 1.3 Test Basic Query
```python
# Test if ORM queries work
from apps.models import BT

# Get count of active items
count = BT.objects.filter(active=True).count()
print(f"Active BT items: {count}")

# Should return a number without errors
```

## Step 2: Test Tree Traversal (Replacement for Recursive CTEs)

### 2.1 Test Tree Building
```python
from apps.core.queries import TreeTraversal
from apps.models import BT

# Get all nodes
all_nodes = list(BT.objects.filter(active=True).values('id', 'code', 'name', 'parent_id'))
print(f"Total nodes: {len(all_nodes)}")

# Build tree structure
tree = TreeTraversal.build_tree(all_nodes, root_id=1)
print(f"Tree nodes: {len(tree)}")

# Display tree structure
for node in tree[:10]:  # First 10 nodes
    print("  " * node.get('level', 0) + f"- {node['name']} (ID: {node['id']})")
```

### 2.2 Compare with Old Raw Query (If Still Available)
```python
# Optional: If raw_queries.py still exists for comparison
try:
    from apps.core.raw_queries import get_tree_raw_query
    # Compare performance
    import time
    
    # Old way (if available)
    start = time.time()
    # Execute old query
    old_time = time.time() - start
    
    # New way
    start = time.time()
    tree = TreeTraversal.build_tree(all_nodes, root_id=1)
    new_time = time.time() - start
    
    print(f"Old way: {old_time*1000:.2f}ms")
    print(f"New way: {new_time*1000:.2f}ms")
    print(f"Improvement: {old_time/new_time:.1f}x faster")
except ImportError:
    print("raw_queries.py not available for comparison")
```

## Step 3: Test Cache Functionality

### 3.1 Test Cache Operations
```python
from apps.core.cache_manager import TreeCache
from django.core.cache import cache

# Clear cache first
cache.clear()
print("✓ Cache cleared")

# First call - should hit database
import time
start = time.time()
tree_data = TreeCache.get_full_tree(root_id=1)
first_call = time.time() - start
print(f"First call (uncached): {first_call*1000:.2f}ms")

# Second call - should hit cache
start = time.time()
tree_data = TreeCache.get_full_tree(root_id=1)
second_call = time.time() - start
print(f"Second call (cached): {second_call*1000:.2f}ms")

print(f"Cache speedup: {first_call/second_call:.0f}x faster")
```

### 3.2 Test Cache Invalidation
```python
# Test cache invalidation
initial_count = len(tree_data)

# Invalidate cache
TreeCache.invalidate_tree_cache(node_id=1)
print("✓ Cache invalidated")

# Next call should hit database again
start = time.time()
tree_data = TreeCache.get_full_tree(root_id=1)
duration = time.time() - start
print(f"After invalidation: {duration*1000:.2f}ms")
```

## Step 4: Test Report Queries

### 4.1 Test Report Query Repository
```python
from apps.core.queries import ReportQueryRepository
from datetime import date, timedelta

# Test date range
end_date = date.today()
start_date = end_date - timedelta(days=30)

# Test attendance summary (example)
try:
    data = ReportQueryRepository.get_attendance_summary(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )
    print(f"✓ Attendance summary returned {len(data)} records")
except Exception as e:
    print(f"✗ Error: {e}")
```

## Step 5: Test Query Performance

### 5.1 Check Query Optimization
```python
from django.db import connection
from django.db import reset_queries
from apps.models import BT

# Reset query counter
reset_queries()

# Test without optimization
items = BT.objects.filter(active=True)
for item in items[:5]:
    if item.parent:
        print(f"{item.name} -> {item.parent.name}")

print(f"Queries without optimization: {len(connection.queries)}")

# Reset and test with optimization
reset_queries()

items = BT.objects.filter(active=True).select_related('parent')
for item in items[:5]:
    if item.parent:
        print(f"{item.name} -> {item.parent.name}")

print(f"Queries with select_related: {len(connection.queries)}")
# Should be significantly fewer queries
```

## Step 6: Test Monitoring Endpoints

### 6.1 Check Health Endpoint
```bash
# In terminal
curl http://localhost:8000/monitoring/health/
```

Expected response:
```json
{
    "status": "healthy",
    "database": "connected",
    "cache": "connected",
    "timestamp": "2024-01-23T10:00:00Z"
}
```

### 6.2 Check Metrics Endpoint
```bash
curl http://localhost:8000/monitoring/metrics/
```

Should return performance metrics in JSON format.

### 6.3 Check Query Performance Endpoint
```bash
curl http://localhost:8000/monitoring/performance/queries/
```

Should show recent query performance data.

## Step 7: Test Database Indexes

### 7.1 Verify Indexes Exist
```sql
-- In PostgreSQL
\d bt
-- Should show indexes including new ones

-- Or query pg_indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'bt' 
ORDER BY indexname;
```

### 7.2 Check Index Usage
```sql
-- Check if indexes are being used
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM bt 
WHERE active = true AND parent_id = 1;

-- Should show "Index Scan" not "Seq Scan"
```

## Step 8: Run Integration Tests

### 8.1 Run Test Suite
```bash
# Run ORM migration tests
python manage.py test tests.test_orm_migration -v 2

# Run validation tests
python tests/validate_schema.py
python tests/validate_data_integrity.py
```

### 8.2 Run Performance Benchmarks
```bash
# If benchmark script exists
python tests/benchmark_orm_performance.py
```

## Step 9: Application-Level Testing

### 9.1 Test Through Django Admin
1. Login to Django Admin
2. Navigate to BT model
3. Try list view - should load quickly
4. Try tree view - should show hierarchy
5. Create/Update/Delete operations

### 9.2 Test Through Application UI
1. Access reports section
2. Generate a report that previously used raw SQL
3. Verify data correctness
4. Check response time

### 9.3 Test Background Tasks
```python
# Test ticket escalation
from apps.background.ticket_escalation import process_escalations

# Should run without SQL errors
result = process_escalations()
print(f"Processed {result['count']} escalations")
```

## Step 10: Monitoring Verification

### 10.1 Start Monitoring Service
```bash
# Run monitoring service
python manage.py run_monitoring --once
```

Should output current metrics without errors.

### 10.2 Check Grafana Dashboard
1. Access Grafana (usually http://localhost:3000)
2. Import dashboard from `/monitoring/dashboards/grafana_django_orm.json`
3. Verify metrics are populating

## Common Issues and Solutions

### Issue 1: Import Errors
```python
# If you get ImportError
import sys
print(sys.path)
# Ensure project root is in Python path
```

### Issue 2: Database Connection
```python
# Test database connection
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT 1")
print("✓ Database connected")
```

### Issue 3: Cache Not Working
```python
from django.conf import settings
print(settings.CACHES)
# Verify cache backend is configured
```

### Issue 4: Slow Performance
```python
# Enable query logging
import logging
logging.getLogger('django.db.backends').setLevel(logging.DEBUG)
# Now queries will be logged
```

## Performance Verification Checklist

- [ ] Tree queries complete in < 100ms (uncached)
- [ ] Tree queries complete in < 5ms (cached)
- [ ] Report queries complete in < 500ms
- [ ] No N+1 query problems detected
- [ ] Cache hit rate > 70%
- [ ] All endpoints respond in < 1 second

## Final Verification Script

Save this as `verify_migration.py`:

```python
#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from apps.core.queries import TreeTraversal, QueryRepository
from apps.core.cache_manager import TreeCache
from django.core.cache import cache
import time

print("Django ORM Migration Verification")
print("=" * 50)

# Test 1: Import test
try:
    from apps.core.queries import *
    print("✓ Core modules imported successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Basic query
try:
    from apps.models import BT
    count = BT.objects.filter(active=True).count()
    print(f"✓ Basic query works: {count} active items")
except Exception as e:
    print(f"✗ Basic query failed: {e}")

# Test 3: Tree traversal
try:
    nodes = list(BT.objects.filter(active=True).values('id', 'code', 'name', 'parent_id'))
    tree = TreeTraversal.build_tree(nodes, root_id=1)
    print(f"✓ Tree traversal works: {len(tree)} nodes in tree")
except Exception as e:
    print(f"✗ Tree traversal failed: {e}")

# Test 4: Cache
try:
    cache.clear()
    start = time.time()
    TreeCache.get_full_tree(root_id=1)
    uncached_time = time.time() - start
    
    start = time.time()
    TreeCache.get_full_tree(root_id=1)
    cached_time = time.time() - start
    
    print(f"✓ Cache works: {uncached_time*1000:.1f}ms → {cached_time*1000:.1f}ms")
except Exception as e:
    print(f"✗ Cache failed: {e}")

# Test 5: Monitoring
try:
    from monitoring.views import get_health_status
    health = get_health_status()
    print(f"✓ Monitoring works: System is {health['status']}")
except Exception as e:
    print(f"✗ Monitoring failed: {e}")

print("\nVerification complete!")
```

Run with:
```bash
python verify_migration.py
```

If all tests pass, your Django ORM migration is working correctly!