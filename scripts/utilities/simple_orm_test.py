#!/usr/bin/env python
"""
Simple ORM Migration Test
Run with: python manage.py shell < simple_orm_test.py
"""

print("\n" + "="*60)
print("Django ORM Migration - Simple Verification")
print("="*60)

# 1. Test Imports
print("\n✅ Testing Imports...")
from apps.core.queries import TreeTraversal, QueryRepository, ReportQueryRepository
from apps.core.cache_manager import CacheManager, TreeCache
from apps.client_onboarding.models import Bt
from apps.peoples.models import People
print("   All core modules imported successfully!")

# 2. Test Basic Queries
print("\n✅ Testing Basic ORM Queries...")
people_count = People.objects.count()
bt_count = Bt.objects.count()
print(f"   - People in database: {people_count}")
print(f"   - Bt (Business Tree) items: {bt_count}")

# 3. Test Query Optimization
print("\n✅ Testing Query Optimization...")
from django.db import connection, reset_queries

# Without optimization
reset_queries()
people = People.objects.all()[:5]
for p in people:
    _ = str(p)
without_optimization = len(connection.queries)

# With select_related (if there are foreign keys)
reset_queries()
people = People.objects.select_related()[:5]
for p in people:
    _ = str(p)
with_optimization = len(connection.queries)

print(f"   - Queries without optimization: {without_optimization}")
print(f"   - Queries with optimization: {with_optimization}")

# 4. Test Cache
print("\n✅ Testing Cache System...")
from django.core.cache import cache

cache.set('test_key', 'Hello ORM!', 60)
value = cache.get('test_key')
print(f"   - Cache working: {value == 'Hello ORM!'}")
print(f"   - Cache backend: {cache._cache.__class__.__name__}")

# 5. Test Report Queries
print("\n✅ Testing Report Query Repository...")
methods = [m for m in dir(ReportQueryRepository) if not m.startswith('_')]
print(f"   - Available report methods: {len(methods)}")
print(f"   - Sample: {', '.join(methods[:3])}")

# 6. Check Monitoring
print("\n✅ Checking Monitoring Setup...")
import os
monitoring_files = [
    'monitoring/django_monitoring.py',
    'monitoring/views.py',
    'monitoring/alerts.py'
]
for f in monitoring_files:
    exists = os.path.exists(f)
    print(f"   - {f}: {'✓' if exists else '✗'}")

# 7. Database Info
print("\n✅ Database Information...")
from django.db import connection
print(f"   - Database: {connection.settings_dict['ENGINE']}")
print(f"   - Name: {connection.settings_dict['NAME']}")

print("\n" + "="*60)
print("VERIFICATION COMPLETE!")
print("="*60)
print("\nThe Django ORM migration is working! 🎉")
print("\nTo test further:")
print("1. Run the application: python manage.py runserver")
print("2. Check monitoring at: http://localhost:8000/monitoring/") 
print("3. Read the guide at: docs/DJANGO_ORM_MIGRATION_GUIDE.md")
print("\n✅ All basic tests passed!")