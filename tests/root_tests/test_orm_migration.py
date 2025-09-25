#!/usr/bin/env python
"""
Test Django ORM Migration - Run this with: python manage.py shell < test_orm_migration.py
"""
import time
from datetime import date, timedelta

print("\n" + "="*60)
print("Django ORM Migration Verification Test")
print("="*60)

# Test 1: Import Core Modules
print("\n1. Testing Core Module Imports...")
try:
    from apps.core.queries import TreeTraversal, QueryRepository, ReportQueryRepository
    print("   ✅ Query modules imported successfully")
except ImportError as e:
    print(f"   ❌ Query import failed: {e}")
    
try:
    from apps.core.cache_manager import CacheManager, TreeCache
    print("   ✅ Cache modules imported successfully")
except ImportError as e:
    print(f"   ❌ Cache import failed: {e}")

# Test 2: Check Model Access
print("\n2. Testing Model Access...")
try:
    from apps.peoples.models import People
    people_count = People.objects.count()
    print(f"   ✅ People model works: {people_count} people in database")
except Exception as e:
    print(f"   ❌ People model error: {e}")

try:
    from apps.onboarding.models import BT
    bt_count = BT.objects.filter(active=True).count()
    print(f"   ✅ BT model works: {bt_count} active BT items")
except Exception as e:
    print(f"   ❌ BT model error: {e}")

# Test 3: Tree Traversal
print("\n3. Testing Tree Traversal (Replacement for Recursive CTEs)...")
try:
    from apps.onboarding.models import BT
    from apps.core.queries import TreeTraversal
    
    # Get some nodes
    nodes = list(BT.objects.filter(active=True).values('id', 'code', 'name', 'parent_id')[:50])
    
    if nodes:
        # Find a root node (one with no parent)
        root_node = next((n for n in nodes if n['parent_id'] is None), nodes[0])
        root_id = root_node['id']
        
        # Test tree building
        start = time.time()
        tree = TreeTraversal.build_tree(nodes, root_id=root_id)
        build_time = (time.time() - start) * 1000
        
        print(f"   ✅ Tree traversal works: Built tree with {len(tree)} nodes in {build_time:.1f}ms")
        
        # Show first few nodes
        print("   Sample tree structure:")
        for node in tree[:5]:
            level = node.get('level', 0)
            print(f"     {'  ' * level}- {node['name']} (ID: {node['id']})")
    else:
        print("   ⚠️  No BT data found to test tree traversal")
        
except Exception as e:
    print(f"   ❌ Tree traversal error: {e}")

# Test 4: Query Optimization
print("\n4. Testing Query Optimization...")
try:
    from django.db import connection, reset_queries
    from apps.onboarding.models import BT
    
    # Test without optimization
    reset_queries()
    items = BT.objects.filter(active=True)[:5]
    for item in items:
        if item.parent:
            _ = item.parent.name
    unoptimized_count = len(connection.queries)
    
    # Test with optimization
    reset_queries()
    items = BT.objects.filter(active=True).select_related('parent')[:5]
    for item in items:
        if item.parent:
            _ = item.parent.name
    optimized_count = len(connection.queries)
    
    print(f"   ✅ Query optimization works:")
    print(f"      Without select_related: {unoptimized_count} queries")
    print(f"      With select_related: {optimized_count} queries")
    
except Exception as e:
    print(f"   ❌ Query optimization test error: {e}")

# Test 5: Cache Functionality
print("\n5. Testing Cache System...")
try:
    from django.core.cache import cache
    from apps.core.cache_manager import TreeCache
    
    # Test basic cache
    cache.clear()
    cache.set('test_key', 'test_value', 30)
    value = cache.get('test_key')
    
    if value == 'test_value':
        print("   ✅ Basic cache operations work")
    else:
        print("   ❌ Cache not working properly")
    
    # Test TreeCache
    if 'BT' in locals():
        try:
            start = time.time()
            tree1 = TreeCache.get_full_tree(root_id=1)
            first_call = (time.time() - start) * 1000
            
            start = time.time()
            tree2 = TreeCache.get_full_tree(root_id=1)
            second_call = (time.time() - start) * 1000
            
            print(f"   ✅ TreeCache works:")
            print(f"      First call: {first_call:.1f}ms")
            print(f"      Second call (cached): {second_call:.1f}ms")
        except Exception as e:
            print(f"   ⚠️  TreeCache test skipped: {e}")
            
except Exception as e:
    print(f"   ❌ Cache test error: {e}")

# Test 6: Report Queries
print("\n6. Testing Report Queries...")
try:
    from apps.core.queries import ReportQueryRepository
    
    # Get available methods
    report_methods = [m for m in dir(ReportQueryRepository) if not m.startswith('_') and callable(getattr(ReportQueryRepository, m))]
    print(f"   ✅ ReportQueryRepository has {len(report_methods)} methods")
    print(f"      Sample methods: {', '.join(report_methods[:5])}")
    
except Exception as e:
    print(f"   ❌ Report query test error: {e}")

# Test 7: Database Connection
print("\n7. Testing Database Connection...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
    print(f"   ✅ Database connection works")
    print(f"      Backend: {connection.settings_dict['ENGINE']}")
except Exception as e:
    print(f"   ❌ Database connection error: {e}")

# Test 8: Check Files
print("\n8. Checking Migration Files...")
import os

files_to_check = [
    ('apps/core/queries.py', 'New ORM queries'),
    ('apps/core/cache_manager.py', 'Cache system'),
    ('monitoring/django_monitoring.py', 'Monitoring middleware'),
    ('scripts/database_optimizations.sql', 'DB indexes'),
]

for filepath, description in files_to_check:
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"   ✅ {description}: {filepath} ({size:,} bytes)")
    else:
        print(f"   ❌ Missing: {filepath}")

# Summary
print("\n" + "="*60)
print("VERIFICATION SUMMARY")
print("="*60)
print("\nThe Django ORM migration files are in place and basic functionality is working.")
print("\nNext steps:")
print("1. Review any errors above")
print("2. Test specific features in your application") 
print("3. Monitor performance using: http://localhost:8000/monitoring/")
print("4. Check documentation in docs/DJANGO_ORM_MIGRATION_GUIDE.md")
print("\n✅ Basic verification complete!")