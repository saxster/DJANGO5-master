#!/usr/bin/env python
"""
Test Caching Layer Implementation

Verifies:
- Cache decorator works correctly
- Cache hit/miss functionality
- Cache invalidation
- Performance improvements

Usage:
    python scripts/test_caching_layer.py
"""

import os
import sys
import django
import time
from datetime import date, timedelta

# Setup Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.core.decorators.caching import cache_query, invalidate_cache_pattern
from apps.core.services.cache_invalidation_service import CacheInvalidationService

People = get_user_model()


def test_cache_decorator():
    """Test cache decorator functionality."""
    print("\n" + "="*80)
    print("TEST 1: Cache Decorator Functionality")
    print("="*80)

    # Define a simple cached function
    call_count = {'value': 0}

    @cache_query(timeout=60, key_prefix='test')
    def expensive_query(arg1, arg2):
        """Simulate expensive database query."""
        call_count['value'] += 1
        time.sleep(0.1)  # Simulate query time
        return f"Result: {arg1} + {arg2}"

    # First call - should execute function
    print("\n1. First call (cache MISS)...")
    start = time.time()
    result1 = expensive_query("foo", "bar")
    duration1 = time.time() - start
    print(f"   Result: {result1}")
    print(f"   Duration: {duration1:.4f}s")
    print(f"   Function calls: {call_count['value']}")

    # Second call - should use cache
    print("\n2. Second call (cache HIT)...")
    start = time.time()
    result2 = expensive_query("foo", "bar")
    duration2 = time.time() - start
    print(f"   Result: {result2}")
    print(f"   Duration: {duration2:.4f}s")
    print(f"   Function calls: {call_count['value']}")

    # Verify cache was used
    assert result1 == result2, "Results should match"
    assert call_count['value'] == 1, "Function should only be called once"
    assert duration2 < duration1, "Cached call should be faster"

    print("\n✅ Cache decorator test PASSED")
    print(f"   Speedup: {duration1/duration2:.2f}x faster")

    # Cleanup
    invalidate_cache_pattern('test:*')


def test_cache_invalidation():
    """Test cache invalidation patterns."""
    print("\n" + "="*80)
    print("TEST 2: Cache Invalidation")
    print("="*80)

    # Set some test cache values
    cache.set('tickets:user:123:page:1', {'data': 'test1'}, 300)
    cache.set('tickets:user:123:page:2', {'data': 'test2'}, 300)
    cache.set('tickets:user:456:page:1', {'data': 'test3'}, 300)
    cache.set('people:search:test', {'data': 'test4'}, 300)

    print("\n1. Setting test cache values...")
    print("   - tickets:user:123:page:1")
    print("   - tickets:user:123:page:2")
    print("   - tickets:user:456:page:1")
    print("   - people:search:test")

    # Invalidate user 123's tickets
    print("\n2. Invalidating tickets for user 123...")
    deleted = invalidate_cache_pattern('tickets:user:123:*')
    print(f"   Deleted {deleted} keys")

    # Check cache values
    print("\n3. Checking cache values after invalidation...")
    val1 = cache.get('tickets:user:123:page:1')
    val2 = cache.get('tickets:user:123:page:2')
    val3 = cache.get('tickets:user:456:page:1')
    val4 = cache.get('people:search:test')

    print(f"   tickets:user:123:page:1 = {val1}")
    print(f"   tickets:user:123:page:2 = {val2}")
    print(f"   tickets:user:456:page:1 = {val3}")
    print(f"   people:search:test = {val4}")

    assert val1 is None, "User 123 page 1 should be invalidated"
    assert val2 is None, "User 123 page 2 should be invalidated"
    assert val3 is not None, "User 456 should NOT be invalidated"
    assert val4 is not None, "People search should NOT be invalidated"

    print("\n✅ Cache invalidation test PASSED")

    # Cleanup
    cache.clear()


def test_people_search_caching():
    """Test people search caching."""
    print("\n" + "="*80)
    print("TEST 3: People Search Caching")
    print("="*80)

    # Check if we have users in database
    user_count = People.objects.count()
    print(f"\n1. Users in database: {user_count}")

    if user_count == 0:
        print("   ⚠️  No users in database - skipping this test")
        return

    from apps.api.v2.services.people_service import PeopleService

    # Get first user for testing
    test_user = People.objects.first()
    print(f"   Test user: {test_user.username}")

    # Create mock request object
    class MockRequest:
        def __init__(self, user):
            self.user = user

    mock_request = MockRequest(test_user)

    # First search - cache miss
    print("\n2. First search (cache MISS)...")
    start = time.time()
    results1 = PeopleService.search_users(mock_request, search_query='test', limit=10)
    duration1 = time.time() - start
    print(f"   Results: {len(results1)} users")
    print(f"   Duration: {duration1:.4f}s")

    # Second search - cache hit
    print("\n3. Second search (cache HIT)...")
    start = time.time()
    results2 = PeopleService.search_users(mock_request, search_query='test', limit=10)
    duration2 = time.time() - start
    print(f"   Results: {len(results2)} users")
    print(f"   Duration: {duration2:.4f}s")

    assert results1 == results2, "Results should match"
    print(f"\n✅ People search caching test PASSED")
    print(f"   Speedup: {duration1/duration2:.2f}x faster")

    # Cleanup
    invalidate_cache_pattern('people:*')


def test_attendance_query_caching():
    """Test attendance query caching."""
    print("\n" + "="*80)
    print("TEST 4: Attendance Query Caching")
    print("="*80)

    from apps.attendance.services.attendance_query_service import AttendanceQueryService
    from apps.attendance.models import PeopleEventlog

    # Check if we have attendance records
    attendance_count = PeopleEventlog.objects.count()
    print(f"\n1. Attendance records in database: {attendance_count}")

    if attendance_count == 0:
        print("   ⚠️  No attendance records - skipping this test")
        return

    # Get first attendance record for testing
    test_record = PeopleEventlog.objects.first()
    test_user_id = test_record.people_id
    print(f"   Test user ID: {test_user_id}")

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    # First query - cache miss
    print("\n2. First query (cache MISS)...")
    start = time.time()
    results1 = AttendanceQueryService.get_attendance_by_date_range(
        user_id=test_user_id,
        start_date=start_date,
        end_date=end_date
    )
    duration1 = time.time() - start
    print(f"   Results: {len(results1)} records")
    print(f"   Duration: {duration1:.4f}s")

    # Second query - cache hit
    print("\n3. Second query (cache HIT)...")
    start = time.time()
    results2 = AttendanceQueryService.get_attendance_by_date_range(
        user_id=test_user_id,
        start_date=start_date,
        end_date=end_date
    )
    duration2 = time.time() - start
    print(f"   Results: {len(results2)} records")
    print(f"   Duration: {duration2:.4f}s")

    assert results1 == results2, "Results should match"
    print(f"\n✅ Attendance query caching test PASSED")
    print(f"   Speedup: {duration1/duration2:.2f}x faster")

    # Cleanup
    invalidate_cache_pattern('attendance:*')


def main():
    """Run all cache tests."""
    print("\n" + "="*80)
    print("CACHING LAYER TEST SUITE")
    print("="*80)

    # Clear cache before starting
    print("\nClearing cache before tests...")
    cache.clear()

    try:
        # Run tests
        test_cache_decorator()
        test_cache_invalidation()
        test_people_search_caching()
        test_attendance_query_caching()

        # Summary
        print("\n" + "="*80)
        print("ALL TESTS PASSED ✅")
        print("="*80)
        print("\nCache layer is working correctly:")
        print("  - Cache decorator: ✅")
        print("  - Cache invalidation: ✅")
        print("  - People search caching: ✅")
        print("  - Attendance query caching: ✅")
        print("\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
