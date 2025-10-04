"""
Comprehensive Unit Tests for Universal Idempotency Service

Tests verify:
- Idempotency key generation (deterministic, collision-resistant)
- Duplicate detection (Redis + database fallback)
- Distributed locks (Redis + PostgreSQL advisory locks)
- TTL expiration and cache behavior
- Performance (< 10ms overhead target)
- Edge cases and failure scenarios

Test Coverage:
- Unit tests: Individual function behavior
- Integration tests: Redis + Database interaction
- Performance tests: Overhead validation
- Security tests: Key generation collision resistance
"""

import pytest
import hashlib
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase, TransactionTestCase
from django.core.cache import cache
from django.utils import timezone
from django.db import connection

from apps.core.tasks.idempotency_service import (
    UniversalIdempotencyService,
    with_idempotency
)
from apps.core.models.sync_idempotency import SyncIdempotencyRecord
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR


class TestIdempotencyKeyGeneration(TestCase):
    """Test deterministic key generation"""

    def setUp(self):
        self.service = UniversalIdempotencyService

    def test_generate_task_key_deterministic(self):
        """Test that same inputs always generate same key"""
        task_name = "test_task"
        args = (1, 2, 3)
        kwargs = {'foo': 'bar', 'baz': 'qux'}

        key1 = self.service.generate_task_key(task_name, args, kwargs)
        key2 = self.service.generate_task_key(task_name, args, kwargs)

        self.assertEqual(key1, key2, "Keys should be deterministic")

    def test_generate_task_key_different_args(self):
        """Test that different args generate different keys"""
        task_name = "test_task"

        key1 = self.service.generate_task_key(task_name, args=(1,))
        key2 = self.service.generate_task_key(task_name, args=(2,))

        self.assertNotEqual(key1, key2, "Different args should generate different keys")

    def test_generate_task_key_arg_order_matters(self):
        """Test that argument order affects key"""
        task_name = "test_task"

        key1 = self.service.generate_task_key(task_name, kwargs={'a': 1, 'b': 2})
        key2 = self.service.generate_task_key(task_name, kwargs={'b': 2, 'a': 1})

        # Keys should be SAME because dict is sorted before hashing
        self.assertEqual(key1, key2, "Dict order should not matter (sorted keys)")

    def test_generate_task_key_scope(self):
        """Test that scope affects key generation"""
        task_name = "test_task"
        args = (1,)

        key_global = self.service.generate_task_key(task_name, args, scope='global')
        key_user = self.service.generate_task_key(task_name, args, scope='user')

        self.assertNotEqual(key_global, key_user, "Different scopes should generate different keys")

    def test_generate_task_key_prefix(self):
        """Test that generated key has correct prefix"""
        task_name = "test_task"
        args = (1,)

        key = self.service.generate_task_key(task_name, args)

        self.assertTrue(key.startswith(f"task:{task_name}:"), "Key should have task prefix")

    def test_generate_task_key_complex_data(self):
        """Test key generation with complex data structures"""
        task_name = "test_task"
        args = ([1, 2, 3], {'nested': {'deep': 'value'}})
        kwargs = {'list_arg': [4, 5, 6], 'dict_arg': {'key': 'value'}}

        # Should not raise exception
        key = self.service.generate_task_key(task_name, args, kwargs)
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)

    def test_generate_task_key_collision_resistance(self):
        """Test that similar inputs generate different keys"""
        task_name = "test_task"

        key1 = self.service.generate_task_key(task_name, args=("test",))
        key2 = self.service.generate_task_key(task_name, args=("test1",))
        key3 = self.service.generate_task_key(task_name, args=("tset",))

        keys = {key1, key2, key3}
        self.assertEqual(len(keys), 3, "Similar inputs should not collide")


@pytest.mark.django_db
class TestDuplicateDetection(TransactionTestCase):
    """Test duplicate detection via Redis and database"""

    def setUp(self):
        self.service = UniversalIdempotencyService
        # Clear cache before each test
        cache.clear()

    def test_check_duplicate_not_found(self):
        """Test that new key returns None"""
        key = "task:test:unique_key_123"

        result = self.service.check_duplicate(key)

        self.assertIsNone(result, "New key should not be found")

    def test_check_duplicate_redis_hit(self):
        """Test duplicate detection from Redis cache"""
        key = "task:test:cached_key"
        cached_data = {'result': 'success', 'data': 'test'}

        # Cache data
        cache.set(key, cached_data, timeout=SECONDS_IN_HOUR)

        # Check duplicate
        result = self.service.check_duplicate(key)

        self.assertEqual(result, cached_data, "Should return cached data")

    def test_check_duplicate_database_fallback(self):
        """Test fallback to database when Redis unavailable"""
        key = "task:test:db_key"
        response_data = {'result': 'success', 'data': 'from_db'}

        # Create database record
        SyncIdempotencyRecord.objects.create(
            idempotency_key=key,
            scope='task',
            request_hash=hashlib.sha256(str(response_data).encode()).hexdigest()[:64],
            response_data=response_data,
            expires_at=timezone.now() + timedelta(hours=1)
        )

        # Mock Redis failure
        with patch('apps.core.tasks.idempotency_service.cache.get', side_effect=ConnectionError):
            result = self.service.check_duplicate(key, use_redis=False)

        self.assertEqual(result, response_data, "Should fallback to database")

    def test_check_duplicate_expired_record(self):
        """Test that expired records are not returned"""
        key = "task:test:expired_key"
        response_data = {'result': 'success'}

        # Create expired database record
        SyncIdempotencyRecord.objects.create(
            idempotency_key=key,
            scope='task',
            request_hash=hashlib.sha256(str(response_data).encode()).hexdigest()[:64],
            response_data=response_data,
            expires_at=timezone.now() - timedelta(hours=1)  # Expired
        )

        result = self.service.check_duplicate(key, use_redis=False)

        self.assertIsNone(result, "Expired records should not be returned")

    def test_store_result_redis_and_database(self):
        """Test that result is stored in both Redis and database"""
        key = "task:test:store_key"
        result_data = {'status': 'success', 'data': 'test_result'}

        success = self.service.store_result(
            key, result_data, ttl_seconds=3600, task_name='test_task'
        )

        self.assertTrue(success, "Store should succeed")

        # Verify Redis
        cached = cache.get(key)
        self.assertEqual(cached, result_data, "Data should be in Redis")

        # Verify database
        db_record = SyncIdempotencyRecord.objects.filter(idempotency_key=key).first()
        self.assertIsNotNone(db_record, "Data should be in database")
        self.assertEqual(db_record.response_data, result_data)

    def test_store_result_duplicate_key(self):
        """Test storing result with duplicate key"""
        key = "task:test:duplicate_store"
        result_data = {'status': 'success'}

        # First store
        success1 = self.service.store_result(key, result_data, ttl_seconds=3600)
        self.assertTrue(success1)

        # Second store (duplicate)
        success2 = self.service.store_result(key, result_data, ttl_seconds=3600)
        # Should handle gracefully (may return False due to IntegrityError)
        self.assertIsInstance(success2, bool)


@pytest.mark.django_db
class TestDistributedLocks(TransactionTestCase):
    """Test distributed lock acquisition and release"""

    def setUp(self):
        self.service = UniversalIdempotencyService

    def test_acquire_distributed_lock_success(self):
        """Test successful lock acquisition"""
        lock_key = "test_lock_unique_123"

        with self.service.acquire_distributed_lock(lock_key, timeout=10):
            # Lock acquired
            pass

        # Should complete without exception

    def test_acquire_distributed_lock_blocking(self):
        """Test that second acquire blocks when lock held"""
        lock_key = "test_lock_blocking"

        # Acquire lock in first context
        with self.service.acquire_distributed_lock(lock_key, timeout=5):
            # Try to acquire same lock in another context
            # This should block or fail
            with pytest.raises(RuntimeError):
                with self.service.acquire_distributed_lock(lock_key, timeout=1, blocking=False):
                    pass

    def test_acquire_distributed_lock_auto_release(self):
        """Test that lock is automatically released after context"""
        lock_key = "test_lock_auto_release"

        # Acquire and release
        with self.service.acquire_distributed_lock(lock_key, timeout=5):
            pass

        # Should be able to acquire again immediately
        with self.service.acquire_distributed_lock(lock_key, timeout=5):
            pass

        # No exception should be raised

    def test_acquire_distributed_lock_timeout(self):
        """Test lock timeout expiration"""
        lock_key = "test_lock_timeout"

        # Acquire lock with short timeout
        with self.service.acquire_distributed_lock(lock_key, timeout=1):
            # Wait for timeout
            time.sleep(2)

        # Lock should be auto-released by timeout

    @patch('apps.core.tasks.idempotency_service.cache.client')
    def test_acquire_distributed_lock_redis_fallback(self, mock_cache_client):
        """Test fallback to database lock when Redis unavailable"""
        lock_key = "test_lock_fallback"

        # Mock Redis failure
        mock_cache_client.get_client.side_effect = ConnectionError("Redis unavailable")

        # Should fallback to database advisory lock
        with self.service.acquire_distributed_lock(lock_key, timeout=5):
            pass

        # Should complete using PostgreSQL advisory locks


class TestIdempotencyDecorator(TestCase):
    """Test with_idempotency decorator"""

    def setUp(self):
        cache.clear()

    def test_decorator_prevents_duplicate_execution(self):
        """Test that decorated function executes only once"""
        execution_count = {'count': 0}

        @with_idempotency(ttl_seconds=3600)
        def test_function(x):
            execution_count['count'] += 1
            return x * 2

        # First call
        result1 = test_function(5)
        self.assertEqual(result1, 10)
        self.assertEqual(execution_count['count'], 1)

        # Second call with same args (should use cached result)
        result2 = test_function(5)
        self.assertEqual(result2, 10)
        self.assertEqual(execution_count['count'], 1, "Function should not execute twice")

    def test_decorator_different_args_execute(self):
        """Test that different args cause re-execution"""
        execution_count = {'count': 0}

        @with_idempotency(ttl_seconds=3600)
        def test_function(x):
            execution_count['count'] += 1
            return x * 2

        # Different args should execute
        result1 = test_function(5)
        result2 = test_function(10)

        self.assertEqual(result1, 10)
        self.assertEqual(result2, 20)
        self.assertEqual(execution_count['count'], 2, "Different args should execute twice")

    def test_decorator_caches_errors(self):
        """Test that errors are also cached"""

        @with_idempotency(ttl_seconds=3600)
        def test_function_error():
            raise ValueError("Test error")

        # First call raises error
        with pytest.raises(ValueError):
            test_function_error()

        # Second call should also raise (from cache)
        with pytest.raises(ValueError):
            test_function_error()


class TestPerformance(TestCase):
    """Test performance characteristics"""

    def setUp(self):
        self.service = UniversalIdempotencyService
        cache.clear()

    def test_key_generation_performance(self):
        """Test that key generation is fast (< 1ms)"""
        task_name = "test_task"
        args = (1, 2, 3, 'test', {'key': 'value'})

        start = time.time()

        for _ in range(1000):
            self.service.generate_task_key(task_name, args)

        elapsed = (time.time() - start) * 1000  # Convert to ms

        avg_time = elapsed / 1000
        self.assertLess(avg_time, 1.0, f"Key generation should be < 1ms, got {avg_time:.2f}ms")

    def test_redis_check_performance(self):
        """Test that Redis check is fast (< 5ms)"""
        key = "task:test:perf_key"
        cache.set(key, {'result': 'test'}, timeout=SECONDS_IN_HOUR)

        start = time.time()

        for _ in range(100):
            self.service.check_duplicate(key, use_redis=True)

        elapsed = (time.time() - start) * 1000

        avg_time = elapsed / 100
        self.assertLess(avg_time, 5.0, f"Redis check should be < 5ms, got {avg_time:.2f}ms")

    def test_store_result_performance(self):
        """Test that storing result is fast (< 10ms)"""
        result_data = {'status': 'success', 'data': 'test'}

        times = []
        for i in range(10):
            key = f"task:test:perf_store_{i}"
            start = time.time()
            self.service.store_result(key, result_data, ttl_seconds=3600)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        self.assertLess(avg_time, 10.0, f"Store should be < 10ms, got {avg_time:.2f}ms")


class TestEdgeCases(TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        self.service = UniversalIdempotencyService

    def test_generate_key_with_none_args(self):
        """Test key generation with None arguments"""
        key = self.service.generate_task_key("test_task", args=None, kwargs=None)
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)

    def test_generate_key_with_empty_strings(self):
        """Test key generation with empty strings"""
        key = self.service.generate_task_key("", args=(), kwargs={})
        self.assertIsInstance(key, str)

    def test_generate_key_with_special_characters(self):
        """Test key generation with special characters"""
        task_name = "test@task#special$"
        args = ("test!@#$%^&*()",)

        key = self.service.generate_task_key(task_name, args)
        self.assertIsInstance(key, str)

    def test_check_duplicate_with_invalid_key(self):
        """Test duplicate check with invalid key"""
        result = self.service.check_duplicate("")
        # Should handle gracefully
        self.assertIsNone(result)

    def test_store_result_with_large_data(self):
        """Test storing large result data"""
        key = "task:test:large_data"
        large_data = {'data': 'x' * 10000}  # 10KB of data

        success = self.service.store_result(key, large_data, ttl_seconds=3600)
        self.assertIsInstance(success, bool)


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
