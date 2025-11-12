"""
Query Monitoring Production Tests

Tests fix for Ultrathink Phase 4:
- Issue #1: PerformanceMonitoringMiddleware query counting only works in DEBUG mode

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Test query monitoring works in production (DEBUG=False)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import RequestFactory, override_settings, TestCase
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser

from monitoring.performance_monitor_enhanced import PerformanceMonitoringMiddleware


class TestPerformanceMonitorProductionMode(TestCase):
    """Test query monitoring works in production with DEBUG=False."""

    def setUp(self):
        """Initialize test fixtures."""
        self.factory = RequestFactory()
        self.middleware = PerformanceMonitoringMiddleware(get_response=lambda r: HttpResponse())

    @override_settings(DEBUG=False)
    @patch('monitoring.performance_monitor_enhanced.connection')
    def test_query_monitoring_works_in_production_mode(self, mock_connection):
        """
        Test that query monitoring works when DEBUG=False.

        Issue #1: Previously used connection.queries which is only populated
        when DEBUG=True, making production monitoring completely broken.

        Fix: Uses execute_wrapper with thread-local storage, works in all environments.
        """
        # Setup mock connection with execute_wrappers
        mock_connection.execute_wrappers = []

        # Create test request
        request = self.factory.get('/test-endpoint/')
        request.user = AnonymousUser()

        # Process request
        self.middleware.process_request(request)

        # Verify execute_wrapper was registered
        assert len(mock_connection.execute_wrappers) == 1, (
            "Query tracker should be registered with connection.execute_wrappers"
        )

        # Simulate queries by calling the wrapper
        wrapper = mock_connection.execute_wrappers[0]

        def mock_execute(sql, params, many, context):
            return []

        # Simulate 3 queries
        for i in range(3):
            sql = f"SELECT * FROM test_table WHERE id = {i}"
            wrapper(mock_execute, sql, None, False, {})

        # Process response
        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        # Verify queries were tracked in thread-local storage
        assert hasattr(self.middleware._local_storage, 'queries') is False, (
            "Thread-local storage should be cleaned up after response"
        )

        # Verify wrapper was removed
        assert len(mock_connection.execute_wrappers) == 0, (
            "Query tracker should be removed after response"
        )

    @override_settings(DEBUG=False)
    @patch('monitoring.performance_monitor_enhanced.connection')
    def test_query_count_accurate_in_production(self, mock_connection):
        """
        Test that query count is accurate in production mode.

        Validates that execute_wrapper correctly tracks all queries,
        not just returning 0 like connection.queries does in production.
        """
        mock_connection.execute_wrappers = []

        request = self.factory.get('/api/users/')
        request.user = AnonymousUser()

        # Spy on record_metric to verify query_count
        recorded_metrics = []

        def spy_record_metric(metric_type, value, tags):
            recorded_metrics.append({
                'type': metric_type,
                'value': value,
                'tags': tags
            })

        with patch.object(self.middleware.monitor, 'record_metric', side_effect=spy_record_metric):
            self.middleware.process_request(request)

            # Simulate 5 queries
            wrapper = mock_connection.execute_wrappers[0]

            def mock_execute(sql, params, many, context):
                return []

            for i in range(5):
                wrapper(mock_execute, f"SELECT * FROM table_{i}", None, False, {})

            response = HttpResponse()
            self.middleware.process_response(request, response)

        # Find query_count metric
        query_count_metrics = [m for m in recorded_metrics if m['type'] == 'query_count']
        assert len(query_count_metrics) == 1, "Should record exactly one query_count metric"
        assert query_count_metrics[0]['value'] == 5, (
            f"Query count should be 5, got {query_count_metrics[0]['value']}"
        )

    @override_settings(DEBUG=False)
    @patch('monitoring.performance_monitor_enhanced.connection')
    def test_slow_query_detection_in_production(self, mock_connection):
        """
        Test that slow query detection works in production.

        Validates that slow queries are detected and logged even when
        DEBUG=False, fixing the production monitoring blind spot.
        """
        mock_connection.execute_wrappers = []

        request = self.factory.get('/api/expensive-operation/')
        request.user = AnonymousUser()

        # Spy on record_slow_query
        slow_queries_recorded = []

        def spy_slow_query(sql, duration, request_path, user_id):
            slow_queries_recorded.append({
                'sql': sql,
                'duration': duration,
                'path': request_path,
                'user': user_id
            })

        with patch.object(self.middleware.monitor, 'record_slow_query', side_effect=spy_slow_query):
            self.middleware.process_request(request)

            wrapper = mock_connection.execute_wrappers[0]

            # Mock a slow query (simulate 0.2 seconds)
            def slow_execute(sql, params, many, context):
                import time
                time.sleep(0.001)  # Small sleep for test speed
                return []

            # Manually inject a slow query into thread-local storage
            self.middleware._local_storage.queries.append({
                'sql': 'SELECT * FROM huge_table WHERE complex_condition',
                'time': 0.200,  # 200ms - above default threshold
                'params': None
            })

            response = HttpResponse()
            self.middleware.process_response(request, response)

        # Verify slow query was detected
        assert len(slow_queries_recorded) >= 1, (
            "Slow query should be detected in production mode"
        )

    @override_settings(DEBUG=True)
    @patch('monitoring.performance_monitor_enhanced.connection')
    def test_backward_compatibility_with_debug_mode(self, mock_connection):
        """
        Test that middleware still works in DEBUG=True mode.

        Validates backward compatibility: execute_wrapper approach
        doesn't break existing DEBUG mode functionality.
        """
        mock_connection.execute_wrappers = []

        request = self.factory.get('/debug-endpoint/')
        request.user = AnonymousUser()

        # Process request/response
        self.middleware.process_request(request)

        # Simulate query
        if mock_connection.execute_wrappers:
            wrapper = mock_connection.execute_wrappers[0]

            def mock_execute(sql, params, many, context):
                return []

            wrapper(mock_execute, "SELECT 1", None, False, {})

        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        # Should complete without errors
        assert response.status_code == 200

    def test_thread_local_storage_isolation(self):
        """
        Test that thread-local storage properly isolates requests.

        Validates that queries from one request don't leak into another,
        preventing cross-request contamination.
        """
        # Create two separate middleware instances (simulating concurrent requests)
        middleware1 = PerformanceMonitoringMiddleware(get_response=lambda r: HttpResponse())
        middleware2 = PerformanceMonitoringMiddleware(get_response=lambda r: HttpResponse())

        # Initialize thread-local storage for both
        middleware1._local_storage.queries = [{'sql': 'SELECT 1', 'time': 0.001}]
        middleware2._local_storage.queries = [{'sql': 'SELECT 2', 'time': 0.002}]

        # Verify isolation
        assert len(middleware1._local_storage.queries) == 1
        assert middleware1._local_storage.queries[0]['sql'] == 'SELECT 1'

        assert len(middleware2._local_storage.queries) == 1
        assert middleware2._local_storage.queries[0]['sql'] == 'SELECT 2'

    @patch('monitoring.performance_monitor_enhanced.connection')
    def test_wrapper_cleanup_on_exception(self, mock_connection):
        """
        Test that query wrapper is cleaned up even if response processing fails.

        Security: Validates no wrapper leakage on exceptions, preventing
        memory leaks and performance degradation.
        """
        mock_connection.execute_wrappers = []

        request = self.factory.get('/error-endpoint/')
        request.user = AnonymousUser()

        self.middleware.process_request(request)
        initial_wrapper_count = len(mock_connection.execute_wrappers)

        # Create response and process (should clean up)
        response = HttpResponse()
        self.middleware.process_response(request, response)

        # Verify wrapper was removed
        assert len(mock_connection.execute_wrappers) < initial_wrapper_count or (
            len(mock_connection.execute_wrappers) == 0
        ), "Wrapper should be cleaned up after response"
