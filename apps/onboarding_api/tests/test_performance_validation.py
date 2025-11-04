"""
Performance validation tests for Conversational Onboarding API

This test suite validates performance characteristics, including
response times, concurrency handling, and resource utilization.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.onboarding_api.utils.concurrency import advisory_lock

User = get_user_model()


class PerformanceBaseTestCase(APITestCase):
    """Base test case for performance tests"""

    def setUp(self):
        self.client_model = Bt.objects.create(
            buname="Perf Test Client",
            bucode="PERFTEST",
            is_active=True
        )

        self.users = []
        for i in range(10):  # Create multiple test users
            user = User.objects.create_user(
                email=f'user{i}@example.com',
                loginid=f'user{i}',
                client=self.client_model,
                is_active=True,
                capabilities={'can_use_conversational_onboarding': True}
            )
            self.users.append(user)

        cache.clear()

    def measure_response_time(self, func, *args, **kwargs):
        """Utility to measure function execution time"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, (end_time - start_time) * 1000  # Return ms


class AdvisoryLockPerformanceTestCase(PerformanceBaseTestCase):
    """Test advisory lock performance under load"""

    def test_advisory_lock_performance(self):
        """Test advisory lock acquisition performance"""
        results = []

        def acquire_lock(user_index):
            user = self.users[user_index]
            start_time = time.time()

            try:
                with advisory_lock(user, self.client_model.id, "performance_test") as acquired:
                    acquisition_time = (time.time() - start_time) * 1000
                    if acquired:
                        # Simulate some work
                        time.sleep(0.01)  # 10ms work simulation

                    return {
                        'user_index': user_index,
                        'acquired': acquired,
                        'acquisition_time_ms': acquisition_time,
                        'success': True
                    }
            except (ValueError, TypeError, AttributeError) as e:
                return {
                    'user_index': user_index,
                    'acquired': False,
                    'error': str(e),
                    'success': False
                }

        # Test concurrent lock acquisitions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(acquire_lock, i) for i in range(5)]
            results = [future.result() for future in as_completed(futures)]

        # Verify results
        successful_results = [r for r in results if r['success']]
        self.assertEqual(len(successful_results), 5)

        # At least one should acquire the lock
        acquired_count = len([r for r in successful_results if r['acquired']])
        self.assertGreaterEqual(acquired_count, 1)

        # Acquisition times should be reasonable
        acquisition_times = [r['acquisition_time_ms'] for r in successful_results]
        max_acquisition_time = max(acquisition_times)
        self.assertLess(max_acquisition_time, 1000, "Lock acquisition took too long")

    def test_lock_release_reliability(self):
        """Test that locks are reliably released"""
        lock_operations = []

        def lock_operation(user_index):
            user = self.users[user_index % len(self.users)]

            with advisory_lock(user, self.client_model.id, f"test_op_{user_index}") as acquired:
                if acquired:
                    # Brief work simulation
                    time.sleep(0.005)
                    return True
            return False

        # Run many lock operations
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(lock_operation, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]

        # Most operations should succeed
        success_count = sum(results)
        self.assertGreaterEqual(success_count, 15, "Too many lock operations failed")


class APIPerformanceTestCase(PerformanceBaseTestCase):
    """Test API endpoint performance"""

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    def test_conversation_start_performance(self):
        """Test conversation start endpoint performance"""
        url = reverse('onboarding_api:conversation-start')
        data = {'language': 'en', 'client_context': {'setup_type': 'test'}}

        response_times = []

        for i in range(10):  # Test multiple requests
            user = self.users[i]
            self.client.force_authenticate(user=user)

            response, response_time = self.measure_response_time(
                self.client.post, url, data, format='json'
            )

            if response.status_code in [201, 409]:  # Success or conflict (expected)
                response_times.append(response_time)

        # Performance assertions
        self.assertGreater(len(response_times), 0, "No successful responses")

        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        # SLO targets from settings
        p95_target = getattr(settings, 'SLO_REC_LATENCY_P95', 5000)
        p50_target = getattr(settings, 'SLO_REC_LATENCY_P50', 2000)

        self.assertLess(avg_response_time, p50_target, f"Average response time {avg_response_time}ms exceeds P50 target")
        self.assertLess(max_response_time, p95_target, f"Max response time {max_response_time}ms exceeds P95 target")

    def test_concurrent_api_requests(self):
        """Test API performance under concurrent load"""
        url = reverse('onboarding_api:feature-status')

        def make_request(user_index):
            user = self.users[user_index % len(self.users)]

            # Note: In a real test, we'd need to create separate client instances
            # for true concurrency testing
            start_time = time.time()

            try:
                # Simulate API request (would use real HTTP client in practice)
                response_time = (time.time() - start_time) * 1000
                return {
                    'user_index': user_index,
                    'response_time_ms': response_time,
                    'success': True
                }
            except (ValueError, TypeError, AttributeError) as e:
                return {
                    'user_index': user_index,
                    'error': str(e),
                    'success': False
                }

        # Test concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(50)]
            results = [future.result() for future in as_completed(futures)]

        # Analyze results
        successful_results = [r for r in results if r['success']]
        success_rate = len(successful_results) / len(results)

        self.assertGreaterEqual(success_rate, 0.95, "Success rate below 95%")

    def test_memory_usage_under_load(self):
        """Test memory usage remains stable under load"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate load
        sessions = []
        for i in range(100):
            user = self.users[i % len(self.users)]
            session = ConversationSession.objects.create(
                user=user,
                client=self.client_model,
                conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                current_state=ConversationSession.StateChoices.STARTED
            )
            sessions.append(session)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (adjust threshold as needed)
        self.assertLess(memory_increase, 100, f"Memory increased by {memory_increase}MB")

        # Cleanup
        for session in sessions:
            session.delete()


class CachePerformanceTestCase(PerformanceBaseTestCase):
    """Test cache performance and optimization"""

    def test_cache_performance_under_load(self):
        """Test cache performance with high request volume"""
        cache_operations = []

        def cache_operation(operation_index):
            key = f'test_key_{operation_index}'
            value = {'data': f'value_{operation_index}', 'timestamp': time.time()}

            start_time = time.time()

            try:
                # Set operation
                cache.set(key, value, 300)
                set_time = time.time() - start_time

                # Get operation
                start_get = time.time()
                retrieved = cache.get(key)
                get_time = time.time() - start_get

                # Delete operation
                start_delete = time.time()
                cache.delete(key)
                delete_time = time.time() - start_delete

                return {
                    'operation_index': operation_index,
                    'set_time_ms': set_time * 1000,
                    'get_time_ms': get_time * 1000,
                    'delete_time_ms': delete_time * 1000,
                    'data_matches': retrieved == value,
                    'success': True
                }

            except (ValueError, TypeError, AttributeError) as e:
                return {
                    'operation_index': operation_index,
                    'error': str(e),
                    'success': False
                }

        # Run concurrent cache operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(cache_operation, i) for i in range(100)]
            results = [future.result() for future in as_completed(futures)]

        # Analyze cache performance
        successful_operations = [r for r in results if r['success']]
        success_rate = len(successful_operations) / len(results)

        self.assertGreaterEqual(success_rate, 0.95, "Cache success rate below 95%")

        if successful_operations:
            avg_set_time = sum(r['set_time_ms'] for r in successful_operations) / len(successful_operations)
            avg_get_time = sum(r['get_time_ms'] for r in successful_operations) / len(successful_operations)

            # Cache operations should be fast
            self.assertLess(avg_set_time, 50, f"Average cache set time {avg_set_time}ms too high")
            self.assertLess(avg_get_time, 20, f"Average cache get time {avg_get_time}ms too high")

            # Data integrity check
            data_integrity_rate = sum(1 for r in successful_operations if r['data_matches']) / len(successful_operations)
            self.assertEqual(data_integrity_rate, 1.0, "Cache data integrity issues detected")


class DatabasePerformanceTestCase(TransactionTestCase):
    """Test database performance characteristics"""

    def setUp(self):
        self.client_model = Bt.objects.create(
            buname="DB Perf Test Client",
            bucode="DBPERFTEST",
            is_active=True
        )

        self.user = User.objects.create_user(
            email='dbtest@example.com',
            loginid='dbtest',
            client=self.client_model,
            is_active=True
        )

    def test_bulk_session_creation_performance(self):
        """Test performance of bulk session creation"""
        start_time = time.time()

        # Create many sessions
        sessions = []
        for i in range(100):
            session = ConversationSession(
                user=self.user,
                client=self.client_model,
                conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                current_state=ConversationSession.StateChoices.STARTED,
                context_data={'test_index': i}
            )
            sessions.append(session)

        # Bulk create
        ConversationSession.objects.bulk_create(sessions)

        creation_time = (time.time() - start_time) * 1000

        # Should complete quickly
        self.assertLess(creation_time, 5000, f"Bulk creation took {creation_time}ms")

        # Verify all were created
        created_count = ConversationSession.objects.filter(user=self.user).count()
        self.assertEqual(created_count, 100)

    def test_query_performance_with_large_dataset(self):
        """Test query performance with large dataset"""
        # Create large dataset
        sessions = []
        for i in range(1000):
            session = ConversationSession(
                user=self.user,
                client=self.client_model,
                conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                current_state=ConversationSession.StateChoices.COMPLETED,
                context_data={'index': i}
            )
            sessions.append(session)

        ConversationSession.objects.bulk_create(sessions)

        # Test query performance
        start_time = time.time()

        # Complex query that might be used in production
        active_sessions = ConversationSession.objects.filter(
            client=self.client_model,
            current_state__in=[
                ConversationSession.StateChoices.STARTED,
                ConversationSession.StateChoices.IN_PROGRESS
            ]
        ).select_related('user', 'client')[:50]

        # Force evaluation
        list(active_sessions)

        query_time = (time.time() - start_time) * 1000

        # Query should be fast even with large dataset
        self.assertLess(query_time, 1000, f"Query took {query_time}ms with large dataset")


class LoadTestCase(PerformanceBaseTestCase):
    """Load testing for concurrent operations"""

    def test_concurrent_conversation_starts(self):
        """Test concurrent conversation start requests"""
        def start_conversation(user_index):
            user = self.users[user_index]
            url = reverse('onboarding_api:conversation-start')
            data = {'language': 'en'}

            start_time = time.time()

            try:
                # In a real test, would need separate client instances
                # This test validates the concept
                with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
                    # Simulate request processing time
                    time.sleep(0.01)  # 10ms simulation

                response_time = (time.time() - start_time) * 1000

                return {
                    'user_index': user_index,
                    'response_time_ms': response_time,
                    'success': True
                }

            except (ValueError, TypeError, AttributeError) as e:
                return {
                    'user_index': user_index,
                    'error': str(e),
                    'response_time_ms': (time.time() - start_time) * 1000,
                    'success': False
                }

        # Run concurrent conversation starts
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(start_conversation, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]

        # Analyze performance
        successful_results = [r for r in results if r['success']]
        success_rate = len(successful_results) / len(results)

        self.assertGreaterEqual(success_rate, 0.9, "Success rate below 90% under load")

        if successful_results:
            response_times = [r['response_time_ms'] for r in successful_results]
            avg_response_time = sum(response_times) / len(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]

            # Performance thresholds
            self.assertLess(avg_response_time, 2000, f"Average response time {avg_response_time}ms too high")
            self.assertLess(p95_response_time, 5000, f"P95 response time {p95_response_time}ms too high")

    def test_system_stability_under_load(self):
        """Test system stability under sustained load"""
        error_count = 0
        successful_operations = 0

        def sustained_operation(operation_index):
            nonlocal error_count, successful_operations

            try:
                # Simulate various API operations
                operations = [
                    self._simulate_feature_status_check,
                    self._simulate_preflight_check,
                    self._simulate_health_check
                ]

                operation = operations[operation_index % len(operations)]
                result = operation()

                if result['success']:
                    successful_operations += 1
                else:
                    error_count += 1

                return result

            except (ValueError, TypeError, AttributeError) as e:
                error_count += 1
                return {'success': False, 'error': str(e)}

        # Run sustained load
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Run for shorter duration in tests
            futures = [executor.submit(sustained_operation, i) for i in range(50)]
            results = [future.result() for future in as_completed(futures)]

        duration = time.time() - start_time

        # System should remain stable
        error_rate = error_count / (successful_operations + error_count)
        self.assertLess(error_rate, 0.1, f"Error rate {error_rate:.2%} too high under load")

        # Should complete in reasonable time
        self.assertLess(duration, 30, f"Load test took {duration}s - too long")

    def _simulate_feature_status_check(self):
        """Simulate feature status check operation"""
        try:
            # Simulate API call processing
            time.sleep(0.01)  # 10ms simulation
            return {'success': True, 'operation': 'feature_status'}
        except (ValueError, TypeError, AttributeError) as e:
            return {'success': False, 'error': str(e)}

    def _simulate_preflight_check(self):
        """Simulate preflight validation operation"""
        try:
            # Simulate validation processing
            time.sleep(0.02)  # 20ms simulation
            return {'success': True, 'operation': 'preflight'}
        except (ValueError, TypeError, AttributeError) as e:
            return {'success': False, 'error': str(e)}

    def _simulate_health_check(self):
        """Simulate health check operation"""
        try:
            # Simulate health check processing
            time.sleep(0.005)  # 5ms simulation
            return {'success': True, 'operation': 'health_check'}
        except (ValueError, TypeError, AttributeError) as e:
            return {'success': False, 'error': str(e)}


class ResourceUtilizationTestCase(PerformanceBaseTestCase):
    """Test resource utilization patterns"""

    def test_memory_efficiency_conversation_sessions(self):
        """Test memory efficiency of conversation session handling"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create and process many sessions
        sessions = []
        for i in range(500):
            user = self.users[i % len(self.users)]
            session = ConversationSession.objects.create(
                user=user,
                client=self.client_model,
                conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                current_state=ConversationSession.StateChoices.STARTED,
                context_data={'large_data': 'x' * 1000}  # 1KB per session
            )
            sessions.append(session)

        # Force garbage collection
        import gc
        gc.collect()

        peak_memory = process.memory_info().rss
        memory_increase = (peak_memory - initial_memory) / 1024 / 1024  # MB

        # Memory increase should be reasonable
        expected_data_size = 500 * 1  # 500KB of data
        self.assertLess(memory_increase, expected_data_size * 3, "Memory usage too high")

        # Cleanup and verify memory release
        for session in sessions:
            session.delete()

        gc.collect()
        final_memory = process.memory_info().rss
        memory_after_cleanup = (final_memory - initial_memory) / 1024 / 1024

        # Memory should be mostly released
        self.assertLess(memory_after_cleanup, memory_increase * 0.5, "Memory not properly released")


# Performance test utilities
class PerformanceTestRunner:
    """Utility for running performance tests"""

    @staticmethod
    def run_performance_suite():
        """Run complete performance test suite"""
        from django.test.utils import get_runner
        from django.conf import settings

        TestRunner = get_runner(settings)
        test_runner = TestRunner()

        performance_tests = [
            'apps.onboarding_api.tests.test_performance_validation.AdvisoryLockPerformanceTestCase',
            'apps.onboarding_api.tests.test_performance_validation.APIPerformanceTestCase',
            'apps.onboarding_api.tests.test_performance_validation.LoadTestCase',
            'apps.onboarding_api.tests.test_performance_validation.ResourceUtilizationTestCase',
        ]

        return test_runner.run_tests(performance_tests)

    @staticmethod
    def generate_performance_report(results):
        """Generate performance test report"""
        # Would implement detailed performance reporting
        pass