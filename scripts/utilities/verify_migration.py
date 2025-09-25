#!/usr/bin/env python
"""
Django ORM Migration Verification Script
Run this to verify the migration is working correctly
"""
import os
import sys
import django
import time
from datetime import date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'YOUTILITY3.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize Django
try:
    django.setup()
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    print("Make sure you're in the project root and settings are correct")
    sys.exit(1)

# Now import Django modules
from django.db import connection, reset_queries
from django.core.cache import cache

print("Django ORM Migration Verification")
print("=" * 60)

# Test 1: Import test
print("\n1. Testing imports...")
try:
    from apps.core.queries import TreeTraversal, QueryRepository, ReportQueryRepository
    from apps.core.cache_manager import TreeCache, cache_decorator
    print("✅ Core modules imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    print("   Make sure apps.core.queries and cache_manager exist")
    sys.exit(1)

# Test 2: Basic ORM query
print("\n2. Testing basic ORM functionality...")
try:
    # Import your model - adjust based on your actual model location
    from django.contrib.auth.models import User
    user_count = User.objects.count()
    print(f"✅ Basic query works: {user_count} users in database")
except Exception as e:
    print(f"❌ Basic query failed: {e}")

# Test 3: Check if BT model exists and test tree traversal
print("\n3. Testing tree traversal...")
try:
    from django.apps import apps
    
    # Try to find BT model
    bt_model = None
    for app_config in apps.get_app_configs():
        try:
            bt_model = apps.get_model(app_config.label, 'BT')
            break
        except LookupError:
            continue
    
    if bt_model:
        nodes = list(bt_model.objects.filter(active=True).values('id', 'code', 'name', 'parent_id'))
        if nodes:
            tree = TreeTraversal.build_tree(nodes, root_id=nodes[0]['id'])
            print(f"✅ Tree traversal works: {len(tree)} nodes in tree")
        else:
            print("⚠️  No active BT records found to test tree traversal")
    else:
        print("⚠️  BT model not found - skipping tree traversal test")
        
except Exception as e:
    print(f"❌ Tree traversal failed: {e}")

# Test 4: Query performance with select_related
print("\n4. Testing query optimization...")
try:
    reset_queries()
    
    # Test with any model that has foreign keys
    users = User.objects.all()[:5]
    for user in users:
        _ = user.username
    
    unoptimized_queries = len(connection.queries)
    print(f"✅ Query counting works: {unoptimized_queries} queries executed")
    
except Exception as e:
    print(f"❌ Query optimization test failed: {e}")

# Test 5: Cache functionality
print("\n5. Testing cache system...")
try:
    # Clear cache first
    cache.clear()
    
    # Test basic cache operations
    cache.set('test_key', 'test_value', 30)
    value = cache.get('test_key')
    
    if value == 'test_value':
        print("✅ Cache basic operations work")
    else:
        print("❌ Cache not working properly")
    
    # Test cache performance
    @cache_decorator(timeout=60, key_prefix='test')
    def expensive_operation():
        time.sleep(0.1)  # Simulate expensive operation
        return "result"
    
    start = time.time()
    result1 = expensive_operation()
    uncached_time = time.time() - start
    
    start = time.time()
    result2 = expensive_operation()
    cached_time = time.time() - start
    
    if cached_time < uncached_time / 2:
        print(f"✅ Cache decorator works: {uncached_time*1000:.1f}ms → {cached_time*1000:.1f}ms")
    else:
        print(f"⚠️  Cache might not be working: {uncached_time*1000:.1f}ms → {cached_time*1000:.1f}ms")
        
except Exception as e:
    print(f"❌ Cache test failed: {e}")

# Test 6: Database connection
print("\n6. Testing database connectivity...")
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
    print("✅ Database connection works")
    
    # Show database backend
    print(f"   Database: {connection.settings_dict['ENGINE']}")
    
except Exception as e:
    print(f"❌ Database connection failed: {e}")

# Test 7: Check monitoring module
print("\n7. Testing monitoring integration...")
try:
    from monitoring.django_monitoring import metrics_collector
    from monitoring.views import get_health_status
    
    health = get_health_status()
    print(f"✅ Monitoring module works: System is {health.get('status', 'unknown')}")
    
except ImportError:
    print("⚠️  Monitoring module not found - this is optional")
except Exception as e:
    print(f"⚠️  Monitoring test error: {e}")

# Test 8: Check for common issues
print("\n8. Checking for common issues...")

# Check if raw_queries.py still exists
try:
    from apps.core import raw_queries
    print("⚠️  raw_queries.py still exists - should be deprecated")
except ImportError:
    print("✅ raw_queries.py properly removed/deprecated")

# Check Python path
if os.getcwd() in sys.path or '.' in sys.path:
    print("✅ Python path configured correctly")
else:
    print("⚠️  Project root not in Python path")

# Summary
print("\n" + "=" * 60)
print("VERIFICATION SUMMARY")
print("=" * 60)

# Performance benchmarks
print("\nExpected Performance Benchmarks:")
print("- Tree queries: < 100ms (uncached), < 5ms (cached)")
print("- Report queries: < 500ms")
print("- Response time p95: < 1 second")
print("- Cache hit rate: > 70%")

print("\nNext Steps:")
print("1. Run full test suite: python manage.py test")
print("2. Check monitoring dashboard: http://localhost:8000/monitoring/")
print("3. Test specific features in the application")
print("4. Monitor logs for any SQL-related errors")

print("\n✅ Basic verification complete! Check the results above.")